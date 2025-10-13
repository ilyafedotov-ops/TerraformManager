from base64 import b64decode
import zipfile
from io import BytesIO

from backend.generators.blueprints import render_blueprint_bundle
from backend.generators.models import (
    AwsS3BackendSettings,
    BlueprintComponent,
    BlueprintRemoteStateS3,
    BlueprintRequest,
)


def test_blueprint_bundle_creates_environment_dirs() -> None:
    request = BlueprintRequest(
        name="Platform Core",
        environments=["dev", "prod"],
        components=[
            BlueprintComponent(
                slug="aws/s3-secure-bucket",
                payload={
                    "bucket_name": "platform-{env}-logs",
                    "owner_tag": "platform",
                    "cost_center_tag": "ENG",
                },
            )
        ],
        remote_state=BlueprintRemoteStateS3(
            default=AwsS3BackendSettings(
                bucket="tfstate-platform",
                key="env/{env}/terraform.tfstate",
                region="us-east-1",
                dynamodb_table="tfstate-locks",
            )
        ),
    )

    result = render_blueprint_bundle(request)

    assert result["archive_name"] == "platform_core_blueprint.zip"
    archive_bytes = b64decode(result["archive_base64"])
    with zipfile.ZipFile(BytesIO(archive_bytes)) as zf:
        names = set(zf.namelist())
    assert "environments/dev/backend.tf" in names
    assert "environments/prod/backend.tf" in names
    assert "environments/dev/aws_s3_platform_dev_logs.tf" in names
    assert "README.md" in names
