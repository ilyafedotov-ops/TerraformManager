from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

import httpx
from azure.storage.blob import BlobClient  # type: ignore[import-untyped]
from google.cloud import storage as gcs_storage  # type: ignore[import-untyped]

from .models import (
    AzureBackendConfig,
    GCSBackendConfig,
    LocalBackendConfig,
    S3BackendConfig,
    StateBackendConfig,
    TerraformCloudBackendConfig,
)


class StateBackendError(Exception):
    """Raised when a backend fails to return a Terraform state file."""


@dataclass
class BackendReadResult:
    backend: str
    size_bytes: int
    data: bytes


def read_state_from_backend(config: StateBackendConfig) -> BackendReadResult:
    """Load the Terraform state bytes described by the provided backend configuration."""

    if isinstance(config, LocalBackendConfig):
        data = _read_local_state(config)
    elif isinstance(config, S3BackendConfig):
        data = _read_s3_state(config)
    elif isinstance(config, AzureBackendConfig):
        data = _read_azure_state(config)
    elif isinstance(config, GCSBackendConfig):
        data = _read_gcs_state(config)
    elif isinstance(config, TerraformCloudBackendConfig):
        data = _read_remote_state(config)
    else:  # pragma: no cover - defensive
        raise StateBackendError(f"Unsupported backend configuration: {config!r}")
    return BackendReadResult(backend=config.type, size_bytes=len(data), data=data)


def _read_local_state(config: LocalBackendConfig) -> bytes:
    candidate = Path(config.path).expanduser()
    if not candidate.exists() or not candidate.is_file():
        raise StateBackendError(f"State file '{candidate}' not found.")
    return candidate.read_bytes()


def _read_s3_state(config: S3BackendConfig) -> bytes:
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - import guard
        raise StateBackendError("boto3 is required for s3 state backends.") from exc

    session_kwargs: dict[str, Optional[str]] = {}
    if config.profile:
        session_kwargs["profile_name"] = config.profile
    if config.region:
        session_kwargs["region_name"] = config.region
    if config.session_token:
        session_kwargs["aws_session_token"] = config.session_token

    session = boto3.session.Session(**session_kwargs)

    client_kwargs: dict[str, Optional[str]] = {}
    if config.region:
        client_kwargs["region_name"] = config.region
    if config.endpoint_url:
        client_kwargs["endpoint_url"] = config.endpoint_url

    client = session.client("s3", **client_kwargs)
    try:
        response = client.get_object(Bucket=config.bucket, Key=config.key)
    except Exception as exc:  # noqa: BLE001
        raise StateBackendError(f"Failed to download state from s3://{config.bucket}/{config.key}: {exc}") from exc

    body = response.get("Body")
    if body is None:
        raise StateBackendError("S3 get_object response was missing a body.")
    data = body.read()
    if not isinstance(data, (bytes, bytearray)):
        raise StateBackendError("Unexpected state payload type from S3 backend.")
    return bytes(data)


def _read_azure_state(config: AzureBackendConfig) -> bytes:
    if not (config.connection_string or config.sas_token):
        raise StateBackendError("Azure backend requires a connection_string or sas_token.")

    try:
        if config.connection_string:
            client = BlobClient.from_connection_string(
                conn_str=config.connection_string,
                container_name=config.container,
                blob_name=config.key,
            )
        else:
            credential = config.sas_token.lstrip("?") if config.sas_token else None
            account_url = f"https://{config.storage_account}.blob.core.windows.net"
            client = BlobClient(account_url=account_url, container_name=config.container, blob_name=config.key, credential=credential)
        downloader = client.download_blob()
        return downloader.readall()
    except Exception as exc:  # noqa: BLE001
        raise StateBackendError(f"Failed to download Azure state blob: {exc}") from exc


def _read_gcs_state(config: GCSBackendConfig) -> bytes:
    try:
        if config.credentials_file:
            client = gcs_storage.Client.from_service_account_json(config.credentials_file, project=config.project)
        else:
            client = gcs_storage.Client(project=config.project)
    except Exception as exc:  # noqa: BLE001
        raise StateBackendError(f"Failed to initialise GCS client: {exc}") from exc

    bucket = client.bucket(config.bucket)
    blob = bucket.blob(config.prefix)
    try:
        return blob.download_as_bytes()
    except Exception as exc:  # noqa: BLE001
        raise StateBackendError(f"Failed to download gs://{config.bucket}/{config.prefix}: {exc}") from exc


def _read_remote_state(config: TerraformCloudBackendConfig) -> bytes:
    hostname = (config.hostname or "app.terraform.io").rstrip("/")
    token = config.token or os.getenv("TERRAFORM_CLOUD_TOKEN")
    if not token:
        raise StateBackendError("Terraform Cloud backend requires an API token.")

    state_url = f"https://{hostname}/api/v2/organizations/{config.organization}/workspaces/{config.workspace}/state-versions/current"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/vnd.api+json"}
    try:
        response = httpx.get(state_url, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise StateBackendError(f"Failed to query Terraform Cloud workspace: {exc}") from exc

    payload = response.json()
    attributes = payload.get("data", {}).get("attributes") or {}
    download_url = attributes.get("hosted-state-download-url")
    if not download_url:
        raise StateBackendError("Terraform Cloud response missing hosted-state-download-url.")
    try:
        download = httpx.get(download_url, timeout=30)
        download.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise StateBackendError(f"Failed to download Terraform Cloud state: {exc}") from exc
    return download.content
