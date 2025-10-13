<script lang="ts">
    import { browser } from '$app/environment';
    import {
        generateAwsS3,
        generateAzureServiceBus,
        generateAzureStorageAccount,
        generateAzureFunctionApp,
        generateAzureApiManagement,
        updateProjectRun,
        type AwsS3GeneratorPayload,
        type AzureServiceBusGeneratorPayload,
        type AzureStorageGeneratorPayload,
        type AzureFunctionAppGeneratorPayload,
        type AzureApiManagementGeneratorPayload,
        type GeneratorResult,
        type ProjectRunUpdatePayload,
        type ProjectSummary
    } from '$lib/api/client';
    import { notifyError, notifySuccess } from '$lib/stores/notifications';
    import type { SubmitFunction } from '@sveltejs/kit';
    import { onDestroy } from 'svelte';
    import AwsS3Form from '$lib/components/generate/AwsS3Form.svelte';
    import AzureStorageForm from '$lib/components/generate/AzureStorageForm.svelte';
    import AzureServiceBusForm from '$lib/components/generate/AzureServiceBusForm.svelte';
    import AzureFunctionAppForm from '$lib/components/generate/AzureFunctionAppForm.svelte';
    import AzureApiManagementForm from '$lib/components/generate/AzureApiManagementForm.svelte';
    import type { GeneratorFormStyles } from '$lib/components/generate/types';
    import type { ServiceBusPreset } from '$lib/components/generate/models';
    import { token as authTokenStore } from '$lib/stores/auth';
    import { activeProject, projectState } from '$lib/stores/project';
    import type { PageData } from './$types';

    const { data } = $props<{ data: PageData }>();

    type GeneratorId =
        | 'aws_s3'
        | 'azure_storage'
        | 'azure_servicebus'
        | 'azure_function_app'
        | 'azure_api_management';

    type GeneratorMetadata = {
        slug: string;
        example_payload?: Record<string, any>;
        presets?: Array<{ id?: string; label?: string; description?: string; payload?: Record<string, any> }>;
    };

    const metadataBySlug: Record<string, GeneratorMetadata> = Object.fromEntries(
        (data.metadata as GeneratorMetadata[]).map((item) => [item.slug, item])
    );

    type WizardStepId = 'select' | 'configure' | 'review';

    const wizardSteps: Array<{ id: WizardStepId; label: string; description: string }> = [
        {
            id: 'select',
            label: 'Select blueprint',
            description: 'Choose the Terraform module template to start from.'
        },
        {
            id: 'configure',
            label: 'Configure inputs',
            description: 'Provide environment specifics, policies, and networking details.'
        },
        {
            id: 'review',
            label: 'Review & generate',
            description: 'Verify inputs and download or copy the rendered Terraform.'
        }
    ];

    const inputClass =
        'w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200';
    const textareaClass =
        'w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200';
    const checkboxClass = 'flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600';
    const checkboxInputClass = 'h-4 w-4 rounded border-slate-300 text-sky-500 focus:ring-sky-200';
    const statusClass = 'rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-600';
    const actionClass =
        'inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-300/50 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60';
    const spinnerClass = 'h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent';
    const resultClass = 'space-y-3 rounded-3xl border border-slate-200 bg-slate-50 p-5';
    const resultHeaderClass = 'flex items-center justify-between gap-3';
    const resultTitleClass = 'text-sm font-semibold text-slate-700';
    const resultActionsClass = 'flex gap-2';
    const resultButtonClass =
        'rounded-xl border border-sky-200 px-3 py-1 text-xs font-semibold text-sky-600 transition hover:bg-sky-500 hover:text-white';
    const resultContentClass = 'max-h-96 overflow-auto rounded-2xl bg-slate-50 p-4 text-xs text-slate-600';
    const placeholderClass = 'rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-5 text-sm text-slate-500';
    const stepperDotClass =
        'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-semibold transition';
    const secondaryButtonClass =
        'inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-sky-300 hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200';

    const formStyles: GeneratorFormStyles = {
        input: inputClass,
        textarea: textareaClass,
        checkboxWrapper: checkboxClass,
        checkboxInput: checkboxInputClass,
        status: statusClass,
        primaryAction: actionClass,
        spinner: spinnerClass,
        resultContainer: resultClass,
        resultHeader: resultHeaderClass,
        resultTitle: resultTitleClass,
        resultActions: resultActionsClass,
        resultButton: resultButtonClass,
        resultContent: resultContentClass,
        placeholder: placeholderClass
    };

    const parseList = (value: string): string[] =>
        value
            .split(/\r?\n|,/)
            .map((entry) => entry.trim())
            .filter(Boolean);

    const parseKeyValuePairs = (value: string): Record<string, string> => {
        const result: Record<string, string> = {};
        for (const line of value.split(/\r?\n/)) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            const [key, ...rest] = trimmed.split('=');
            if (key && rest.length) {
                result[key.trim()] = rest.join('=').trim();
            }
        }
        return result;
    };

    const s3Example = metadataBySlug['aws/s3-secure-bucket']?.example_payload ?? {};
    const storageExample = metadataBySlug['azure/storage-secure-account']?.example_payload ?? {};
    const serviceBusMetadata = metadataBySlug['azure/servicebus-namespace'];
    const serviceBusExample = serviceBusMetadata?.example_payload ?? {};
    const functionMetadata = metadataBySlug['azure/function-app'];
    const functionExample = functionMetadata?.example_payload ?? {};
    const apimMetadata = metadataBySlug['azure/api-management'];
    const apimExample = apimMetadata?.example_payload ?? {};

    const metadataServiceBusPresets = (serviceBusMetadata?.presets ?? []).map((preset, index) => {
        const payload = preset.payload ?? {};
        const queues = Array.isArray(payload.queues)
            ? payload.queues.map((queue: any) => queue.name).join('\n')
            : '';
        const topics = Array.isArray(payload.topics)
            ? payload.topics.map((topic: any) => topic.name).join('\n')
            : '';
        return {
            id: preset.id ?? `preset-${index}`,
            label: preset.label ?? `Preset ${index + 1}`,
            description: preset.description ?? '',
            payload,
            queues,
            topics
        };
    });

    const serviceBusPresets: ServiceBusPreset[] = [
        {
            id: 'custom',
            label: 'Custom from scratch',
            description: 'Define queues and topics manually.',
            payload: null,
            queues: '',
            topics: ''
        },
        ...metadataServiceBusPresets
    ];

    const generators: Array<{ id: GeneratorId; label: string; description: string }> = [
        {
            id: 'aws_s3',
            label: 'AWS S3 Baseline',
            description: 'Hardened S3 bucket with encryption, public access block, and optional TLS-only policy.'
        },
        {
            id: 'azure_storage',
            label: 'Azure Storage Account',
            description: 'Secure Storage Account with HTTPS-only access, optional network restrictions, and private endpoint.'
        },
        {
            id: 'azure_servicebus',
            label: 'Azure Service Bus Namespace',
            description: 'Messaging namespace with queues/topics, managed identities, diagnostics, and preset scaffolding.'
        },
        {
            id: 'azure_function_app',
            label: 'Azure Function App',
            description: 'Linux Function App with managed identity, Application Insights, and optional VNet integration.'
        },
        {
            id: 'azure_api_management',
            label: 'Azure API Management',
            description: 'API Management gateway with managed identity, diagnostics, and optional private networking.'
        }
    ];

    const generatorLabels: Record<GeneratorId, string> = {
        aws_s3: 'AWS S3 Generator',
        azure_storage: 'Azure Storage Generator',
        azure_servicebus: 'Azure Service Bus Generator',
        azure_function_app: 'Azure Function App Generator',
        azure_api_management: 'Azure API Management Generator'
    };

    let activeStep = $state<WizardStepId>('select');
    let activeGenerator = $state<GeneratorId>('aws_s3');
    let activeProjectValue = $state<ProjectSummary | null>(null);
    let authTokenValue = $state<string | null>(null);
    let missingProjectWarningShown = $state(false);
    let unsubscribeProject: (() => void) | null = null;
    let unsubscribeToken: (() => void) | null = null;

    if (browser) {
        unsubscribeProject = activeProject.subscribe((value) => {
            activeProjectValue = value;
            if (value) {
                missingProjectWarningShown = false;
            }
        });
        unsubscribeToken = authTokenStore.subscribe((value) => {
            authTokenValue = value;
        });
    }

    onDestroy(() => {
        unsubscribeProject?.();
        unsubscribeToken?.();
    });

    const setActiveGenerator = (id: GeneratorId) => {
        if (activeGenerator !== id) {
            activeGenerator = id;
        }
    };

    const moveToConfigure = () => {
        activeStep = 'configure';
    };

    const moveToReview = () => {
        activeStep = 'review';
    };

    const resetToSelection = () => {
        activeStep = 'select';
    };

    const stepState = (stepId: WizardStepId): 'complete' | 'current' | 'upcoming' => {
        const currentIndex = wizardSteps.findIndex((step) => step.id === activeStep);
        const targetIndex = wizardSteps.findIndex((step) => step.id === stepId);
        if (targetIndex < currentIndex) {
            return 'complete';
        }
        if (targetIndex === currentIndex) {
            return 'current';
        }
        return 'upcoming';
    };

    const getResultForGenerator = (id: GeneratorId): GeneratorResult | null => {
        switch (id) {
            case 'aws_s3':
                return awsResult;
            case 'azure_storage':
                return azureResult;
            case 'azure_servicebus':
                return sbResult;
            case 'azure_function_app':
                return funcResult;
            case 'azure_api_management':
                return apimResult;
            default:
                return null;
        }
    };

    const getStatusSetterForGenerator = (id: GeneratorId): ((value: string | null) => void) => {
        switch (id) {
            case 'aws_s3':
                return (value) => (awsStatus = value);
            case 'azure_storage':
                return (value) => (azureStatus = value);
            case 'azure_servicebus':
                return (value) => (sbStatus = value);
            case 'azure_function_app':
                return (value) => (funcStatus = value);
            case 'azure_api_management':
                return (value) => (apimStatus = value);
            default:
                return () => undefined;
        }
    };

    const createEnhanceHandler = (handler: (event?: SubmitEvent) => Promise<void>): SubmitFunction => {
        return ({ cancel }) => {
            cancel();
            void handler();
        };
    };

    const formatBoolean = (value: boolean, trueLabel = 'Enabled', falseLabel = 'Disabled') =>
        value ? trueLabel : falseLabel;

    const getSummaryForGenerator = (id: GeneratorId): Array<{ label: string; value: string }> => {
        switch (id) {
            case 'aws_s3':
                return [
                    { label: 'Bucket', value: awsBucketName },
                    { label: 'Region', value: awsRegion },
                    { label: 'Environment', value: awsEnvironment },
                    { label: 'Remote state', value: awsIncludeBackend ? `${awsBackendBucket}/${awsBackendKey}` : 'Disabled' },
                    { label: 'Versioning', value: formatBoolean(awsVersioning) },
                    { label: 'TLS enforcement', value: formatBoolean(awsEnforceSecureTransport, 'Enforced', 'Not enforced') }
                ];
            case 'azure_storage':
                return [
                    { label: 'Storage account', value: azureSaName },
                    { label: 'Location', value: azureLocation },
                    { label: 'Environment', value: azureEnvironment },
                    { label: 'Replication', value: azureReplication },
                    { label: 'Network access', value: azureRestrictNetwork ? 'Restricted' : 'Public allowed' },
                    { label: 'Private endpoint', value: formatBoolean(azureIncludePrivateEndpoint, 'Provisioned', 'Not provisioned') }
                ];
            case 'azure_servicebus':
                return [
                    { label: 'Namespace', value: sbNamespace },
                    { label: 'Location', value: sbLocation },
                    { label: 'SKU', value: sbSku },
                    { label: 'Queues', value: `${parseList(sbQueueNames).length} configured` },
                    { label: 'Topics', value: `${parseList(sbTopicNames).length} configured` },
                    { label: 'Private endpoint', value: formatBoolean(sbPrivateEndpointEnabled, 'Enabled', 'Disabled') }
                ];
            case 'azure_function_app':
                return [
                    { label: 'Function App', value: funcAppName },
                    { label: 'Runtime', value: `${funcRuntime} ${funcRuntimeVersion}` },
                    { label: 'Plan SKU', value: funcSku },
                    { label: 'Application Insights', value: formatBoolean(funcEnableInsights) },
                    { label: 'VNet integration', value: formatBoolean(funcEnableVnet, 'Attached', 'Not attached') }
                ];
            case 'azure_api_management':
                return [
                    { label: 'API Management', value: apimName },
                    { label: 'Location', value: apimLocation },
                    { label: 'SKU', value: apimSku },
                    { label: 'Capacity', value: apimCapacity || 'Default (1)' },
                    { label: 'Virtual network', value: apimVnetType },
                    { label: 'Diagnostics', value: formatBoolean(apimDiagnosticsEnabled) }
                ];
            default:
                return [];
        }
    };

    // AWS S3 state
    let awsBucketName = $state(s3Example.bucket_name ?? 'my-secure-logs-bucket');
    let awsRegion = $state(s3Example.region ?? 'us-east-1');
    let awsEnvironment = $state(s3Example.environment ?? 'prod');
    let awsOwnerTag = $state(s3Example.owner_tag ?? 'platform-team');
    let awsCostCenterTag = $state(s3Example.cost_center_tag ?? 'ENG-SRE');
    let awsForceDestroy = $state(Boolean(s3Example.force_destroy ?? false));
    let awsVersioning = $state(Boolean(s3Example.versioning ?? true));
    let awsEnforceSecureTransport = $state(Boolean(s3Example.enforce_secure_transport ?? true));
    let awsKmsKeyId = $state(s3Example.kms_key_id ?? '');
    let awsIncludeBackend = $state(false);
    let awsBackendBucket = $state('terraform-state-bucket');
    let awsBackendKey = $state('s3/baseline/terraform.tfstate');
    let awsBackendRegion = $state('us-east-1');
    let awsBackendTable = $state('terraform_locks');
    let awsResult = $state<GeneratorResult | null>(null);
    let awsStatus = $state<string | null>(null);
    let awsBusy = $state(false);

    // Azure storage state
    let azureRgName = $state(storageExample.resource_group_name ?? 'rg-app');
    let azureSaName = $state(storageExample.storage_account_name ?? 'stapp1234567890');
    let azureLocation = $state(storageExample.location ?? 'eastus');
    let azureEnvironment = $state(storageExample.environment ?? 'prod');
    let azureReplication = $state(storageExample.replication ?? 'LRS');
    let azureVersioning = $state(Boolean(storageExample.versioning ?? true));
    let azureOwnerTag = $state(storageExample.owner_tag ?? 'platform-team');
    let azureCostCenterTag = $state(storageExample.cost_center_tag ?? 'ENG-SRE');
    let azureRestrictNetwork = $state(Boolean(storageExample.restrict_network ?? true));
    let azureAllowedIps = $state('10.0.0.0/24');
    let azureIncludeBackend = $state(false);
    let azureBackendRg = $state('rg-tfstate');
    let azureBackendAccount = $state('sttfstate123456');
    let azureBackendContainer = $state('tfstate');
    let azureBackendKey = $state('prod/storage/terraform.tfstate');
    let azureIncludePrivateEndpoint = $state(false);
    let azurePrivateEndpointName = $state('storage-pe');
    let azurePrivateEndpointConnection = $state('storage-blob');
    let azurePrivateEndpointSubnet = $state('/subscriptions/.../subnets/private-endpoint');
    let azurePrivateDnsZoneId = $state('/subscriptions/.../privateDnsZones/privatelink.blob.core.windows.net');
    let azurePrivateDnsZoneGroup = $state('storage-blob-zone');
    let azureResult = $state<GeneratorResult | null>(null);
    let azureStatus = $state<string | null>(null);
    let azureBusy = $state(false);

    // Service Bus state
    const serviceBusExampleQueues = Array.isArray(serviceBusExample.queues)
        ? serviceBusExample.queues.map((queue: any) => queue.name).join('\n')
        : 'orders';
    const serviceBusExampleTopics = Array.isArray(serviceBusExample.topics)
        ? serviceBusExample.topics.map((topic: any) => topic.name).join('\n')
        : 'events';

    let sbPresetId = $state<ServiceBusPreset['id']>('custom');
    let sbRgName = $state(serviceBusExample.resource_group_name ?? 'rg-integration');
    let sbNamespace = $state(serviceBusExample.namespace_name ?? 'sb-platform-prod');
    let sbLocation = $state(serviceBusExample.location ?? 'eastus2');
    let sbEnvironment = $state(serviceBusExample.environment ?? 'prod');
    let sbSku = $state(serviceBusExample.sku ?? 'Premium');
    let sbCapacity = $state(serviceBusExample.capacity ? String(serviceBusExample.capacity) : '');
    let sbZoneRedundant = $state(Boolean(serviceBusExample.zone_redundant ?? true));
    let sbOwnerTag = $state(serviceBusExample.owner_tag ?? 'platform-team');
    let sbCostCenterTag = $state(serviceBusExample.cost_center_tag ?? 'ENG-SRE');
    let sbRestrictNetwork = $state(Boolean(serviceBusExample.restrict_network ?? true));
    let sbPrivateEndpointEnabled = $state(true);
    let sbPrivateEndpointName = $state('sb-namespace-pe');
    let sbPrivateEndpointSubnet = $state('/subscriptions/.../subnets/private-endpoint');
    let sbPrivateEndpointZones = $state('/subscriptions/.../privateDnsZones/privatelink.servicebus.windows.net');
    let sbDiagnosticsEnabled = $state(true);
    let sbDiagnosticsWorkspaceId = $state('/subscriptions/.../Microsoft.OperationalInsights/workspaces/log-analytics');
    let sbDiagnosticsLogCategories = $state('OperationalLogs');
    let sbDiagnosticsMetricCategories = $state('AllMetrics');
    let sbCmkEnabled = $state(false);
    let sbCmkKeyId = $state('');
    let sbCmkIdentityId = $state('');
    let sbQueueNames = $state(serviceBusExampleQueues);
    let sbTopicNames = $state(serviceBusExampleTopics);
    let sbBackendEnabled = $state(false);
    let sbBackendRg = $state('rg-tfstate');
    let sbBackendAccount = $state('sttfstate123456');
    let sbBackendContainer = $state('tfstate');
    let sbBackendKey = $state('prod/servicebus/terraform.tfstate');
    let sbResult = $state<GeneratorResult | null>(null);
    let sbStatus = $state<string | null>(null);
    let sbBusy = $state(false);

    // Azure Function App state
    let funcRgName = $state(functionExample.resource_group_name ?? 'rg-functions');
    let funcAppName = $state(functionExample.function_app_name ?? 'func-app-prod');
    let funcStorageName = $state(functionExample.storage_account_name ?? 'stfuncprod');
    let funcPlanName = $state(functionExample.app_service_plan_name ?? 'plan-func-prod');
    let funcLocation = $state(functionExample.location ?? 'eastus2');
    let funcEnvironment = $state(functionExample.environment ?? 'prod');
    let funcRuntime = $state(functionExample.runtime ?? 'dotnet');
    let funcRuntimeVersion = $state(functionExample.runtime_version ?? '8');
    let funcSku = $state(functionExample.app_service_plan_sku ?? 'EP1');
    let funcStorageReplication = $state(functionExample.storage_replication ?? 'LRS');
    let funcEnableVnet = $state(Boolean(functionExample.enable_vnet_integration ?? false));
    let funcSubnetId = $state(functionExample.vnet_subnet_id ?? '');
    let funcEnableInsights = $state(Boolean(functionExample.enable_application_insights ?? true));
    let funcInsightsName = $state(functionExample.application_insights_name ?? 'func-prod-ai');
    let funcDiagnosticsEnabled = $state(Boolean(functionExample.diagnostics ? true : false));
    let funcDiagnosticsWorkspaceId = $state(functionExample.diagnostics?.workspace_resource_id ?? '');
    let funcDiagnosticsLogCategories = $state(
        (functionExample.diagnostics?.log_categories ?? ['FunctionAppLogs']).join('\n')
    );
    let funcDiagnosticsMetricCategories = $state(
        (functionExample.diagnostics?.metric_categories ?? ['AllMetrics']).join('\n')
    );
    let funcOwnerTag = $state(functionExample.owner_tag ?? 'platform-team');
    let funcCostCenterTag = $state(functionExample.cost_center_tag ?? 'ENG-SRE');
    let funcResult = $state<GeneratorResult | null>(null);
    let funcStatus = $state<string | null>(null);
    let funcBusy = $state(false);

    // Azure API Management state
    let apimRgName = $state(apimExample.resource_group_name ?? 'rg-apim');
    let apimName = $state(apimExample.name ?? 'apim-platform-prod');
    let apimLocation = $state(apimExample.location ?? 'eastus2');
    let apimEnvironment = $state(apimExample.environment ?? 'prod');
    let apimPublisherName = $state(apimExample.publisher_name ?? 'Platform Team');
    let apimPublisherEmail = $state(apimExample.publisher_email ?? 'platform@example.com');
    let apimSku = $state(apimExample.sku_name ?? 'Premium_1');
    let apimCapacity = $state(apimExample.capacity ? String(apimExample.capacity) : '');
    let apimZones = $state(Array.isArray(apimExample.zones) ? apimExample.zones.join('\n') : '');
    let apimVnetType = $state(apimExample.virtual_network_type ?? 'None');
    let apimSubnetId = $state(apimExample.subnet_id ?? '');
    let apimIdentityType = $state(apimExample.identity_type ?? 'SystemAssigned');
    let apimCustomProperties = $state(
        apimExample.custom_properties
            ? Object.entries(apimExample.custom_properties)
                  .map(([key, value]) => `${key}=${value}`)
                  .join('\n')
            : ''
    );
    let apimDiagnosticsEnabled = $state(Boolean(apimExample.diagnostics ? true : false));
    let apimDiagnosticsWorkspaceId = $state(apimExample.diagnostics?.workspace_resource_id ?? '');
    let apimDiagnosticsLogCategories = $state(
        (apimExample.diagnostics?.log_categories ?? ['GatewayLogs']).join('\n')
    );
    let apimDiagnosticsMetricCategories = $state(
        (apimExample.diagnostics?.metric_categories ?? ['AllMetrics']).join('\n')
    );
    let apimOwnerTag = $state(apimExample.owner_tag ?? 'platform-team');
    let apimCostCenterTag = $state(apimExample.cost_center_tag ?? 'ENG-SRE');
    let apimResult = $state<GeneratorResult | null>(null);
    let apimStatus = $state<string | null>(null);
    let apimBusy = $state(false);

    const buildAwsPayload = (): AwsS3GeneratorPayload => ({
        bucket_name: awsBucketName,
        region: awsRegion,
        environment: awsEnvironment,
        owner_tag: awsOwnerTag,
        cost_center_tag: awsCostCenterTag,
        force_destroy: awsForceDestroy,
        versioning: awsVersioning,
        enforce_secure_transport: awsEnforceSecureTransport,
        kms_key_id: awsKmsKeyId || null,
        backend: awsIncludeBackend
            ? {
                  bucket: awsBackendBucket,
                  key: awsBackendKey,
                  region: awsBackendRegion,
                  dynamodb_table: awsBackendTable
              }
            : null
    });

    const buildAzureStoragePayload = (): AzureStorageGeneratorPayload => ({
        resource_group_name: azureRgName,
        storage_account_name: azureSaName,
        location: azureLocation,
        environment: azureEnvironment,
        replication: azureReplication,
        versioning: azureVersioning,
        owner_tag: azureOwnerTag,
        cost_center_tag: azureCostCenterTag,
        restrict_network: azureRestrictNetwork,
        allowed_ips: parseList(azureAllowedIps),
        backend: azureIncludeBackend
            ? {
                  resource_group: azureBackendRg,
                  storage_account: azureBackendAccount,
                  container: azureBackendContainer,
                  key: azureBackendKey
              }
            : null,
        private_endpoint: azureIncludePrivateEndpoint
            ? {
                  name: azurePrivateEndpointName,
                  connection_name: azurePrivateEndpointConnection,
                  subnet_id: azurePrivateEndpointSubnet,
                  private_dns_zone_id: azurePrivateDnsZoneId || null,
                  dns_zone_group_name: azurePrivateDnsZoneGroup || null
              }
            : null
    });

    const buildServiceBusPayload = (): AzureServiceBusGeneratorPayload => {
        const queues = parseList(sbQueueNames).map((name) => ({
            name,
            enable_partitioning: true,
            lock_duration: 'PT1M',
            max_delivery_count: 10,
            requires_duplicate_detection: true,
            duplicate_detection_history_time_window: 'PT10M'
        }));

        const topics = parseList(sbTopicNames).map((name) => ({
            name,
            enable_partitioning: true,
            default_message_ttl: 'P7D',
            requires_duplicate_detection: false,
            duplicate_detection_history_time_window: 'PT10M',
            subscriptions: []
        }));

        const capacityValue = sbCapacity.trim();

        return {
            resource_group_name: sbRgName,
            namespace_name: sbNamespace,
            location: sbLocation,
            environment: sbEnvironment,
            sku: sbSku,
            capacity: capacityValue ? Number(capacityValue) : null,
            zone_redundant: sbZoneRedundant,
            owner_tag: sbOwnerTag,
            cost_center_tag: sbCostCenterTag,
            restrict_network: sbRestrictNetwork,
            queues,
            topics,
            private_endpoint: sbPrivateEndpointEnabled
                ? {
                      name: sbPrivateEndpointName,
                      subnet_id: sbPrivateEndpointSubnet,
                      group_ids: ['namespace'],
                      private_dns_zone_ids: parseList(sbPrivateEndpointZones)
                  }
                : null,
            diagnostics: sbDiagnosticsEnabled
                ? {
                      workspace_resource_id: sbDiagnosticsWorkspaceId,
                      log_categories: parseList(sbDiagnosticsLogCategories),
                      metric_categories: parseList(sbDiagnosticsMetricCategories)
                  }
                : null,
            customer_managed_key: sbCmkEnabled
                ? {
                      key_vault_key_id: sbCmkKeyId,
                      user_assigned_identity_id: sbCmkIdentityId.trim() || null
                  }
                : null,
            backend: sbBackendEnabled
                ? {
                      resource_group: sbBackendRg,
                      storage_account: sbBackendAccount,
                      container: sbBackendContainer,
                      key: sbBackendKey
                  }
                : null
        };
    };

    const buildFunctionPayload = (): AzureFunctionAppGeneratorPayload => ({
        resource_group_name: funcRgName,
        function_app_name: funcAppName,
        storage_account_name: funcStorageName,
        app_service_plan_name: funcPlanName,
        location: funcLocation,
        environment: funcEnvironment,
        runtime: funcRuntime,
        runtime_version: funcRuntimeVersion,
        app_service_plan_sku: funcSku,
        storage_replication: funcStorageReplication,
        enable_vnet_integration: funcEnableVnet,
        vnet_subnet_id: funcEnableVnet ? funcSubnetId : null,
        enable_application_insights: funcEnableInsights,
        application_insights_name: funcInsightsName,
        diagnostics: funcDiagnosticsEnabled
            ? {
                  workspace_resource_id: funcDiagnosticsWorkspaceId,
                  log_categories: parseList(funcDiagnosticsLogCategories),
                  metric_categories: parseList(funcDiagnosticsMetricCategories)
              }
            : null,
        owner_tag: funcOwnerTag,
        cost_center_tag: funcCostCenterTag
    });

    const buildApiManagementPayload = (): AzureApiManagementGeneratorPayload => ({
        resource_group_name: apimRgName,
        name: apimName,
        location: apimLocation,
        environment: apimEnvironment,
        publisher_name: apimPublisherName,
        publisher_email: apimPublisherEmail,
        sku_name: apimSku,
        capacity: apimCapacity.trim() ? Number(apimCapacity.trim()) : null,
        zones: parseList(apimZones),
        virtual_network_type: apimVnetType,
        subnet_id: apimVnetType !== 'None' ? apimSubnetId : null,
        identity_type: apimIdentityType as AzureApiManagementGeneratorPayload['identity_type'],
        custom_properties: parseKeyValuePairs(apimCustomProperties),
        diagnostics: apimDiagnosticsEnabled
            ? {
                  workspace_resource_id: apimDiagnosticsWorkspaceId,
                  log_categories: parseList(apimDiagnosticsLogCategories),
                  metric_categories: parseList(apimDiagnosticsMetricCategories)
              }
            : null,
        owner_tag: apimOwnerTag,
        cost_center_tag: apimCostCenterTag
    });

    const applyServiceBusPreset = (presetId: string) => {
        const preset = serviceBusPresets.find((item) => item.id === presetId);
        if (!preset) return;
        sbPresetId = presetId;
        if (preset.queues !== undefined) {
            sbQueueNames = preset.queues;
        }
        if (preset.topics !== undefined) {
            sbTopicNames = preset.topics;
        }
        if (preset.payload) {
            if (preset.payload.sku) {
                sbSku = preset.payload.sku;
            }
            if (preset.payload.restrict_network !== undefined) {
                sbRestrictNetwork = Boolean(preset.payload.restrict_network);
            }
            if (preset.payload.zone_redundant !== undefined) {
                sbZoneRedundant = Boolean(preset.payload.zone_redundant);
            }
        }
        if (presetId !== 'custom') {
            sbStatus = `Preset "${preset.label}" applied.`;
            notifySuccess(sbStatus, { duration: 2500 });
        }
    };

    const summariseAwsInputs = (payload: AwsS3GeneratorPayload) => ({
        bucket_name: payload.bucket_name,
        region: payload.region,
        environment: payload.environment,
        versioning: payload.versioning,
        secure_transport: payload.enforce_secure_transport,
        backend_enabled: Boolean(payload.backend)
    });

    const summariseAzureStorageInputs = (payload: AzureStorageGeneratorPayload) => ({
        storage_account: payload.storage_account_name,
        location: payload.location,
        environment: payload.environment,
        restrict_network: payload.restrict_network,
        private_endpoint: Boolean(payload.private_endpoint),
        backend_enabled: Boolean(payload.backend)
    });

    const summariseServiceBusInputs = (payload: AzureServiceBusGeneratorPayload) => ({
        namespace: payload.namespace_name,
        location: payload.location,
        sku: payload.sku,
        queues: payload.queues?.length ?? 0,
        topics: payload.topics?.length ?? 0,
        restrict_network: payload.restrict_network,
        private_endpoint: Boolean(payload.private_endpoint),
        diagnostics: Boolean(payload.diagnostics)
    });

    const summariseFunctionInputs = (payload: AzureFunctionAppGeneratorPayload) => ({
        function_app: payload.function_app_name,
        runtime: `${payload.runtime} ${payload.runtime_version}`,
        plan_sku: payload.app_service_plan_sku,
        application_insights: payload.enable_application_insights,
        vnet_integration: payload.enable_vnet_integration
    });

    const summariseApiManagementInputs = (payload: AzureApiManagementGeneratorPayload) => ({
        name: payload.name,
        location: payload.location,
        environment: payload.environment,
        sku: payload.sku_name,
        capacity: payload.capacity ?? 1,
        virtual_network: payload.virtual_network_type,
        diagnostics: Boolean(payload.diagnostics)
    });

    const buildRunSummary = (result: GeneratorResult | null): Record<string, unknown> | null => {
        if (!result) return null;
        return {
            filename: result.filename,
            content_length: result.content.length
        };
    };

    const recordGeneratorRun = async (
        generatorId: GeneratorId,
        inputs: Record<string, unknown>,
        result: GeneratorResult | null
    ) => {
        if (!browser) {
            return;
        }
        if (!activeProjectValue) {
            if (!missingProjectWarningShown) {
                notifyError('Select a project in the sidebar to log generator runs.');
                missingProjectWarningShown = true;
            }
            return;
        }
        if (!authTokenValue) {
            console.warn('Skipping project run logging because token is unavailable.');
            return;
        }

        const label = `${generatorLabels[generatorId] ?? generatorId} • ${new Date().toLocaleString()}`;
        try {
            const run = await projectState.createRun(fetch, authTokenValue, activeProjectValue.id, {
                label,
                kind: 'generator',
                parameters: {
                    generator: generatorId,
                    inputs
                }
            });
            if (!run?.id) {
                return;
            }
            const summary = buildRunSummary(result);
            const updatePayload: ProjectRunUpdatePayload = {
                status: 'completed',
                finished_at: new Date().toISOString()
            };
            if (summary) {
                updatePayload.summary = summary;
            }
            try {
                const updated = await updateProjectRun(
                    fetch,
                    authTokenValue,
                    activeProjectValue.id,
                    run.id,
                    updatePayload
                );
                projectState.upsertRun(activeProjectValue.id, updated);
            } catch (updateError) {
                console.warn('Failed to update generator run status', updateError);
            }
        } catch (error) {
            console.warn('Unable to record generator run', error);
        }
    };

    const handleAwsSubmit = async (event?: SubmitEvent) => {
        event?.preventDefault();
        awsStatus = null;
        awsResult = null;
        if (!awsBucketName.trim()) {
            awsStatus = 'Bucket name is required.';
            notifyError(awsStatus);
            return;
        }
        if (
            awsIncludeBackend &&
            (!awsBackendBucket.trim() || !awsBackendKey.trim() || !awsBackendRegion.trim() || !awsBackendTable.trim())
        ) {
            awsStatus = 'Provide backend bucket, key, region, and DynamoDB table.';
            notifyError(awsStatus);
            return;
        }
        awsBusy = true;
        try {
            const payload = buildAwsPayload();
            awsResult = await generateAwsS3(fetch, payload);
            awsStatus = 'Terraform module generated successfully.';
            notifySuccess(awsStatus);
            moveToReview();
            void recordGeneratorRun('aws_s3', summariseAwsInputs(payload), awsResult);
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to generate AWS S3 module.';
            awsStatus = message;
            notifyError(message);
        } finally {
            awsBusy = false;
        }
    };

    const handleAzureStorageSubmit = async (event?: SubmitEvent) => {
        event?.preventDefault();
        azureStatus = null;
        azureResult = null;
        if (!azureRgName.trim() || !azureSaName.trim()) {
            azureStatus = 'Resource group and storage account names are required.';
            notifyError(azureStatus);
            return;
        }
        if (
            azureIncludeBackend &&
            (!azureBackendRg.trim() || !azureBackendAccount.trim() || !azureBackendContainer.trim() || !azureBackendKey.trim())
        ) {
            azureStatus = 'Provide resource group, storage account, container, and key for remote state.';
            notifyError(azureStatus);
            return;
        }
        if (azureRestrictNetwork && !azureAllowedIps.trim()) {
            azureStatus = 'Specify at least one CIDR range when network restrictions are enabled.';
            notifyError(azureStatus);
            return;
        }
        if (azureIncludePrivateEndpoint && (!azurePrivateEndpointName.trim() || !azurePrivateEndpointSubnet.trim())) {
            azureStatus = 'Private endpoint name and subnet ID are required when enabled.';
            notifyError(azureStatus);
            return;
        }
        azureBusy = true;
        try {
            const payload = buildAzureStoragePayload();
            azureResult = await generateAzureStorageAccount(fetch, payload);
            azureStatus = 'Terraform module generated successfully.';
            notifySuccess(azureStatus);
            moveToReview();
            void recordGeneratorRun('azure_storage', summariseAzureStorageInputs(payload), azureResult);
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to generate Azure storage module.';
            azureStatus = message;
            notifyError(message);
        } finally {
            azureBusy = false;
        }
    };

    const handleServiceBusSubmit = async (event?: SubmitEvent) => {
        event?.preventDefault();
        sbStatus = null;
        sbResult = null;
        if (!sbRgName.trim() || !sbNamespace.trim()) {
            sbStatus = 'Resource group and namespace names are required.';
            notifyError(sbStatus);
            return;
        }
        if (sbCapacity.trim() && Number.isNaN(Number(sbCapacity.trim()))) {
            sbStatus = 'Capacity must be a number.';
            notifyError(sbStatus);
            return;
        }
        if (sbPrivateEndpointEnabled && (!sbPrivateEndpointName.trim() || !sbPrivateEndpointSubnet.trim())) {
            sbStatus = 'Private endpoint name and subnet ID are required when enabled.';
            notifyError(sbStatus);
            return;
        }
        if (sbDiagnosticsEnabled && !sbDiagnosticsWorkspaceId.trim()) {
            sbStatus = 'Log Analytics workspace ID is required when diagnostics are enabled.';
            notifyError(sbStatus);
            return;
        }
        if (sbCmkEnabled && !sbCmkKeyId.trim()) {
            sbStatus = 'Provide the Key Vault key ID when customer-managed keys are enabled.';
            notifyError(sbStatus);
            return;
        }
        if (
            sbBackendEnabled &&
            (!sbBackendRg.trim() || !sbBackendAccount.trim() || !sbBackendContainer.trim() || !sbBackendKey.trim())
        ) {
            sbStatus = 'Provide resource group, storage account, container, and key for remote state.';
            notifyError(sbStatus);
            return;
        }
        sbBusy = true;
        try {
            const payload = buildServiceBusPayload();
            sbResult = await generateAzureServiceBus(fetch, payload);
            sbStatus = 'Terraform module generated successfully.';
            notifySuccess(sbStatus);
            moveToReview();
            void recordGeneratorRun('azure_servicebus', summariseServiceBusInputs(payload), sbResult);
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to generate Service Bus module.';
            sbStatus = message;
            notifyError(message);
        } finally {
            sbBusy = false;
        }
    };

    const handleFunctionSubmit = async (event?: SubmitEvent) => {
        event?.preventDefault();
        funcStatus = null;
        funcResult = null;
        if (!funcRgName.trim() || !funcAppName.trim() || !funcStorageName.trim() || !funcPlanName.trim()) {
            funcStatus = 'Resource group, Function App, storage account, and plan names are required.';
            notifyError(funcStatus);
            return;
        }
        if (funcEnableVnet && !funcSubnetId.trim()) {
            funcStatus = 'Provide subnet ID when VNet integration is enabled.';
            notifyError(funcStatus);
            return;
        }
        if (funcDiagnosticsEnabled && !funcDiagnosticsWorkspaceId.trim()) {
            funcStatus = 'Log Analytics workspace ID is required when diagnostics are enabled.';
            notifyError(funcStatus);
            return;
        }
        funcBusy = true;
        try {
            const payload = buildFunctionPayload();
            funcResult = await generateAzureFunctionApp(fetch, payload);
            funcStatus = 'Terraform module generated successfully.';
            notifySuccess(funcStatus);
            moveToReview();
            void recordGeneratorRun('azure_function_app', summariseFunctionInputs(payload), funcResult);
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to generate Function App module.';
            funcStatus = message;
            notifyError(message);
        } finally {
            funcBusy = false;
        }
    };

    const handleApimSubmit = async (event?: SubmitEvent) => {
        event?.preventDefault();
        apimStatus = null;
        apimResult = null;
        if (!apimRgName.trim() || !apimName.trim() || !apimPublisherName.trim() || !apimPublisherEmail.trim()) {
            apimStatus = 'Resource group, service name, publisher name, and publisher email are required.';
            notifyError(apimStatus);
            return;
        }
        if (apimVnetType !== 'None' && !apimSubnetId.trim()) {
            apimStatus = 'Subnet ID is required when virtual network integration is enabled.';
            notifyError(apimStatus);
            return;
        }
        if (apimDiagnosticsEnabled && !apimDiagnosticsWorkspaceId.trim()) {
            apimStatus = 'Log Analytics workspace ID is required when diagnostics are enabled.';
            notifyError(apimStatus);
            return;
        }
        if (apimCapacity.trim() && Number.isNaN(Number(apimCapacity.trim()))) {
            apimStatus = 'Capacity must be a number when provided.';
            notifyError(apimStatus);
            return;
        }
        apimBusy = true;
        try {
            const payload = buildApiManagementPayload();
            apimResult = await generateAzureApiManagement(fetch, payload);
            apimStatus = 'Terraform module generated successfully.';
            notifySuccess(apimStatus);
            moveToReview();
            void recordGeneratorRun('azure_api_management', summariseApiManagementInputs(payload), apimResult);
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to generate API Management module.';
            apimStatus = message;
            notifyError(message);
        } finally {
            apimBusy = false;
        }
    };

    const copyResult = async (result: GeneratorResult | null, setStatus: (value: string | null) => void) => {
        if (!result) return;
        try {
            await navigator.clipboard.writeText(result.content);
            setStatus('Copied to clipboard.');
            notifySuccess('Copied to clipboard.', { duration: 3000 });
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Unable to copy to clipboard.';
            setStatus(message);
            notifyError(message);
        }
    };

    const downloadResult = (result: GeneratorResult | null) => {
        if (!result) return;
        const blob = new Blob([result.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = result.filename;
        link.click();
        URL.revokeObjectURL(url);
    };

    const awsEnhance = createEnhanceHandler(handleAwsSubmit);
    const azureStorageEnhance = createEnhanceHandler(handleAzureStorageSubmit);
    const serviceBusEnhance = createEnhanceHandler(handleServiceBusSubmit);
    const functionEnhance = createEnhanceHandler(handleFunctionSubmit);
    const apimEnhance = createEnhanceHandler(handleApimSubmit);
</script>
<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Blueprint Studio</p>
        <h2 class="text-3xl font-semibold text-slate-700">Generate hardened Terraform modules</h2>
        <p class="max-w-3xl text-sm text-slate-500">
            Select a generator and tailor the inputs to your environment. Generated Terraform can be copied directly into your
            codebase or downloaded as a `.tf` file.
        </p>
    </header>

    <ol class="grid gap-3 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm shadow-slate-300/20" aria-label="Terraform generation steps">
        {#each wizardSteps as step, index}
            {@const state = stepState(step.id)}
            <li class="flex items-start gap-3">
                <span
                    class={`${stepperDotClass} ${
                        state === 'current'
                            ? 'border-sky-500 bg-sky-500 text-white'
                            : state === 'complete'
                            ? 'border-sky-500 bg-sky-50 text-sky-600'
                            : 'border-slate-200 bg-white text-slate-400'
                    }`}
                >
                    {index + 1}
                </span>
                <div class="space-y-1">
                    <p class="text-sm font-semibold text-slate-600">{step.label}</p>
                    <p class="text-xs text-slate-500">{step.description}</p>
                </div>
            </li>
        {/each}
    </ol>

    {#if activeStep === 'select'}
        <section class="space-y-6 rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-6">
            <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {#each generators as option}
                    <button
                        type="button"
                        class={`flex h-full flex-col justify-between rounded-2xl border p-4 text-left transition ${
                            activeGenerator === option.id
                                ? 'border-sky-400 bg-white text-slate-700 shadow-sm shadow-sky-200/60'
                                : 'border-transparent bg-white text-slate-600 hover:border-sky-200 hover:text-slate-700'
                        }`}
                        aria-pressed={activeGenerator === option.id}
                        onclick={() => setActiveGenerator(option.id)}
                    >
                        <span class="text-base font-semibold">{option.label}</span>
                        <span class="mt-3 text-sm text-slate-500">{option.description}</span>
                    </button>
                {/each}
            </div>
            <div class="flex flex-wrap items-center justify-between gap-3">
                <p class="text-xs text-slate-500">Pick a blueprint to continue. You can adjust inputs or switch later.</p>
                <button class={actionClass} type="button" onclick={moveToConfigure}>
                    Configure blueprint
                </button>
            </div>
        </section>
    {:else if activeStep === 'configure'}
        <div class="flex flex-wrap items-center justify-between gap-3">
            <nav class="flex flex-wrap gap-3">
                {#each generators as option}
                    <button
                        class={`rounded-2xl border px-4 py-2 text-sm font-semibold transition ${
                            activeGenerator === option.id
                                ? 'border-sky-400 bg-white text-sky-600 shadow-md shadow-sky-200/60'
                                : 'border-slate-200 bg-slate-50 text-slate-500 hover:border-sky-300 hover:text-sky-600'
                        }`}
                        type="button"
                        onclick={() => setActiveGenerator(option.id)}
                    >
                        {option.label}
                    </button>
                {/each}
            </nav>
            <button class={secondaryButtonClass} type="button" onclick={resetToSelection}>
                Back to blueprint list
            </button>
        </div>

        <p class="text-xs text-slate-500">{generators.find((g) => g.id === activeGenerator)?.description}</p>

        {#if activeGenerator === 'aws_s3'}
            <AwsS3Form
                styles={formStyles}
                bind:bucketName={awsBucketName}
                bind:region={awsRegion}
                bind:environment={awsEnvironment}
                bind:ownerTag={awsOwnerTag}
                bind:costCenterTag={awsCostCenterTag}
                bind:kmsKeyId={awsKmsKeyId}
                bind:forceDestroy={awsForceDestroy}
                bind:versioning={awsVersioning}
                bind:enforceSecureTransport={awsEnforceSecureTransport}
                bind:includeBackend={awsIncludeBackend}
                bind:backendBucket={awsBackendBucket}
                bind:backendKey={awsBackendKey}
                bind:backendRegion={awsBackendRegion}
                bind:backendTable={awsBackendTable}
                status={awsStatus}
                busy={awsBusy}
                result={awsResult}
                onSubmit={handleAwsSubmit}
                onCopy={() => copyResult(awsResult, (value) => (awsStatus = value))}
                onDownload={() => downloadResult(awsResult)}
                enhanceAction={awsEnhance}
            />
        {:else if activeGenerator === 'azure_storage'}
            <AzureStorageForm
                styles={formStyles}
                bind:resourceGroupName={azureRgName}
                bind:accountName={azureSaName}
                bind:location={azureLocation}
                bind:environment={azureEnvironment}
                bind:replication={azureReplication}
                bind:ownerTag={azureOwnerTag}
                bind:costCenterTag={azureCostCenterTag}
                bind:enableVersioning={azureVersioning}
                bind:restrictNetwork={azureRestrictNetwork}
                bind:includeBackend={azureIncludeBackend}
                bind:includePrivateEndpoint={azureIncludePrivateEndpoint}
                bind:allowedIps={azureAllowedIps}
                bind:backendResourceGroup={azureBackendRg}
                bind:backendAccount={azureBackendAccount}
                bind:backendContainer={azureBackendContainer}
                bind:backendKey={azureBackendKey}
                bind:privateEndpointName={azurePrivateEndpointName}
                bind:privateEndpointConnection={azurePrivateEndpointConnection}
                bind:privateEndpointSubnet={azurePrivateEndpointSubnet}
                bind:privateDnsZoneId={azurePrivateDnsZoneId}
                bind:privateDnsZoneGroup={azurePrivateDnsZoneGroup}
                status={azureStatus}
                busy={azureBusy}
                result={azureResult}
                onSubmit={handleAzureStorageSubmit}
                onCopy={() => copyResult(azureResult, (value) => (azureStatus = value))}
                onDownload={() => downloadResult(azureResult)}
                enhanceAction={azureStorageEnhance}
            />
        {:else if activeGenerator === 'azure_servicebus'}
            <AzureServiceBusForm
                styles={formStyles}
                presets={serviceBusPresets}
                bind:presetId={sbPresetId}
                bind:resourceGroupName={sbRgName}
                bind:namespaceName={sbNamespace}
                bind:location={sbLocation}
                bind:environment={sbEnvironment}
                bind:sku={sbSku}
                bind:capacity={sbCapacity}
                bind:zoneRedundant={sbZoneRedundant}
                bind:ownerTag={sbOwnerTag}
                bind:costCenterTag={sbCostCenterTag}
                bind:restrictNetwork={sbRestrictNetwork}
                bind:privateEndpointEnabled={sbPrivateEndpointEnabled}
                bind:privateEndpointName={sbPrivateEndpointName}
                bind:privateEndpointSubnet={sbPrivateEndpointSubnet}
                bind:privateEndpointZones={sbPrivateEndpointZones}
                bind:diagnosticsEnabled={sbDiagnosticsEnabled}
                bind:diagnosticsWorkspaceId={sbDiagnosticsWorkspaceId}
                bind:diagnosticsLogCategories={sbDiagnosticsLogCategories}
                bind:diagnosticsMetricCategories={sbDiagnosticsMetricCategories}
                bind:cmkEnabled={sbCmkEnabled}
                bind:cmkKeyId={sbCmkKeyId}
                bind:cmkIdentityId={sbCmkIdentityId}
                bind:queueNames={sbQueueNames}
                bind:topicNames={sbTopicNames}
                bind:backendEnabled={sbBackendEnabled}
                bind:backendResourceGroup={sbBackendRg}
                bind:backendAccount={sbBackendAccount}
                bind:backendContainer={sbBackendContainer}
                bind:backendKey={sbBackendKey}
                status={sbStatus}
                busy={sbBusy}
                result={sbResult}
                onSubmit={handleServiceBusSubmit}
                onCopy={() => copyResult(sbResult, (value) => (sbStatus = value))}
                onDownload={() => downloadResult(sbResult)}
                applyPreset={applyServiceBusPreset}
                enhanceAction={serviceBusEnhance}
            />
        {:else if activeGenerator === 'azure_function_app'}
            <AzureFunctionAppForm
                styles={formStyles}
                bind:resourceGroupName={funcRgName}
                bind:functionAppName={funcAppName}
                bind:storageAccountName={funcStorageName}
                bind:appServicePlanName={funcPlanName}
                bind:location={funcLocation}
                bind:environment={funcEnvironment}
                bind:runtime={funcRuntime}
                bind:runtimeVersion={funcRuntimeVersion}
                bind:appServicePlanSku={funcSku}
                bind:storageReplication={funcStorageReplication}
                bind:enableVnetIntegration={funcEnableVnet}
                bind:subnetId={funcSubnetId}
                bind:enableInsights={funcEnableInsights}
                bind:insightsName={funcInsightsName}
                bind:diagnosticsEnabled={funcDiagnosticsEnabled}
                bind:diagnosticsWorkspaceId={funcDiagnosticsWorkspaceId}
                bind:diagnosticsLogCategories={funcDiagnosticsLogCategories}
                bind:diagnosticsMetricCategories={funcDiagnosticsMetricCategories}
                bind:ownerTag={funcOwnerTag}
                bind:costCenterTag={funcCostCenterTag}
                status={funcStatus}
                busy={funcBusy}
                result={funcResult}
                onSubmit={handleFunctionSubmit}
                onCopy={() => copyResult(funcResult, (value) => (funcStatus = value))}
                onDownload={() => downloadResult(funcResult)}
                enhanceAction={functionEnhance}
            />
        {:else if activeGenerator === 'azure_api_management'}
            <AzureApiManagementForm
                styles={formStyles}
                bind:resourceGroupName={apimRgName}
                bind:serviceName={apimName}
                bind:location={apimLocation}
                bind:environment={apimEnvironment}
                bind:publisherName={apimPublisherName}
                bind:publisherEmail={apimPublisherEmail}
                bind:sku={apimSku}
                bind:capacity={apimCapacity}
                bind:zones={apimZones}
                bind:vnetType={apimVnetType}
                bind:subnetId={apimSubnetId}
                bind:identityType={apimIdentityType}
                bind:customProperties={apimCustomProperties}
                bind:diagnosticsEnabled={apimDiagnosticsEnabled}
                bind:diagnosticsWorkspaceId={apimDiagnosticsWorkspaceId}
                bind:diagnosticsLogCategories={apimDiagnosticsLogCategories}
                bind:diagnosticsMetricCategories={apimDiagnosticsMetricCategories}
                bind:ownerTag={apimOwnerTag}
                bind:costCenterTag={apimCostCenterTag}
                status={apimStatus}
                busy={apimBusy}
                result={apimResult}
                onSubmit={handleApimSubmit}
                onCopy={() => copyResult(apimResult, (value) => (apimStatus = value))}
                onDownload={() => downloadResult(apimResult)}
                enhanceAction={apimEnhance}
            />
        {/if}
{:else}
    {@const activeResult = getResultForGenerator(activeGenerator)}
    <section class="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
        <header class="space-y-2">
            <p class="text-xs font-semibold uppercase tracking-[0.35em] text-sky-500">Review</p>
            <h3 class="text-xl font-semibold text-slate-700">Verify and export Terraform</h3>
            <p class="text-sm text-slate-500">
                Confirm the generated Terraform before copying or downloading. Jump back to the previous step to adjust inputs or
                pick a different blueprint.
            </p>
        </header>

        <div class="flex flex-wrap items-center gap-2">
            <button class={secondaryButtonClass} type="button" onclick={moveToConfigure}>
                Back to inputs
            </button>
            <button class={secondaryButtonClass} type="button" onclick={resetToSelection}>
                Choose another blueprint
            </button>
        </div>

        {#if activeResult}
            {@const summaryItems = getSummaryForGenerator(activeGenerator)}
            <div class={resultClass}>
                <header class={resultHeaderClass}>
                    <div>
                        <p class={resultTitleClass}>{activeResult.filename}</p>
                        <p class="text-xs text-slate-500">
                            {generators.find((g) => g.id === activeGenerator)?.label}
                        </p>
                    </div>
                    <div class={resultActionsClass}>
                        <button
                            class={resultButtonClass}
                            type="button"
                            onclick={() => copyResult(activeResult, getStatusSetterForGenerator(activeGenerator))}
                        >
                            Copy
                        </button>
                        <button class={resultButtonClass} type="button" onclick={() => downloadResult(activeResult)}>
                            Download
                        </button>
                    </div>
                </header>
                {#if summaryItems.length}
                    <div class="grid gap-3 rounded-2xl bg-slate-50 p-4 sm:grid-cols-2">
                        {#each summaryItems as item}
                            <div>
                                <p class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">{item.label}</p>
                                <p class="text-sm text-slate-600">{item.value}</p>
                            </div>
                        {/each}
                    </div>
                {/if}
                <pre class={resultContentClass}>{activeResult.content}</pre>
            </div>
        {:else}
            <div class={placeholderClass}>
                Generate the Terraform module from the configuration step to review the rendered code here.
            </div>
        {/if}
    </section>
{/if}
</section>
