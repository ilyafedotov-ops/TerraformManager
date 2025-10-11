from pathlib import Path
import json
import sys
import subprocess
import tempfile

import pytest
import yaml

CONFIG = Path("tests/data/azure_diagnostics_config.yaml")


def _run_cli_scan(fixture: Path) -> set[str]:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)
    try:
        subprocess.run([
            sys.executable,
            "-m",
            "backend.cli",
            "scan",
            "--path",
            str(fixture),
            "--out",
            str(out_path),
        ], check=True, capture_output=True)
        report = json.loads(out_path.read_text())
    finally:
        if out_path.exists():
            out_path.unlink()
    return {finding.get("id", "") for finding in report.get("findings", [])}


@pytest.mark.integration
def test_cli_smoke_matches_config() -> None:
    assert CONFIG.exists(), "Azure diagnostics config missing"
    config = yaml.safe_load(CONFIG.read_text()) or {}
    for case in config.get("cases", []):
        fixture = Path(case.get("fixture", ""))
        assert fixture.exists(), f"Fixture missing: {fixture}"
        expected = set(case.get("expected", []))
        actual = _run_cli_scan(fixture)
        assert actual == expected, (
            f"CLI case {case.get('name')} mismatch: expected {sorted(expected)}, got {sorted(actual)}"
        )
