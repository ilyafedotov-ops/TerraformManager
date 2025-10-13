"""
Utilities for assembling LLM prompts and (later) calling OpenAI/Azure OpenAI.

This module keeps the deterministic scanner untouched while giving the
UI/CLI layers a single place to build requests for AI-assisted
explanations and remediation proposals. API invocation will be layered on top of
the helper functions defined here once credentials are provided.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import hashlib
import json
import os
import time
import re

try:
    from openai import OpenAI
    from openai import AzureOpenAI
    from openai import APIConnectionError, RateLimitError, APITimeoutError, BadRequestError, APIStatusError, OpenAIError
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None
    AzureOpenAI = None

    class _MissingOpenAISDK(Exception):
        pass

    APIConnectionError = _MissingOpenAISDK
    RateLimitError = _MissingOpenAISDK
    APITimeoutError = _MissingOpenAISDK
    BadRequestError = _MissingOpenAISDK
    APIStatusError = _MissingOpenAISDK
    OpenAIError = _MissingOpenAISDK

DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"

from backend.utils.logging import get_logger

LOGGER = get_logger(__name__)


class LLMConfigurationError(RuntimeError):
    """Raised when the LLM provider configuration is incomplete."""


class LLMRequestError(RuntimeError):
    """Raised when the LLM provider fails to deliver a usable response."""


@dataclass
class KBPassage:
    """Structured snippet returned from the local knowledge base."""

    source: str
    content: str
    score: Optional[float] = None


@dataclass
class FindingContext:
    """Minimal data required to ground prompts for a Terraform finding."""

    rule_id: str
    title: str
    severity: str
    description: str
    recommendation: str
    file_path: Optional[str]
    snippet: str
    project_name: Optional[str] = None


@dataclass
class LLMRuntimeConfig:
    """
    Declarative configuration for invoking the OpenAI/Azure backends.

    This keeps feature flags and API toggles explicit, making it easy to extend
    when Azure-specific deployment parameters are supplied later on.
    """

    provider: str = "openai"
    model: str = DEFAULT_OPENAI_MODEL
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    api_version: Optional[str] = None
    deployment_name: Optional[str] = None
    temperature: float = 0.2
    max_output_tokens: int = 700
    enable_explanations: bool = False
    enable_patches: bool = False


CONFIG_ENV_HINTS = {
    "openai": ["OPENAI_API_KEY"],
    "azure": [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT",
    ],
}


class FileCache:
    """Simple JSON-on-disk cache to avoid repeated LLM calls for identical input."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            LOGGER.debug("Failed to read LLM cache entry %s: %s", path, exc)
            return None

    def set(self, key: str, value: Dict[str, Any]) -> None:
        path = self._path(key)
        tmp_path = path.with_suffix(".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as handle:
                json.dump(value, handle)
            tmp_path.replace(path)
        except Exception as exc:
            LOGGER.debug("Failed to write LLM cache entry %s: %s", path, exc)
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)


_CACHE: Optional[FileCache] = None


def _get_cache() -> FileCache:
    global _CACHE
    if _CACHE is None:
        env_path = os.getenv("LLM_CACHE_DIR")
        if env_path:
            cache_root = Path(env_path).expanduser()
        else:
            default_root = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
            cache_root = default_root / "terraform_manager" / "llm"
        _CACHE = FileCache(cache_root)
    return _CACHE


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_first_json_object(text: str) -> Optional[str]:
    depth = 0
    start: Optional[int] = None
    for index, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    return text[start : index + 1]
    return None


def _coerce_json_text(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""

    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        fenced = fence_match.group(1).strip()
        if fenced:
            return fenced

    if text.startswith("{") and text.endswith("}"):
        return text

    balanced = _extract_first_json_object(text)
    if balanced:
        return balanced.strip()

    return text


def _parse_json_payload(raw: str, purpose: str) -> Dict[str, Any]:
    candidate = _coerce_json_text(raw)
    if not candidate:
        raise LLMRequestError(f"LLM {purpose} payload was empty.")
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        preview = candidate[:200].replace("\n", " ").strip() or "<empty>"
        LOGGER.warning("Failed to parse %s payload: %s | preview=%s", purpose, exc, preview)
        raise LLMRequestError(
            f"LLM returned invalid JSON for {purpose}: {exc} (preview: {preview})"
        ) from exc
    if not isinstance(payload, dict):
        raise LLMRequestError(
            f"LLM {purpose} payload is not a JSON object (got {type(payload).__name__})."
        )
    return payload


def _validate_config(config: LLMRuntimeConfig, purpose: str) -> None:
    if config.provider == "openai":
        if not config.api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is not configured; unable to request "
                f"{purpose} from OpenAI."
            )
        if OpenAI is None:
            raise LLMConfigurationError(
                "The OpenAI Python SDK is not installed. Run `pip install openai` to enable LLM features."
            )
    elif config.provider == "azure":
        missing = []
        if not config.api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if not config.api_base:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not config.api_version:
            missing.append("AZURE_OPENAI_API_VERSION")
        if not config.deployment_name:
            missing.append("AZURE_OPENAI_DEPLOYMENT")
        if missing:
            joined = ", ".join(missing)
            raise LLMConfigurationError(
                f"Missing Azure OpenAI settings ({joined}); unable to request {purpose}."
            )
        if AzureOpenAI is None:
            raise LLMConfigurationError(
                "The OpenAI Python SDK is not installed. Run `pip install openai` to enable Azure OpenAI features."
            )
    else:
        raise LLMConfigurationError(f"Unsupported LLM provider '{config.provider}'.")


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_runtime_config_from_env(overrides: Optional[Dict[str, Any]] = None) -> LLMRuntimeConfig:
    overrides = overrides or {}
    provider = overrides.get("provider") or os.getenv("LLM_PROVIDER", "openai")
    provider = provider.strip().lower() if provider else "openai"
    if provider not in {"openai", "azure"}:
        provider = "openai"

    model = overrides.get("model") or os.getenv("LLM_MODEL", DEFAULT_OPENAI_MODEL)
    api_key = overrides.get("api_key")
    api_base = overrides.get("api_base")
    api_version = overrides.get("api_version")
    deployment_name = overrides.get("deployment_name")

    if provider == "azure":
        api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        api_base = api_base or os.getenv("AZURE_OPENAI_ENDPOINT")
        api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION")
        deployment_name = deployment_name or os.getenv("AZURE_OPENAI_DEPLOYMENT")
        if model == DEFAULT_OPENAI_MODEL and deployment_name:
            # For Azure, the deployment name acts as the model identifier.
            model = deployment_name
    else:
        provider = "openai"
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        api_base = api_base or os.getenv("OPENAI_API_BASE")

    temperature_override = overrides.get("temperature")
    temperature = (
        _coerce_float(temperature_override, 0.2)
        if temperature_override is not None
        else _coerce_float(os.getenv("LLM_TEMPERATURE"), 0.2)
    )

    max_tokens_override = overrides.get("max_output_tokens")
    max_output_tokens = (
        _coerce_int(max_tokens_override, 700)
        if max_tokens_override is not None
        else _coerce_int(os.getenv("LLM_MAX_OUTPUT_TOKENS"), 700)
    )

    enable_explanations_override = overrides.get("enable_explanations")
    if enable_explanations_override is None:
        enable_explanations = _env_flag("LLM_ENABLE_EXPLANATIONS", False)
    else:
        enable_explanations = bool(enable_explanations_override)

    enable_patches_override = overrides.get("enable_patches")
    if enable_patches_override is None:
        enable_patches = _env_flag("LLM_ENABLE_PATCHES", False)
    else:
        enable_patches = bool(enable_patches_override)

    cfg = LLMRuntimeConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        api_base=api_base,
        api_version=api_version,
        deployment_name=deployment_name,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        enable_explanations=enable_explanations,
        enable_patches=enable_patches,
    )
    return cfg


EXPLANATION_SYSTEM_PROMPT = (
    "You are an IaC security co-pilot. Your job is to explain Terraform review "
    "findings in clear, actionable language. Treat every answer as AI-assisted, "
    "not authoritative. Never change pass/fail decisions.\n\n"
    "Respond in compact JSON with the keys: `attribution`, `why`, `impact`, "
    "`how_to_fix`, `example_diff`, `kb_refs`. Keep outputs below 500 words."
)

PATCH_SYSTEM_PROMPT = (
    "You are helping an engineer remediate Terraform findings. Propose a patch "
    "that satisfies the stated goal while keeping unrelated code untouched. Do "
    "not assume ownership of merge decisions.\n\n"
    "Return JSON with `attribution`, `summary`, and `diff` keys. `diff` must be "
    "a unified diff starting with `---`/`+++`. If you cannot produce a safe fix, "
    "set `diff` to an empty string and explain why in `summary`."
)


def hash_snippet(snippet: str) -> str:
    """Stable identifier for caching (sha256 hex of normalized whitespace)."""

    normalized = "\n".join(line.rstrip() for line in snippet.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _render_passages(passages: Sequence[KBPassage]) -> str:
    chunks = []
    for idx, passage in enumerate(passages, start=1):
        header = f"[{idx}] Source: {passage.source}"
        if passage.score is not None:
            header += f" (score={passage.score:.3f})"
        chunks.append(f"{header}\n{passage.content.strip()}")
    return "\n\n".join(chunks) if chunks else "No supporting knowledge base passages supplied."


def _sanitize_messages(messages: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    sanitized = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        sanitized.append({"role": role, "content": redact_secrets(str(content))})
    return sanitized


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _make_cache_key(
    prefix: str,
    finding: FindingContext,
    passages: Sequence[KBPassage],
    config: LLMRuntimeConfig,
    extra_parts: Optional[Sequence[str]] = None,
) -> str:
    snippet_hash = hash_snippet(finding.snippet or "")
    passage_fingerprints = [
        f"{passage.source}:{_sha256(passage.content)}" for passage in passages
    ]
    parts = [
        prefix,
        config.provider,
        config.model,
        finding.rule_id,
        snippet_hash,
    ]
    if finding.file_path:
        parts.append(str(finding.file_path))
    if extra_parts:
        parts.extend(extra_parts)
    parts.extend(passage_fingerprints)
    return _sha256("||".join(parts))


def _extract_response_text(response: Any) -> str:
    # Newer OpenAI SDKs expose output_text directly.
    text = getattr(response, "output_text", None)
    if text:
        return text

    payload: Optional[Dict[str, Any]] = None
    if hasattr(response, "model_dump"):
        try:
            payload = response.model_dump()
        except Exception:
            payload = None
    if payload is None and hasattr(response, "to_dict"):
        try:
            payload = response.to_dict()
        except Exception:
            payload = None

    if payload:
        text = payload.get("output_text")
        if text:
            return text
        # Fall back to traversing structured content
        for key in ("output", "choices", "data"):
            if key not in payload or not payload[key]:
                continue
            for item in payload[key]:
                if isinstance(item, dict):
                    # responses-style
                    if "content" in item:
                        for chunk in item["content"]:
                            if not isinstance(chunk, dict):
                                continue
                            if chunk.get("type") == "output_text" and "text" in chunk:
                                inner = chunk["text"]
                                if isinstance(inner, dict):
                                    inner_text = inner.get("value") or inner.get("text")
                                    if inner_text:
                                        return inner_text
                                elif inner:
                                    return str(inner)
                            inner_text = chunk.get("text")
                            if isinstance(inner_text, str) and inner_text:
                                return inner_text
                    # chat.completions-style
                    message = item.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        if isinstance(content, str) and content:
                            return content
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict):
                                    if block.get("type") == "text" and block.get("text"):
                                        return str(block["text"])
                                    if "text" in block:
                                        return str(block["text"])
                else:
                    possible = getattr(item, "content", None)
                    if possible:
                        for chunk in possible:
                            text_value = getattr(chunk, "text", None)
                            if text_value:
                                if isinstance(text_value, str):
                                    return text_value
                                inner = getattr(text_value, "value", None)
                                if inner:
                                    return inner
    raise LLMRequestError("LLM response did not include any textual output.")


def _build_client(config: LLMRuntimeConfig):
    if config.provider == "azure":
        return AzureOpenAI(
            api_key=config.api_key,
            azure_endpoint=config.api_base,
            api_version=config.api_version,
        )
    return OpenAI(
        api_key=config.api_key,
        base_url=config.api_base,
    )


def _invoke_responses_api(
    messages: Sequence[Dict[str, str]],
    config: LLMRuntimeConfig,
    purpose: str,
) -> str:
    sanitized_messages = _sanitize_messages(messages)
    client = _build_client(config)
    max_attempts = 3
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = client.responses.create(
                model=config.model,
                input=sanitized_messages,
                temperature=config.temperature,
                max_output_tokens=config.max_output_tokens,
            )
            return _extract_response_text(response)
        except (RateLimitError, APIConnectionError, APITimeoutError, APIStatusError) as exc:
            last_exc = exc
            sleep_seconds = min(6.0, 2.0 ** attempt)
            LOGGER.warning(
                "LLM %s attempt %s/%s failed (%s). Retrying in %.1fs.",
                purpose,
                attempt,
                max_attempts,
                exc.__class__.__name__,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)
        except BadRequestError as exc:
            LOGGER.error("LLM %s request rejected: %s", purpose, exc)
            raise LLMRequestError(f"LLM rejected the {purpose} request: {exc}") from exc
        except OpenAIError as exc:
            last_exc = exc
            LOGGER.error("LLM %s request failed: %s", purpose, exc)
            break
    raise LLMRequestError(f"Failed to obtain {purpose} from LLM after {max_attempts} attempts.") from last_exc


def _normalise_explanation_payload(payload: Dict[str, Any], config: LLMRuntimeConfig) -> Dict[str, Any]:
    result = dict(payload)
    for key in ("why", "impact", "how_to_fix", "example_diff"):
        value = result.get(key)
        result[key] = value.strip() if isinstance(value, str) else ""

    kb_refs = result.get("kb_refs") or []
    if not isinstance(kb_refs, list):
        kb_refs = [kb_refs]
    result["kb_refs"] = [str(ref) for ref in kb_refs if ref]

    attribution_raw = result.get("attribution")
    attribution = dict(attribution_raw) if isinstance(attribution_raw, dict) else {}
    attribution.setdefault("provider", config.provider)
    attribution.setdefault("model", config.model)
    result["attribution"] = attribution
    return result


def _normalise_patch_payload(payload: Dict[str, Any], config: LLMRuntimeConfig) -> Dict[str, Any]:
    result = dict(payload)
    summary = result.get("summary", "")
    result["summary"] = summary.strip() if isinstance(summary, str) else ""
    diff_text = result.get("diff", "")
    result["diff"] = diff_text if isinstance(diff_text, str) else ""

    validation = result.get("validation")
    if isinstance(validation, dict):
        status = validation.get("status")
        validation["status"] = status.strip() if isinstance(status, str) else status
        details = validation.get("details")
        validation["details"] = details.strip() if isinstance(details, str) else details
        result["validation"] = validation
    elif validation is not None:
        result["validation"] = {}

    attribution_raw = result.get("attribution")
    attribution = dict(attribution_raw) if isinstance(attribution_raw, dict) else {}
    attribution.setdefault("provider", config.provider)
    attribution.setdefault("model", config.model)
    result["attribution"] = attribution
    return result


def request_explanation(
    finding: FindingContext,
    passages: Sequence[KBPassage],
    config: Optional[LLMRuntimeConfig] = None,
) -> Optional[Dict[str, Any]]:
    cfg = config or load_runtime_config_from_env()
    if not cfg.enable_explanations:
        LOGGER.debug("LLM explanations disabled; skipping request for %s.", finding.rule_id)
        return None

    _validate_config(cfg, "explanation")

    cache_key = _make_cache_key("explanation", finding, passages, cfg)
    cache = _get_cache()
    cached = cache.get(cache_key)
    if cached:
        cached_copy = json.loads(json.dumps(cached))
        attribution = dict(cached_copy.get("attribution") or {})
        attribution["cached"] = True
        cached_copy["attribution"] = attribution
        return cached_copy

    messages = build_explanation_messages(
        finding=finding,
        passages=passages,
        provider=cfg.provider,
        model=cfg.model,
    )

    raw = _invoke_responses_api(messages, cfg, "explanation")
    payload = _parse_json_payload(raw, "explanation")

    normalised = _normalise_explanation_payload(payload, cfg)
    cache.set(cache_key, normalised)

    result = json.loads(json.dumps(normalised))
    attribution = dict(result.get("attribution") or {})
    attribution["cached"] = False
    result["attribution"] = attribution
    return result


def request_patch(
    finding: FindingContext,
    fix_goal: str,
    passages: Sequence[KBPassage],
    config: Optional[LLMRuntimeConfig] = None,
) -> Optional[Dict[str, Any]]:
    cfg = config or load_runtime_config_from_env()
    if not cfg.enable_patches:
        LOGGER.debug("LLM patch suggestions disabled; skipping request for %s.", finding.rule_id)
        return None

    _validate_config(cfg, "patch suggestion")

    extra_parts = [_sha256(fix_goal or "")]
    cache_key = _make_cache_key("patch", finding, passages, cfg, extra_parts=extra_parts)
    cache = _get_cache()
    cached = cache.get(cache_key)
    if cached:
        cached_copy = json.loads(json.dumps(cached))
        attribution = dict(cached_copy.get("attribution") or {})
        attribution["cached"] = True
        cached_copy["attribution"] = attribution
        return cached_copy

    messages = build_patch_messages(
        finding=finding,
        fix_goal=fix_goal,
        passages=passages,
        provider=cfg.provider,
        model=cfg.model,
    )

    raw = _invoke_responses_api(messages, cfg, "patch suggestion")
    payload = _parse_json_payload(raw, "patch")

    normalised = _normalise_patch_payload(payload, cfg)
    cache.set(cache_key, normalised)

    result = json.loads(json.dumps(normalised))
    attribution = dict(result.get("attribution") or {})
    attribution["cached"] = False
    result["attribution"] = attribution
    return result


def build_explanation_messages(
    finding: FindingContext,
    passages: Sequence[KBPassage],
    provider: str = "openai",
    model: str = DEFAULT_OPENAI_MODEL,
    locale: str = "en-US",
) -> List[Dict[str, str]]:
    """
    Prepare chat messages for an explanation request.

    The LLM is instructed to stay within the provided knowledge base context and
    cite sources explicitly. Output is JSON so downstream callers can merge it
    into the structured report without post-processing.
    """

    user_sections = [
        "You must produce AI-assisted commentary for the following finding.",
        f"Locale: {locale}",
        f"Provider tag: {provider}",
        f"Model tag: {model}",
        "Finding metadata:",
        f"- Rule ID: {finding.rule_id}",
        f"- Title: {finding.title}",
        f"- Severity: {finding.severity}",
        f"- Description: {finding.description}",
        f"- Recommendation: {finding.recommendation}",
    ]
    if finding.file_path:
        user_sections.append(f"- File: {finding.file_path}")
    if finding.project_name:
        user_sections.append(f"- Project: {finding.project_name}")

    user_sections.extend(
        [
            "",
            "Terraform snippet under review:",
            "```hcl",
            finding.snippet.strip() or "# snippet unavailable",
            "```",
            "",
            "Relevant knowledge base excerpts:",
            _render_passages(passages),
            "",
            "Response contract:",
            "- Always respond with JSON formatting.",
            "- `attribution.provider` MUST be a string (e.g., \"openai\").",
            "- `attribution.model` MUST echo the selected model name.",
            "- `attribution.confidence` MUST be one of: low, medium, high.",
            "- `kb_refs` MUST list the sources you cited using the bracket IDs.",
            "- If information is missing, state \"insufficient context\" rather than inventing facts.",
        ]
    )

    return [
        {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": "\n".join(user_sections),
        },
    ]


def build_patch_messages(
    finding: FindingContext,
    fix_goal: str,
    passages: Sequence[KBPassage],
    provider: str = "openai",
    model: str = DEFAULT_OPENAI_MODEL,
) -> List[Dict[str, str]]:
    """
    Assemble chat messages for a remediation diff request.

    The prompt keeps the model focused on the specific change being requested and
    discourages speculative edits.
    """

    user_sections = [
        "You must suggest a Terraform diff that addresses the stated goal.",
        f"Provider tag: {provider}",
        f"Model tag: {model}",
        f"Rule ID: {finding.rule_id}",
        f"Goal: {fix_goal}",
        "",
        "Existing Terraform snippet:",
        "```hcl",
        finding.snippet.strip() or "# snippet unavailable",
        "```",
        "",
        "Grounding knowledge:",
        _render_passages(passages),
        "",
        "Diff requirements:",
        "- Only touch resources necessary to satisfy the goal.",
        "- Preserve variable names and formatting where possible.",
        "- Output unified diff syntax.",
        "- Leave `diff` empty if you cannot recommend a safe change.",
    ]

    return [
        {"role": "system", "content": PATCH_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_sections)},
    ]


def redact_secrets(payload: str) -> str:
    """
    Basic defense-in-depth redaction. Expand with organisation-specific patterns.

    Currently strips obvious AWS-style keys; this will be extended once API
    integration lands.
    """

    replacements = [
        ("AWS_ACCESS_KEY_ID", "REDACTED_AWS_ACCESS_KEY_ID"),
        ("AWS_SECRET_ACCESS_KEY", "REDACTED_AWS_SECRET_ACCESS_KEY"),
    ]
    redacted = payload
    for needle, token in replacements:
        redacted = redacted.replace(needle, token)
    return redacted


def validate_provider_config(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate provider configuration without making a network call."""
    cfg = load_runtime_config_from_env(overrides or {})
    try:
        _validate_config(cfg, "connectivity test")
        return {"ok": True, "provider": cfg.provider, "model": cfg.model}
    except LLMConfigurationError as exc:
        return {"ok": False, "error": str(exc)}


def live_ping(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Attempt a very small Responses API call to check connectivity (may incur minimal cost)."""
    cfg = load_runtime_config_from_env(overrides or {})
    try:
        _validate_config(cfg, "connectivity ping")
    except LLMConfigurationError as exc:
        return {"ok": False, "error": str(exc)}

    # Keep payload tiny
    msg = [
        {"role": "system", "content": 'You are a health-check agent. Reply with JSON {"status": "ok"}.'},
        {"role": "user", "content": "ping"},
    ]
    # Temporarily reduce tokens
    cfg.max_output_tokens = min(64, cfg.max_output_tokens)
    try:
        raw = _invoke_responses_api(msg, cfg, "health ping")
        payload = _parse_json_payload(raw, "ping")
        return {"ok": True, "response": payload}
    except Exception as exc:  # noqa: BLE001 keep broad here for visibility
        return {"ok": False, "error": str(exc.__class__.__name__) + ": " + str(exc)}
