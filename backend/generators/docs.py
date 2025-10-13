from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.rag import warm_index
from backend.utils.logging import get_logger

from .registry import GeneratorDefinition, list_generator_definitions

LOGGER = get_logger(__name__)


@dataclass
class DocGenerationResult:
    slug: str
    doc_path: Path
    knowledge_path: Optional[Path]
    stdout: str


def _resolve_terraform_docs(binary: Optional[str] = None) -> Optional[str]:
    if binary:
        return binary
    return shutil.which("terraform-docs")


def _render_module(definition: GeneratorDefinition) -> Dict[str, str]:
    payload_data = dict(definition.example_payload or {})
    payload_model = definition.model(**payload_data)
    return definition.render(payload_model)


def _terraform_docs_output(
    binary: str,
    module_dir: Path,
    config_path: Optional[Path],
) -> str:
    command: List[str] = [binary, "markdown", "table"]
    if config_path:
        command.append(f"--config={config_path}")
    command.append(str(module_dir))
    LOGGER.debug("Running terraform-docs", extra={"command": command, "cwd": str(module_dir)})
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _build_doc_body(definition: GeneratorDefinition, terraform_docs_markdown: str) -> str:
    lines: List[str] = [
        f"# {definition.title}",
        "",
        definition.description,
        "",
        "## Metadata",
        f"- **Slug:** `{definition.slug}`",
        f"- **Provider:** `{definition.provider}`",
        f"- **Service:** `{definition.service}`",
    ]
    if definition.compliance:
        lines.append("- **Compliance:** " + ", ".join(f"`{item}`" for item in definition.compliance))
    if definition.requirements:
        lines.append("- **Provider Requirements:** " + ", ".join(definition.requirements))
    if definition.features:
        lines.append("- **Features:** " + ", ".join(f"`{k}`={v}" for k, v in sorted(definition.features.items())))

    lines.append("")
    lines.append("## Terraform Docs")
    lines.append("")
    lines.append(terraform_docs_markdown)
    lines.append("")
    return "\n".join(lines)


def _write_doc_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_docs(
    output_dir: Path,
    knowledge_dir: Optional[Path] = None,
    config_path: Optional[Path] = None,
    binary: Optional[str] = None,
    reindex: bool = True,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    knowledge_dir_final = knowledge_dir
    if knowledge_dir_final:
        knowledge_dir_final.mkdir(parents=True, exist_ok=True)

    binary_path = _resolve_terraform_docs(binary)
    if not binary_path:
        LOGGER.warning("terraform-docs CLI not found; skipping documentation generation.")
        return {"status": "skipped", "reason": "terraform-docs CLI not found"}

    config = Path(config_path) if config_path else Path(".terraform-docs.yml")
    if not config.exists():
        LOGGER.warning("terraform-docs config %s missing; proceeding with defaults.", config)
        config = None

    results: List[DocGenerationResult] = []

    for definition in list_generator_definitions():
        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            rendered = _render_module(definition)
            module_file = tmpdir / rendered["filename"]
            module_file.write_text(rendered["content"], encoding="utf-8")

            try:
                tf_docs_output = _terraform_docs_output(binary_path, tmpdir, config)
            except subprocess.CalledProcessError as exc:
                LOGGER.error("terraform-docs failed for %s: %s", definition.slug, exc.stderr)
                results.append(
                    DocGenerationResult(
                        slug=definition.slug,
                        doc_path=Path(),
                        knowledge_path=None,
                        stdout="",
                    )
                )
                continue

        doc_content = _build_doc_body(definition, tf_docs_output)
        doc_filename = definition.slug.replace("/", "_") + ".md"
        doc_path = output_dir / doc_filename
        _write_doc_file(doc_path, doc_content)

        knowledge_path: Optional[Path] = None
        if knowledge_dir_final:
            knowledge_filename = definition.slug.replace("/", "_") + ".md"
            knowledge_path = knowledge_dir_final / knowledge_filename
            knowledge_front_matter = (
                f"---\n"
                f"title: \"{definition.title}\"\n"
                f"slug: \"{definition.slug}\"\n"
                f"category: \"generator\"\n"
                f"---\n\n"
            )
            _write_doc_file(knowledge_path, knowledge_front_matter + doc_content)

        results.append(
            DocGenerationResult(
                slug=definition.slug,
                doc_path=doc_path,
                knowledge_path=knowledge_path,
                stdout=tf_docs_output,
            )
        )

    indexed_docs = 0
    if reindex and knowledge_dir_final:
        indexed_docs = warm_index()

    return {
        "status": "ok",
        "generated": [
            {
                "slug": item.slug,
                "doc_path": str(item.doc_path),
                "knowledge_path": str(item.knowledge_path) if item.knowledge_path else None,
            }
            for item in results
        ],
        "indexed_documents": indexed_docs,
    }


__all__ = ["generate_docs", "DocGenerationResult"]
