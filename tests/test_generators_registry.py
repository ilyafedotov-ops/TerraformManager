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


def test_registry_render_servicebus_namespace() -> None:
    definition = get_generator_definition("azure/servicebus-namespace")
    payload = definition.model(
        resource_group_name="rg-integration",
        namespace_name="sbplatformdev",
        location="eastus2",
        queues=[{"name": "orders"}],
        topics=[{"name": "events", "subscriptions": [{"name": "critical"}]}],
    )
    result = definition.render(payload)
    assert result["filename"].startswith("azure_servicebus_")
    assert 'resource "azurerm_servicebus_namespace"' in result["content"]
    assert 'resource "azurerm_servicebus_queue"' in result["content"]
    assert 'resource "azurerm_servicebus_subscription"' in result["content"]


def test_registry_render_function_app() -> None:
    definition = get_generator_definition("azure/function-app")
    payload = definition.model(
        resource_group_name="rg-functions",
        function_app_name="func-app-prod",
        storage_account_name="stfuncprod",
        app_service_plan_name="plan-func-prod",
        location="eastus2",
        runtime="dotnet",
        runtime_version="8",
    )
    result = definition.render(payload)
    assert result["filename"].startswith("azure_function_app_")
    assert 'resource "azurerm_linux_function_app"' in result["content"]


def test_registry_render_api_management() -> None:
    definition = get_generator_definition("azure/api-management")
    payload = definition.model(
        resource_group_name="rg-apim",
        name="apim-platform-prod",
        location="eastus2",
        publisher_name="Platform Team",
        publisher_email="platform@example.com",
    )
    result = definition.render(payload)
    assert result["filename"].startswith("azure_api_management_")
    assert 'resource "azurerm_api_management"' in result["content"]
