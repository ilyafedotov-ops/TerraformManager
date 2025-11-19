from __future__ import annotations

from typing import Optional

from .analyzer import parse_state_bytes
from .backends import BackendReadResult, read_state_from_backend
from .models import StateBackendConfig, TerraformStateDocument


def load_state_from_backend(config: StateBackendConfig) -> TerraformStateDocument:
    """Fetch and parse a Terraform state file using the provided backend definition."""

    result = read_state_from_backend(config)
    return parse_state_bytes(result.data, backend_type=result.backend)


def load_state_from_bytes(data: bytes, *, backend_type: str | None = None) -> TerraformStateDocument:
    """Parse Terraform state content that was already loaded into memory."""

    return parse_state_bytes(data, backend_type=backend_type)
