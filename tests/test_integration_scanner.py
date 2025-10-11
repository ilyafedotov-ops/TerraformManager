
from pathlib import Path
from typing import Set, Iterable

import yaml

from backend.scanner import scan_paths


CONFIG_PATHS = [
    Path("tests/data/azure_diagnostics_config.yaml"),
    Path("tests/data/aws_s3_config.yaml"),
    Path("tests/data/aws_rds_config.yaml"),
    Path("tests/data/aws_misc_config.yaml"),
    Path("tests/data/k8s_security_config.yaml"),
]


def _finding_ids(report) -> Set[str]:
    return {finding.get("id", "") for finding in report.get("findings", [])}


def _load_cases() -> Iterable[dict]:
    for config_path in CONFIG_PATHS:
        assert config_path.exists(), f"Config missing: {config_path}"
        config = yaml.safe_load(config_path.read_text()) or {}
        cases = config.get("cases", [])
        assert cases, f"Config {config_path} has no cases"
        for case in cases:
            case.setdefault("config", str(config_path))
            yield case


def test_integration_cases() -> None:
    for case in _load_cases():
        fixture = Path(case.get("fixture", ""))
        assert fixture.exists(), f"Fixture missing: {fixture}"
        expected = set(case.get("expected", []))

        report = scan_paths([fixture])
        actual = _finding_ids(report)

        assert actual == expected, (
            f"Case {case.get('name')} from {case.get('config')} mismatch: "
            f"expected {sorted(expected)}, got {sorted(actual)}"
        )
