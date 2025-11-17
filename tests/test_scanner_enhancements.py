from pathlib import Path
import backend.scanner


def test_scan_paths_includes_cost_and_drift(monkeypatch, tmp_path: Path) -> None:
    tf_file = tmp_path / "main.tf"
    tf_file.write_text(
        "resource \"aws_s3_bucket\" \"example\" { bucket = \"example\" }",
        encoding="utf-8",
    )

    fake_cost = {
        "tool": "infracost",
        "currency": "USD",
        "summary": {
            "total_monthly_cost": 100.0,
            "total_hourly_cost": 0.15,
            "diff_monthly_cost": 5.0,
            "diff_hourly_cost": 0.01,
        },
        "projects": [],
    }

    fake_drift = {
        "source": "plan.json",
        "counts": {"create": 1, "update": 0, "delete": 0, "replace": 0, "no-op": 0},
        "total_changes": 1,
        "has_changes": True,
        "resource_changes": [],
        "output_changes": [],
    }

    monkeypatch.setattr("backend.scanner.run_infracost", lambda paths, usage_file=None: fake_cost)
    monkeypatch.setattr("backend.scanner.parse_plan_summary", lambda plan_path: fake_drift)

    report = backend.scanner.scan_paths(
        [tf_file],
        cost_options={},
        plan_path=tmp_path / "plan.json",
    )

    assert report["cost"]["summary"]["total_monthly_cost"] == 100.0
    assert report["summary"]["cost"]["currency"] == "USD"
    assert report["drift"]["has_changes"] is True
    assert report["summary"]["drift"]["total_changes"] == 1
