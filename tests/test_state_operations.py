from __future__ import annotations

import json
from pathlib import Path

from backend.db.session import init_models, session_scope
from backend.storage import create_project
from backend.state.models import LocalBackendConfig
from backend.state.reader import load_state_from_bytes
from backend.state.storage import persist_state_document
from backend.state.operations import remove_state_resources, move_state_resource


def _build_state_bytes() -> bytes:
    payload = {
        "serial": 4,
        "terraform_version": "1.8.5",
        "lineage": "demo",
        "resources": [
            {
                "address": "aws_s3_bucket.logs",
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "logs",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {"bucket": "logs-bucket"},
                        "dependencies": [],
                    }
                ],
            },
            {
                "address": "module.network.aws_vpc.default",
                "mode": "managed",
                "type": "aws_vpc",
                "name": "default",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "index_key": 0,
                        "schema_version": 1,
                        "attributes": {"cidr_block": "10.0.0.0/16"},
                        "dependencies": [],
                    }
                ],
            },
        ],
        "outputs": {"bucket_name": {"value": "logs-bucket", "sensitive": False, "type": "string"}},
    }
    return json.dumps(payload).encode("utf-8")


def _prepare_state(db_path: Path) -> tuple[str, str]:
    init_models(db_path)
    projects_root = db_path.parent / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)
    with session_scope(db_path) as session:
        project = create_project("demo", projects_root=projects_root, db_path=db_path, session=session)
        document = load_state_from_bytes(_build_state_bytes(), backend_type="local")
        record = persist_state_document(
            session=session,
            project_id=project["id"],
            workspace="default",
            backend=LocalBackendConfig(path="demo.tfstate"),
            document=document,
        )
        session.commit()
        return project["id"], record.id


def test_remove_state_resources(tmp_path):
    db_path = tmp_path / "app.db"
    project_id, state_id = _prepare_state(db_path)
    with session_scope(db_path) as session:
        updated = remove_state_resources(
            session,
            state_id=state_id,
            addresses=["aws_s3_bucket.logs", "module.network.aws_vpc.default[0]"],
        )
        assert updated["resource_count"] == 0
        session.commit()


def test_move_state_resource(tmp_path):
    db_path = tmp_path / "app.db"
    project_id, state_id = _prepare_state(db_path)
    with session_scope(db_path) as session:
        updated = move_state_resource(
            session,
            state_id=state_id,
            source="aws_s3_bucket.logs",
            destination="aws_s3_bucket.archive",
        )
        assert updated["resource_count"] == 2
        session.commit()
