Azure Integration Services Remediation Plan
===========================================

Context
-------
- Current Terraform generators focus on storage, VNet, diagnostics, AKS, and Key Vault baselines.
- Azure Integration Services requirements cover Service Bus, Azure Functions, and API Management plus Azure DevOps pipeline hardening.
- Repository lacks modules, policies, and CI automation for these services, along with CAF naming/tag guidance and comprehensive RBAC/diagnostics coverage.

Missed Features Overview
------------------------
- Terraform generators for Service Bus namespaces/queues/topics, Azure Function Apps, and API Management instances.
- Policy checks and knowledge articles enforcing diagnostics, networking, and RBAC standards for the above services.
- Azure DevOps multi-environment YAML pipelines with fmt/validate/plan/tfsec/checkov/infracost gates and workspace separation.
- Consistent Azure naming/tagging strategy (CAF) integrated into generators/blueprints.
- Managed identity, Key Vault secret storage, and policy-as-code baselines for integration services.
- Documentation and knowledge base updates guiding repository structure, pipelines, and service-specific best practices.

Task Breakdown
--------------

Task 1 – Service Bus Module & Policies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Goal**: Provide hardened Service Bus namespace generator aligned with Azure Verified Module guidance.
- **Steps**
  1. ✅ Create `backend/generators/azure_servicebus_namespace.tf.j2` wrapping `terraform-azurerm-avm-res-servicebus-namespace` features (topics, diagnostics, private endpoints).
  2. ✅ Add pydantic payload model covering SKU, CMK, identity assignments, diagnostic sinks.
  3. ✅ Register generator in `backend/generators/registry.py` with example payload and metadata.
  4. ✅ Implement policy checks for diagnostics, CMK, private endpoints, RBAC (`backend/policies/azure_servicebus.py`) and wire into scanner.
  5. ✅ Add regression coverage in `tests/test_generators_registry.py` and `tests/test_policies_rules.py` for the new generator and rules.
  6. ✅ Generate pipeline docs (`docs/generators/azure_servicebus-namespace.md`) and mirror to the knowledge base; link to how-to article below.
  7. ✅ Add optional preset subscriptions/queues in generator metadata, surface presets in the generator UI, and mirror documentation in `docs/generators/azure_servicebus-namespace.md`.

Task 2 – Azure Functions Baseline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Goal**: Deliver Function App + App Service Plan generator with secure defaults.
- **Steps**
  1. ✅ Produce generator template leveraging Azure Function App best practices, including storage, Application Insights, and managed identity.
  2. ✅ Define pydantic payload to capture runtime stack, VNet integration, and diagnostics toggles.
  3. ✅ Register the generator and surface presets via metadata; UI updated to consume metadata-driven defaults.
  4. 🔄 Review need for additional policy checks (FTP disablement, HTTPS enforcement) aligned with new template outputs.
  5. ✅ Extend tests covering generator rendering and policy detections.
  6. ✅ Publish docs (`docs/generators/azure_function_app.md`) mirrored to `knowledge/generated/` for quick reference.

Task 3 – API Management Generator & Security Gates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Goal**: Ship premium-ready API Management generator with VNet integration.
- **Steps**
  1. ✅ Introduce API Management template supporting Premium SKU, optional zones, VNet integration, and diagnostics.
  2. ✅ Create payload model for publisher details, identity, custom properties, and networking controls.
  3. ✅ Register generator with metadata (presets) and hook UI for form-based authoring (bundle support TBD).
  4. 🔄 Evaluate additional policy coverage for TLS minimums and managed identities based on rendered output.
  5. ✅ Generate docs (`docs/generators/azure_api_management.md`) and knowledge mirrors; registry tests cover rendering.

Task 4 – Azure DevOps Pipeline Suite
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Goal**: Provide reusable YAML pipelines and Terraform automation scaffolding.
- **Steps**
  1. Draft `pipelines/terraform-ci.yml` covering lint (fmt), validate, plan, tfsec, checkov, infracost stages with environment matrix.
  2. Add examples for repo splitting (infra-modules vs. env-config) and pipeline variable grouping in docs.
  3. Author automation script or template to provision Azure DevOps project, agent queue, and pipeline permissions via Terraform Azure DevOps provider.
  4. Update CLI/docs to reference new pipeline assets and required environment variables.

Task 5 – Naming, Tags, and Blueprint Enhancements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Goal**: Standardize naming/tag strategy and improve multi-environment output.
- **Steps**
  1. Integrate Azure CAF naming module into generator payload defaults; expose prefix/suffix controls.
  2. Extend blueprints to emit `naming.tf` helper blocks and shared tag locals.
  3. Add policy validations ensuring mandatory tags (Environment, Owner, CostCenter) across resources.
  4. Update knowledge base with naming and tagging conventions.

Task 6 – RBAC, Secrets, and Policy-as-Code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Goal**: Embed managed identities and compliance policies across integration services.
- **Steps**
  1. Add helper library for managed identity role assignments (Key Vault, Service Bus, Storage).
  2. Create policy rules verifying MI usage vs. client secrets, Key Vault secret storage for app settings, and Azure Policy assignments (`policy_definition_id`s).
  3. Provide sample Sentinel/OPA rules or Azure Policy assignments in docs for Policy-as-Code.
  4. Build tests ensuring RBAC guidance matches new generators.

Task 7 – Documentation & Knowledge Refresh
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Goal**: Align docs/UI with new capabilities.
- **Steps**
  1. Update `docs/terraform_config_enhancement_plan.md` with integration service milestones.
  2. Produce walkthroughs for Service Bus, Functions, APIM, and pipeline setup.
  3. Add knowledge articles for each service plus Azure DevOps workflow, then reindex via `python -m backend.cli reindex`.
  4. Surface new metadata within frontend wizard (routes `(app)/generate` and `(app)/knowledge`).

Task 8 – Release Integration & QA
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Goal**: Ensure end-to-end validation before rollout.
- **Steps**
  1. Add CI jobs running generator rendering + policy tests + pipeline lint (YAML validation).
  2. Provide manual verification checklist (terraform plan/apply in dev subscription using new templates).
  3. Update CHANGELOG/PLAN/README with feature availability and reindex instructions.
  4. Coordinate release communications outlining new integration-service coverage and pipeline assets.
