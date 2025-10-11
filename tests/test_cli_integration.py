import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Dict, Any, Set

import pytest
import yaml


CONFIG_PATHS = [
    Path("tests/data/azure_diagnostics_config.yaml"),
    Path("tests/data/aws_s3_config.yaml"),
    Path("tests/data/aws_rds_config.yaml"),
    Path("tests/data/aws_misc_config.yaml"),
    Path("tests/data/k8s_security_config.yaml"),
]


def _load_cases() -> Iterable[Dict[str, Any]]:
    for config_path in CONFIG_PATHS:
        assert config_path.exists(), f"Config missing: {config_path}"
        config = yaml.safe_load(config_path.read_text()) or {}
        cases = config.get("cases", [])
        assert cases, f"Config {config_path} has no cases"
        for case in cases:
            yield {
                "name": case.get("name", "case"),
                "fixture": Path(case.get("fixture", "")),
                "expected": set(case.get("expected", [])),
                "config": config_path,
            }


def _finding_ids(report: Dict[str, Any]) -> Set[str]:
    return {finding.get("id", "") for finding in report.get("findings", []) if isinstance(finding, dict)}


@pytest.mark.parametrize("case", list(_load_cases()), ids=lambda c: f"{c['config'].name}:{c['name']}")
def test_cli_scan_cases(tmp_path: Path, case: Dict[str, Any]) -> None:
    fixture = case["fixture"]
    assert fixture.exists(), f"Fixture missing: {fixture}"

    out_path = tmp_path / f"{case['name']}_report.json"
    cmd = [
        sys.executable,
        "-m",
        "backend.cli",
        "scan",
        "--path",
        str(fixture),
        "--out",
        str(out_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"CLI scan failed (config={case['config']}, case={case['name']}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert out_path.exists(), f"CLI did not produce report for {case['name']}"

    report = json.loads(out_path.read_text())
    actual = _finding_ids(report)

    assert actual == case["expected"], (
        f"Mismatch for {case['name']} from {case['config']}: "
        f"expected {sorted(case['expected'])}, got {sorted(actual)}"
    )


def test_cli_baseline_generation(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/aws_s3_insecure.tf")
    out_path = tmp_path / "baseline.yaml"
    cmd = [
        sys.executable,
        "-m",
        "backend.cli",
        "baseline",
        "--path",
        str(fixture),
        "--out",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"CLI baseline failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert out_path.exists(), "Baseline command did not create output file"
    data = yaml.safe_load(out_path.read_text()) or {}

    ignore_entries = data.get("ignore", [])
    assert ignore_entries, "Baseline should include ignore entries"
    ignore_ids = {entry.get("id") for entry in ignore_entries}
    expected_ids = {
        "AWS-S3-PUBLIC-ACL::insecure",
        "AWS-S3-SSE::insecure",
        "AWS-S3-SECURE-TRANSPORT::insecure",
        "AWS-S3-ACCESS-LOGGING::insecure",
        "AWS-S3-ACCOUNT-BLOCK::missing",
    }
    assert expected_ids.issubset(ignore_ids), f"Expected IDs missing from baseline ignore list: {expected_ids - ignore_ids}"
    assert data.get("findings"), "Baseline should include findings section"


def test_cli_patch_bundle(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/aws_s3_insecure.tf")
    report_path = tmp_path / "report.json"
    patch_path = tmp_path / "autofix.patch"
    cmd = [
        sys.executable,
        "-m",
        "backend.cli",
        "scan",
        "--path",
        str(fixture),
        "--out",
        str(report_path),
        "--patch-out",
        str(patch_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"CLI scan with patch failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert patch_path.exists(), "Patch bundle file was not created"
    patch_text = patch_path.read_text()
    assert "--- a/aws_s3_insecure.tf" in patch_text
    assert "+  bucket = aws_s3_bucket.insecure.id" in patch_text
