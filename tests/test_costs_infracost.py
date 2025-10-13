import json
from pathlib import Path
from types import SimpleNamespace

from backend.costs.infracost import run_infracost


def test_run_infracost_parses_summary(monkeypatch, tmp_path: Path) -> None:
    sample_output = {
        "currency": "USD",
        "projects": [
            {
                "name": "app",
                "metadata": {"path": "."},
                "summary": {
                    "totalMonthlyCost": "123.45",
                    "totalHourlyCost": "0.17",
                    "diffTotalMonthlyCost": "10.00",
                    "diffTotalHourlyCost": "0.02",
                },
            }
        ],
        "summary": {
            "totalMonthlyCost": "123.45",
            "totalHourlyCost": "0.17",
            "diffTotalMonthlyCost": "10.00",
            "diffTotalHourlyCost": "0.02",
        },
    }

    monkeypatch.setattr("backend.costs.infracost.shutil.which", lambda _: "infracost")

    def fake_execute(command, cwd, env=None):
        assert command[0] == "infracost"
        assert "--format" in command
        return SimpleNamespace(stdout=json.dumps(sample_output))

    monkeypatch.setattr("backend.costs.infracost._execute", fake_execute)

    result = run_infracost([tmp_path])

    assert result["currency"] == "USD"
    assert result["summary"]["total_monthly_cost"] == 123.45
    assert result["projects"][0]["name"] == "app"
    assert result["projects"][0]["monthly_cost"] == 123.45


def test_run_infracost_handles_missing_cli(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("backend.costs.infracost.shutil.which", lambda _: None)
    result = run_infracost([tmp_path])
    assert "error" in result
