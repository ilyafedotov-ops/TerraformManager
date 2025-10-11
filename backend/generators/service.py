from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from jinja2 import Template


@dataclass
class AwsS3BackendConfig:
    bucket: str
    key: str
    region: str
    dynamodb_table: str


BASE_DIR = Path(__file__).resolve().parent


def _sanitize_resource_name(value: str, fallback: str = "bucket") -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]", "_", value or "")
    cleaned = cleaned.strip("_") or fallback
    if cleaned[0].isdigit():
        cleaned = f"bucket_{cleaned}"
    return cleaned.lower()


def render_aws_s3_bucket(payload: Dict[str, Any]) -> Dict[str, str]:
    bucket_name = payload.get("bucket_name", "my-secure-bucket")
    region = payload.get("region", "us-east-1")
    environment = payload.get("environment", "prod")
    owner_tag = payload.get("owner_tag", "platform-team")
    cost_center_tag = payload.get("cost_center_tag", "ENG-SRE")
    force_destroy = bool(payload.get("force_destroy", False))
    versioning = bool(payload.get("versioning", True))
    enforce_secure_transport = bool(payload.get("enforce_secure_transport", True))
    kms_key_id = payload.get("kms_key_id") or None

    resource_name = _sanitize_resource_name(bucket_name)

    backend_payload = payload.get("backend") or None
    backend_context: Optional[Dict[str, str]] = None
    if backend_payload:
        required_keys = {"bucket", "key", "region", "dynamodb_table"}
        if not required_keys.issubset(backend_payload.keys()):
            missing = required_keys - set(backend_payload.keys())
            raise ValueError(f"backend missing keys: {', '.join(sorted(missing))}")
        backend_context = {
            "bucket": backend_payload["bucket"],
            "key": backend_payload["key"],
            "region": backend_payload["region"],
            "dynamodb_table": backend_payload["dynamodb_table"],
        }

    template_path = BASE_DIR / "aws_s3_bucket.tf.j2"
    template = Template(template_path.read_text())
    content = template.render(
        region=region,
        name=resource_name,
        bucket_name=bucket_name,
        force_destroy=force_destroy,
        environment=environment,
        owner_tag=owner_tag,
        cost_center_tag=cost_center_tag,
        versioning=versioning,
        kms_key_id=kms_key_id,
        enforce_secure_transport=enforce_secure_transport,
        backend=backend_context,
    )

    filename = f"aws_s3_{resource_name}.tf"
    return {"filename": filename, "content": content}
