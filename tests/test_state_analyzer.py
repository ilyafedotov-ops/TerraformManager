from __future__ import annotations

import json

from backend.state import analyzer


def build_state_payload() -> bytes:
    payload = {
        "serial": 4,
        "terraform_version": "1.8.5",
        "lineage": "1234",
        "outputs": {
            "bucket_name": {
                "value": "example-bucket",
                "sensitive": False,
                "type": "string",
            },
        },
        "resources": [
            {
                "address": "aws_s3_bucket.example",
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "example",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {"bucket": "example-bucket"},
                        "sensitive_attributes": [["bucket"]],
                        "dependencies": ["aws_kms_key.state"],
                    }
                ],
            },
            {
                "module": "module.logging",
                "address": "module.logging.aws_cloudwatch_log_group.this",
                "mode": "managed",
                "type": "aws_cloudwatch_log_group",
                "name": "this",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "index_key": 0,
                        "schema_version": 1,
                        "attributes": {"name": "log-group"},
                        "sensitive_attributes": [],
                        "dependencies": [],
                    }
                ],
            },
        ],
    }
    return json.dumps(payload).encode("utf-8")


def test_parse_state_bytes_extracts_resources_and_outputs() -> None:
    data = build_state_payload()
    document = analyzer.parse_state_bytes(data, backend_type="local")

    assert document.resource_count == 2
    assert document.output_count == 1
    assert document.backend_type == "local"
    assert document.resources[0].address == "aws_s3_bucket.example"
    assert document.resources[1].module_address == "module.logging"
    assert document.resources[1].address.endswith("[0]")


def test_compare_state_to_plan_counts_actions() -> None:
    data = build_state_payload()
    document = analyzer.parse_state_bytes(data, backend_type="local")
    plan = {
        "planned_values": {
            "root_module": {
                "resources": [
                    {"address": "aws_s3_bucket.example"},
                    {"address": "module.logging.aws_cloudwatch_log_group.this[0]"},
                ]
            }
        },
        "resource_changes": [
            {"address": "aws_s3_bucket.example", "change": {"actions": ["update"]}},
            {"address": "module.logging.aws_cloudwatch_log_group.this[0]", "change": {"actions": ["delete"]}},
            {"address": "aws_iam_role.state", "change": {"actions": ["create"]}},
        ],
    }

    summary = analyzer.compare_state_to_plan(document, plan)

    assert summary.state_resource_count == 2
    assert summary.plan_resource_count == 2
    assert summary.resources_changed == 1
    assert summary.resources_destroyed == 1
    assert summary.resources_added == 1
    assert summary.state_only_resources == 0
