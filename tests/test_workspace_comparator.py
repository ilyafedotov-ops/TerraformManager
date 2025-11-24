from __future__ import annotations

from backend.db.models import WorkspaceVariable
from backend.workspaces.comparator import WorkspaceDifference, compare_variables_map


def _var(key: str, value: str | None, sensitive: bool = False) -> WorkspaceVariable:
    return WorkspaceVariable(workspace_id="ws", key=key, value=value, sensitive=sensitive)  # type: ignore[arg-type]


def test_compare_variables_marks_severity_and_redacts_sensitive() -> None:
    vars_a = {
        "region": _var("region", "us-east-1"),
        "db_password": _var("db_password", "secret", sensitive=True),
        "count": _var("count", "5"),
    }
    vars_b = {
        "region": _var("region", "us-west-2"),
        "db_password": _var("db_password", "another", sensitive=True),
    }

    differences = compare_variables_map(vars_a, vars_b, info_keys=["region"])
    items = {diff.item: diff for diff in differences}

    assert "region" in items
    assert items["region"].severity == "info"
    assert items["db_password"].severity == "critical"
    assert items["db_password"].workspace_a_value == "<redacted>"
    assert items["db_password"].workspace_b_value == "<redacted>"
    assert "count" in items  # Missing in B is captured
    assert isinstance(items["count"], WorkspaceDifference)
