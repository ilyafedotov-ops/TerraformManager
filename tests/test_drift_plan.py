import json
from pathlib import Path

from backend.drift.plan import parse_plan_summary


def test_parse_plan_summary_counts(tmp_path: Path) -> None:
    plan_data = {
        "resource_changes": [
            {"address": "aws_s3_bucket.bucket", "change": {"actions": ["update"]}},
            {"address": "aws_db_instance.db", "change": {"actions": ["create"]}},
            {"address": "azurerm_storage_account.sa", "change": {"actions": ["delete"]}},
            {"address": "aws_iam_role.role", "change": {"actions": ["create", "delete"]}},
        ],
        "output_changes": {
            "db_endpoint": {
                "actions": ["update"],
                "before": "old",
                "after": "new",
            }
        },
    }
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan_data), encoding="utf-8")

    result = parse_plan_summary(plan_file)

    assert result["has_changes"] is True
    assert result["counts"]["create"] == 1
    assert result["counts"]["update"] == 1
    assert result["counts"]["delete"] == 1
    assert result["counts"]["replace"] == 1
    assert result["total_changes"] == 4
    assert result["resource_changes"][0]["action"] == "update"
    assert result["output_changes"][0]["name"] == "db_endpoint"


def test_parse_plan_summary_missing_file(tmp_path: Path) -> None:
    plan_file = tmp_path / "missing.json"
    result = parse_plan_summary(plan_file)
    assert "error" in result
