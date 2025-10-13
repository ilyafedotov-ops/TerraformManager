from backend.generators.registry import get_generator_definition, list_generator_metadata


def test_registry_metadata_contains_schema() -> None:
    metadata = list_generator_metadata()
    s3_entry = next(item for item in metadata if item["slug"] == "aws/s3-secure-bucket")
    schema = s3_entry["schema"]
    assert "bucket_name" in schema["properties"]
    bucket_defaults = schema["properties"]["bucket_name"]
    assert bucket_defaults.get("default") == "my-secure-bucket"


def test_registry_render_with_typed_payload() -> None:
    definition = get_generator_definition("azure/storage-secure-account")
    payload = definition.model(
        resource_group_name="rg-app",
        storage_account_name="stapp1234567890",
        location="eastus",
    )
    result = definition.render(payload)
    assert result["filename"].startswith("azure_storage_")
    assert 'resource "azurerm_storage_account"' in result["content"]
