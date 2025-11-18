<script lang="ts">
    import { browser } from '$app/environment';
    import { goto } from '$app/navigation';
    import { page } from '$app/stores';
    import {
        ApiError,
        generateAwsS3,
        generateAzureApiManagement,
        generateAzureFunctionApp,
        generateAzureServiceBus,
        generateAzureStorageAccount,
        runProjectGenerator,
        type AwsS3GeneratorPayload,
        type AzureServiceBusGeneratorPayload,
        type AzureStorageGeneratorPayload,
        type AzureFunctionAppGeneratorPayload,
        type AzureApiManagementGeneratorPayload,
        type GeneratedAssetSummary,
        type GeneratedAssetVersionSummary,
        type GeneratorResult,
        type ProjectRunSummary,
        type ProjectSummary
    } from '$lib/api/client';
    import { notifyError, notifySuccess } from '$lib/stores/notifications';
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
    import ProjectWorkspaceBanner from '$lib/components/projects/ProjectWorkspaceBanner.svelte';
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
        example_payload?: Record<string, unknown>;
        presets?: Array<{ id?: string; label?: string; description?: string; payload?: Record<string, unknown> }>;
    };

    type GeneratorOverrideState = {
        generatorId: GeneratorId;
        summary: Record<string, unknown> | null;
        message: string | null;
        assetName?: string | null;
        metadata?: Record<string, unknown> | null;
    };

    type GeneratorRunContext = {
        asset: GeneratedAssetSummary;
        version: GeneratedAssetVersionSummary;
        run: ProjectRunSummary;
        projectId: string;
        projectSlug: string | null;
    };

    const metadataBySlug: Record<string, GeneratorMetadata> = Object.fromEntries(
        (data.metadata as GeneratorMetadata[]).map((item) => [item.slug, item])
    );

    type WizardStepId = 'select' | 'configure' | 'destination' | 'review';

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
            id: 'destination',
            label: 'Destination',
            description: 'Choose the workspace, naming, and auto-save preferences for the generated bundle.'
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

    const parseTagsInput = (value: string): string[] =>
        value
            .split(',')
            .map((entry) => entry.trim())
            .filter(Boolean);

    const projectSlugParam = $derived($page.params.projectSlug ?? null);

    let autoSaveEnabled = $state(true);
    let destinationAssetName = $state('');
    let destinationAssetDescription = $state('');
    let destinationAssetTags = $state('');
    let destinationSaving = $state(false);
    let destinationError = $state<string | null>(null);

    const emptyGeneratorContexts: Record<GeneratorId, GeneratorRunContext | null> = {
        aws_s3: null,
        azure_storage: null,
        azure_servicebus: null,
        azure_function_app: null,
        azure_api_management: null
    };
    let generatorContexts = $state<Record<GeneratorId, GeneratorRunContext | null>>({
        ...emptyGeneratorContexts
    });

    const s3Example =
        (metadataBySlug['aws/s3-secure-bucket']?.example_payload ?? {}) as Partial<AwsS3GeneratorPayload>;
    const storageExample =
        (metadataBySlug['azure/storage-secure-account']?.example_payload ?? {}) as Partial<AzureStorageGeneratorPayload>;
    const serviceBusMetadata = metadataBySlug['azure/servicebus-namespace'];
    const serviceBusExample =
        (serviceBusMetadata?.example_payload ?? {}) as Partial<AzureServiceBusGeneratorPayload>;
    const functionMetadata = metadataBySlug['azure/function-app'];
    const functionExample =
        (functionMetadata?.example_payload ?? {}) as Partial<AzureFunctionAppGeneratorPayload>;
    const apimMetadata = metadataBySlug['azure/api-management'];
    const apimExample =
        (apimMetadata?.example_payload ?? {}) as Partial<AzureApiManagementGeneratorPayload>;

	const stringifyNamedEntries = (items: unknown): string =>
		Array.isArray(items)
			? items
					.map((entry) => {
						if (entry && typeof entry === 'object' && 'name' in entry) {
							const value = (entry as { name?: unknown }).name;
							return typeof value === 'string' ? value : '';
						}
						return '';
					})
					.filter(Boolean)
					.join('\n')
			: '';

    const metadataServiceBusPresets = (serviceBusMetadata?.presets ?? []).map((preset, index) => {
        const payload = (preset.payload ?? {}) as Partial<AzureServiceBusGeneratorPayload>;
        const queues = stringifyNamedEntries(payload.queues);
        const topics = stringifyNamedEntries(payload.topics);
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
    let projectOptions = $state<ProjectSummary[]>([]);
    let unsubscribeProject: (() => void) | null = null;
    let unsubscribeToken: (() => void) | null = null;
    let unsubscribeProjectState: (() => void) | null = null;

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
        unsubscribeProjectState = projectState.subscribe((state) => {
            projectOptions = state.projects;
        });
    }

    onDestroy(() => {
        unsubscribeProject?.();
        unsubscribeToken?.();
        unsubscribeProjectState?.();
    });

    const setActiveGenerator = (id: GeneratorId) => {
        if (activeGenerator !== id) {
            activeGenerator = id;
        }
    };

    const moveToConfigure = () => {
        activeStep = 'configure';
    };

    const moveToDestination = () => {
        activeStep = 'destination';
    };

    const moveToReview = () => {
        activeStep = 'review';
    };

    const resetToSelection = () => {
        activeStep = 'select';
    };

    const updateActiveProject = (projectId: string) => {
        projectState.setActiveProject(projectId || null);
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

    const recordGeneratorContext = (
        generatorId: GeneratorId,
        payload: { asset: GeneratedAssetSummary; version: GeneratedAssetVersionSummary; run: ProjectRunSummary; project: ProjectSummary }
    ) => {
        generatorContexts = {
            ...generatorContexts,
            [generatorId]: {
                asset: payload.asset,
                version: payload.version,
                run: payload.run,
                projectId: payload.project.id,
                projectSlug: payload.project.slug ?? null
            }
        };
    };

    const clearGeneratorContext = (generatorId: GeneratorId) => {
        generatorContexts = {
            ...generatorContexts,
            [generatorId]: null
        };
    };

    const resolveGeneratorOptions = (runLabel: string, forceSave: boolean) => {
        const tags = parseTagsInput(destinationAssetTags);
        return {
            run_label: runLabel,
            force_save: forceSave,
            asset_name: destinationAssetName.trim() || undefined,
            description: destinationAssetDescription.trim() || undefined,
            tags
        };
    };

    const formatBoolean = (value: boolean, trueLabel = 'Enabled', falseLabel = 'Disabled') =>
        value ? trueLabel : falseLabel;

    const summaryValue = (value: unknown): string => {
        if (typeof value === 'string') return value;
        if (typeof value === 'number' || typeof value === 'boolean') return String(value);
        if (value == null) return '';
        return String(value);
    };

    const getSummaryForGenerator = (id: GeneratorId): Array<{ label: string; value: string }> => {
        switch (id) {
            case 'aws_s3':
                return [
                    { label: 'Bucket', value: summaryValue(awsBucketName) },
                    { label: 'Region', value: summaryValue(awsRegion) },
                    { label: 'Environment', value: summaryValue(awsEnvironment) },
                    {
                        label: 'Remote state',
                        value: summaryValue(awsIncludeBackend ? `${awsBackendBucket}/${awsBackendKey}` : 'Disabled')
                    },
                    { label: 'Versioning', value: formatBoolean(awsVersioning) },
                    { label: 'TLS enforcement', value: formatBoolean(awsEnforceSecureTransport, 'Enforced', 'Not enforced') }
                ];
            case 'azure_storage':
                return [
                    { label: 'Storage account', value: summaryValue(azureSaName) },
                    { label: 'Location', value: summaryValue(azureLocation) },
                    { label: 'Environment', value: summaryValue(azureEnvironment) },
                    { label: 'Replication', value: summaryValue(azureReplication) },
                    { label: 'Network access', value: azureRestrictNetwork ? 'Restricted' : 'Public allowed' },
                    { label: 'Private endpoint', value: formatBoolean(azureIncludePrivateEndpoint, 'Provisioned', 'Not provisioned') }
                ];
            case 'azure_servicebus':
                return [
                    { label: 'Namespace', value: summaryValue(sbNamespace) },
                    { label: 'Location', value: summaryValue(sbLocation) },
                    { label: 'SKU', value: summaryValue(sbSku) },
                    { label: 'Queues', value: `${parseList(sbQueueNames).length} configured` },
                    { label: 'Topics', value: `${parseList(sbTopicNames).length} configured` },
                    { label: 'Private endpoint', value: formatBoolean(sbPrivateEndpointEnabled, 'Enabled', 'Disabled') }
                ];
            case 'azure_function_app':
                return [
                    { label: 'Function App', value: summaryValue(funcAppName) },
                    { label: 'Runtime', value: `${funcRuntime} ${funcRuntimeVersion}` },
                    { label: 'Plan SKU', value: summaryValue(funcSku) },
                    { label: 'Application Insights', value: formatBoolean(funcEnableInsights) },
                    { label: 'VNet integration', value: formatBoolean(funcEnableVnet, 'Attached', 'Not attached') }
                ];
            case 'azure_api_management':
                return [
                    { label: 'API Management', value: summaryValue(apimName) },
                    { label: 'Location', value: summaryValue(apimLocation) },
                    { label: 'SKU', value: summaryValue(apimSku) },
                    { label: 'Capacity', value: summaryValue(apimCapacity || 'Default (1)') },
                    { label: 'Virtual network', value: summaryValue(apimVnetType) },
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
let generatorOverride = $state<GeneratorOverrideState | null>(null);
let destinationContextKey: string | null = null;

    $effect(() => {
        const context = generatorContexts[activeGenerator];
        const key = context ? `${activeGenerator}:${context.version.id}` : `${activeGenerator}:none`;
        if (destinationContextKey === key) {
            return;
        }
        destinationContextKey = key;
        if (context) {
            destinationAssetName = context.asset.name ?? '';
            destinationAssetDescription = context.asset.description ?? '';
            destinationAssetTags = (context.asset.tags ?? []).join(', ');
        } else {
            destinationAssetName = '';
            destinationAssetDescription = '';
            destinationAssetTags = '';
        }
    });

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
	const serviceBusExampleQueues = stringifyNamedEntries(serviceBusExample.queues) || 'orders';
	const serviceBusExampleTopics = stringifyNamedEntries(serviceBusExample.topics) || 'events';

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
            const payload = preset.payload as Partial<AzureServiceBusGeneratorPayload>;
            if (payload.sku) {
                sbSku = payload.sku;
            }
            if (payload.restrict_network !== undefined) {
                sbRestrictNetwork = Boolean(payload.restrict_network);
            }
            if (payload.zone_redundant !== undefined) {
                sbZoneRedundant = Boolean(payload.zone_redundant);
            }
        }
        if (presetId !== 'custom') {
            sbStatus = `Preset "${preset.label}" applied.`;
            notifySuccess(sbStatus, { duration: 2500 });
        }
    };

    const handleAwsSubmit = async (event?: SubmitEvent, opts?: { force?: boolean }) => {
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
        const forceSave = opts?.force ?? false;
        const shouldAutoSave = autoSaveEnabled || forceSave;
        try {
            const payload = buildAwsPayload();
            const context = requireProjectContext();
            if (!context) {
                awsBusy = false;
                return;
            }
            if (!shouldAutoSave) {
                const response = await generateAwsS3(fetch, payload);
                generatorOverride = null;
                awsResult = response;
                awsStatus = 'Terraform module generated (auto-save disabled).';
                notifySuccess(awsStatus);
                clearGeneratorContext('aws_s3');
                moveToReview();
                return;
            }
            const response = await runProjectGenerator(fetch, context.token, context.project.id, 'aws/s3-secure-bucket', {
                payload: payload as unknown as Record<string, unknown>,
                options: resolveGeneratorOptions(`${generatorLabels.aws_s3} • ${new Date().toLocaleString()}`, forceSave)
            });
            generatorOverride = null;
            awsResult = response.output;
            recordGeneratorContext('aws_s3', {
                asset: response.asset,
                version: response.version,
                run: response.run,
                project: context.project
            });
            const validationStatus = validationStatusLabel(response.version.validation_summary ?? null);
            if (validationStatus === 'failed') {
                const details = validationMessage(response.version.validation_summary ?? null);
                awsStatus = 'Terraform validation failed.';
                notifyError(details ?? 'Terraform validation failed in the API. Adjust inputs or run locally for details.');
                generatorOverride = {
                    generatorId: 'aws_s3',
                    summary: response.version.validation_summary ?? null,
                    message: details ?? 'Terraform validation failed.',
                    assetName: payload.bucket_name,
                    metadata: {
                        generator: 'aws_s3-secure-bucket',
                        payload
                    }
                };
                return;
            }
            awsStatus =
                validationStatus === 'warn'
                    ? 'Terraform module generated with warnings. Review validation output.'
                    : `Terraform module generated (validation ${validationStatus}).`;
            notifySuccess(awsStatus);
            moveToDestination();
            projectState.upsertRun(context.project.id, response.run);
        } catch (error) {
            if (handleGeneratorValidationError('aws_s3', error)) {
                awsStatus = 'Terraform validation failed.';
                return;
            }
            const message = error instanceof Error ? error.message : 'Failed to generate AWS S3 module.';
            awsStatus = message;
            notifyError(message);
        } finally {
            awsBusy = false;
        }
    };

    const handleAzureStorageSubmit = async (event?: SubmitEvent, opts?: { force?: boolean }) => {
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
        const forceSave = opts?.force ?? false;
        const shouldAutoSave = autoSaveEnabled || forceSave;
        try {
            const payload = buildAzureStoragePayload();
            const context = requireProjectContext();
            if (!context) {
                azureBusy = false;
                return;
            }
            if (!shouldAutoSave) {
                const response = await generateAzureStorageAccount(fetch, payload);
                generatorOverride = null;
                azureResult = response;
                azureStatus = 'Terraform module generated (auto-save disabled).';
                notifySuccess(azureStatus);
                clearGeneratorContext('azure_storage');
                moveToReview();
                return;
            }
            const response = await runProjectGenerator(fetch, context.token, context.project.id, 'azure/storage-secure-account', {
                payload: payload as unknown as Record<string, unknown>,
                options: resolveGeneratorOptions(`${generatorLabels.azure_storage} • ${new Date().toLocaleString()}`, forceSave)
            });
            generatorOverride = null;
            azureResult = response.output;
            recordGeneratorContext('azure_storage', {
                asset: response.asset,
                version: response.version,
                run: response.run,
                project: context.project
            });
            const validationStatus = validationStatusLabel(response.version.validation_summary ?? null);
            if (validationStatus === 'failed') {
                const details = validationMessage(response.version.validation_summary ?? null);
                azureStatus = 'Terraform validation failed.';
                notifyError(details ?? 'Terraform validation failed in the API. Adjust inputs or run locally for details.');
                generatorOverride = {
                    generatorId: 'azure_storage',
                    summary: response.version.validation_summary ?? null,
                    message: details ?? 'Terraform validation failed.',
                    assetName: payload.storage_account_name,
                    metadata: {
                        generator: 'azure/storage-secure-account',
                        payload
                    }
                };
                return;
            }
            azureStatus =
                validationStatus === 'warn'
                    ? 'Terraform module generated with warnings. Review validation output.'
                    : `Terraform module generated (validation ${validationStatus}).`;
            notifySuccess(azureStatus);
            moveToDestination();
            projectState.upsertRun(context.project.id, response.run);
        } catch (error) {
            if (handleGeneratorValidationError('azure_storage', error)) {
                azureStatus = 'Terraform validation failed.';
                return;
            }
            const message = error instanceof Error ? error.message : 'Failed to generate Azure storage module.';
            azureStatus = message;
            notifyError(message);
        } finally {
            azureBusy = false;
        }
    };

    const handleServiceBusSubmit = async (event?: SubmitEvent, opts?: { force?: boolean }) => {
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
        const forceSave = opts?.force ?? false;
        const shouldAutoSave = autoSaveEnabled || forceSave;
        try {
            const payload = buildServiceBusPayload();
            const context = requireProjectContext();
            if (!context) {
                sbBusy = false;
                return;
            }
            if (!shouldAutoSave) {
                const response = await generateAzureServiceBus(fetch, payload);
                generatorOverride = null;
                sbResult = response;
                sbStatus = 'Terraform module generated (auto-save disabled).';
                notifySuccess(sbStatus);
                clearGeneratorContext('azure_servicebus');
                moveToReview();
                return;
            }
            const response = await runProjectGenerator(fetch, context.token, context.project.id, 'azure/servicebus-namespace', {
                payload: payload as unknown as Record<string, unknown>,
                options: resolveGeneratorOptions(`${generatorLabels.azure_servicebus} • ${new Date().toLocaleString()}`, forceSave)
            });
            generatorOverride = null;
            sbResult = response.output;
            recordGeneratorContext('azure_servicebus', {
                asset: response.asset,
                version: response.version,
                run: response.run,
                project: context.project
            });
            const validationStatus = validationStatusLabel(response.version.validation_summary ?? null);
            if (validationStatus === 'failed') {
                const details = validationMessage(response.version.validation_summary ?? null);
                sbStatus = 'Terraform validation failed.';
                notifyError(details ?? 'Terraform validation failed in the API. Adjust inputs or run locally for details.');
                generatorOverride = {
                    generatorId: 'azure_servicebus',
                    summary: response.version.validation_summary ?? null,
                    message: details ?? 'Terraform validation failed.',
                    assetName: payload.namespace_name,
                    metadata: {
                        generator: 'azure/servicebus-namespace',
                        payload
                    }
                };
                return;
            }
            sbStatus =
                validationStatus === 'warn'
                    ? 'Terraform module generated with warnings. Review validation output.'
                    : `Terraform module generated (validation ${validationStatus}).`;
            notifySuccess(sbStatus);
            moveToDestination();
            projectState.upsertRun(context.project.id, response.run);
        } catch (error) {
            if (handleGeneratorValidationError('azure_servicebus', error)) {
                sbStatus = 'Terraform validation failed.';
                return;
            }
            const message = error instanceof Error ? error.message : 'Failed to generate Service Bus module.';
            sbStatus = message;
            notifyError(message);
        } finally {
            sbBusy = false;
        }
    };

    const handleFunctionSubmit = async (event?: SubmitEvent, opts?: { force?: boolean }) => {
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
        const forceSave = opts?.force ?? false;
        const shouldAutoSave = autoSaveEnabled || forceSave;
        try {
            const payload = buildFunctionPayload();
            const context = requireProjectContext();
            if (!context) {
                funcBusy = false;
                return;
            }
            if (!shouldAutoSave) {
                const response = await generateAzureFunctionApp(fetch, payload);
                generatorOverride = null;
                funcResult = response;
                funcStatus = 'Terraform module generated (auto-save disabled).';
                notifySuccess(funcStatus);
                clearGeneratorContext('azure_function_app');
                moveToReview();
                return;
            }
            const response = await runProjectGenerator(fetch, context.token, context.project.id, 'azure/function-app', {
                payload: payload as unknown as Record<string, unknown>,
                options: resolveGeneratorOptions(`${generatorLabels.azure_function_app} • ${new Date().toLocaleString()}`, forceSave)
            });
            generatorOverride = null;
            funcResult = response.output;
            recordGeneratorContext('azure_function_app', {
                asset: response.asset,
                version: response.version,
                run: response.run,
                project: context.project
            });
            const validationStatus = validationStatusLabel(response.version.validation_summary ?? null);
            if (validationStatus === 'failed') {
                const details = validationMessage(response.version.validation_summary ?? null);
                funcStatus = 'Terraform validation failed.';
                notifyError(details ?? 'Terraform validation failed in the API. Adjust inputs or run locally for details.');
                generatorOverride = {
                    generatorId: 'azure_function_app',
                    summary: response.version.validation_summary ?? null,
                    message: details ?? 'Terraform validation failed.',
                    assetName: payload.function_app_name,
                    metadata: {
                        generator: 'azure/function-app',
                        payload
                    }
                };
                return;
            }
            funcStatus =
                validationStatus === 'warn'
                    ? 'Terraform module generated with warnings. Review validation output.'
                    : `Terraform module generated (validation ${validationStatus}).`;
            notifySuccess(funcStatus);
            moveToDestination();
            projectState.upsertRun(context.project.id, response.run);
        } catch (error) {
            if (handleGeneratorValidationError('azure_function_app', error)) {
                funcStatus = 'Terraform validation failed.';
                return;
            }
            const message = error instanceof Error ? error.message : 'Failed to generate Function App module.';
            funcStatus = message;
            notifyError(message);
        } finally {
            funcBusy = false;
        }
    };

    const handleApimSubmit = async (event?: SubmitEvent, opts?: { force?: boolean }) => {
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
        const forceSave = opts?.force ?? false;
        const shouldAutoSave = autoSaveEnabled || forceSave;
        try {
            const payload = buildApiManagementPayload();
            const context = requireProjectContext();
            if (!context) {
                apimBusy = false;
                return;
            }
            if (!shouldAutoSave) {
                const response = await generateAzureApiManagement(fetch, payload);
                generatorOverride = null;
                apimResult = response;
                apimStatus = 'Terraform module generated (auto-save disabled).';
                notifySuccess(apimStatus);
                clearGeneratorContext('azure_api_management');
                moveToReview();
                return;
            }
            const response = await runProjectGenerator(fetch, context.token, context.project.id, 'azure/api-management', {
                payload: payload as unknown as Record<string, unknown>,
                options: resolveGeneratorOptions(`${generatorLabels.azure_api_management} • ${new Date().toLocaleString()}`, forceSave)
            });
            generatorOverride = null;
            apimResult = response.output;
            recordGeneratorContext('azure_api_management', {
                asset: response.asset,
                version: response.version,
                run: response.run,
                project: context.project
            });
            const validationStatus = validationStatusLabel(response.version.validation_summary ?? null);
            if (validationStatus === 'failed') {
                const details = validationMessage(response.version.validation_summary ?? null);
                apimStatus = 'Terraform validation failed.';
                notifyError(details ?? 'Terraform validation failed in the API. Adjust inputs or run locally for details.');
                generatorOverride = {
                    generatorId: 'azure_api_management',
                    summary: response.version.validation_summary ?? null,
                    message: details ?? 'Terraform validation failed.',
                    assetName: payload.name,
                    metadata: {
                        generator: 'azure/api-management',
                        payload
                    }
                };
                return;
            }
            apimStatus =
                validationStatus === 'warn'
                    ? 'Terraform module generated with warnings. Review validation output.'
                    : `Terraform module generated (validation ${validationStatus}).`;
            notifySuccess(apimStatus);
            moveToDestination();
            projectState.upsertRun(context.project.id, response.run);
        } catch (error) {
            if (handleGeneratorValidationError('azure_api_management', error)) {
                apimStatus = 'Terraform validation failed.';
                return;
            }
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

    const requireProjectContext = (): { project: ProjectSummary; token: string } | null => {
        if (!browser) {
            return null;
        }
        if (!activeProjectValue) {
            if (!missingProjectWarningShown) {
                notifyError('Select a project to save generated configs into its library.');
                missingProjectWarningShown = true;
            }
            return null;
        }
        if (!authTokenValue) {
            notifyError('Authentication required to generate Terraform modules.');
            return null;
        }
        return { project: activeProjectValue, token: authTokenValue };
    };

    type ValidationStatus = 'skipped' | 'passed' | 'failed' | 'warn' | 'unknown';

    const validationStatusLabel = (summary?: Record<string, unknown> | null): ValidationStatus => {
        if (!summary) {
            return 'skipped';
        }
        const raw = summary['status'];
        if (typeof raw === 'string') {
            const lower = raw.toLowerCase();
            if (lower === 'passed' || lower === 'failed' || lower === 'warn' || lower === 'skipped') {
                return lower;
            }
        }
        return 'unknown' as ValidationStatus;
    };

    const validationMessage = (summary?: Record<string, unknown> | null): string | null => {
        if (!summary) return null;
        if (Array.isArray(summary['issues'])) {
            const issues = summary['issues']
                .map((issue) => (typeof issue === 'string' ? issue : JSON.stringify(issue)))
                .filter(Boolean);
            if (issues.length) {
                return issues.join('\n');
            }
        }
        if (typeof summary['details'] === 'string') {
            return summary['details'];
        }
        return null;
    };

    const validationStatusBadgeClass = (status: ValidationStatus): string => {
        switch (status) {
            case 'passed':
                return 'border-emerald-200 bg-emerald-50 text-emerald-600';
            case 'warn':
                return 'border-amber-200 bg-amber-50 text-amber-600';
            case 'failed':
                return 'border-rose-200 bg-rose-50 text-rose-600';
            default:
                return 'border-slate-200 bg-white text-slate-500';
        }
    };

    const parseValidationSummary = (error: unknown): Record<string, unknown> | null => {
        if (error instanceof ApiError && error.detail && typeof error.detail === 'object') {
            const detail = error.detail as Record<string, unknown>;
            if (detail.error === 'validation_failed') {
                const summary = detail.validation_summary;
                if (!summary || typeof summary !== 'object') {
                    return null;
                }
                return summary as Record<string, unknown>;
            }
        }
        return null;
    };

    const handleGeneratorValidationError = (generatorId: GeneratorId, error: unknown): boolean => {
        const summary = parseValidationSummary(error);
        if (!summary) {
            return false;
        }
        const message = validationMessage(summary);
        generatorOverride = {
            generatorId,
            summary,
            message,
        };
        notifyError(message ?? 'Terraform validation failed. Review validation output or override below.');
        return true;
    };

    const forceSaveCurrentGenerator = () => {
        if (!generatorOverride) return;
        const target = generatorOverride.generatorId;
        generatorOverride = null;
        switch (target) {
            case 'aws_s3':
                void handleAwsSubmit(undefined, { force: true });
                break;
            case 'azure_storage':
                void handleAzureStorageSubmit(undefined, { force: true });
                break;
            case 'azure_servicebus':
                void handleServiceBusSubmit(undefined, { force: true });
                break;
            case 'azure_function_app':
                void handleFunctionSubmit(undefined, { force: true });
                break;
            case 'azure_api_management':
                void handleApimSubmit(undefined, { force: true });
                break;
        }
    };

    const handleSaveDestination = async () => {
        const context = generatorContexts[activeGenerator];
        if (!context) {
            destinationError = 'Generate and save a module before editing the destination.';
            return;
        }
        if (!authTokenValue) {
            destinationError = 'Authentication required.';
            notifyError('Authentication required to update the library asset.');
            return;
        }
        destinationSaving = true;
        destinationError = null;
        try {
            await projectState.updateLibraryAsset(fetch, authTokenValue, context.projectId, context.asset.id, {
                name: destinationAssetName.trim() || undefined,
                description: destinationAssetDescription.trim() || undefined,
                tags: parseTagsInput(destinationAssetTags)
            });
            notifySuccess('Destination details updated.');
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to update destination metadata.';
            destinationError = message;
            notifyError(message);
        } finally {
            destinationSaving = false;
        }
    };

    const openLibraryForContext = (context: GeneratorRunContext | null) => {
        if (!context) return;
        projectState.setActiveProject(context.projectId);
        const slugOrId = context.projectSlug ?? projectSlugParam ?? context.projectId;
        const params = new URLSearchParams({
            tab: 'library',
            project: slugOrId,
            asset: context.asset.id
        });
        void goto(`/projects?${params.toString()}`);
    };

    const openDiffForContext = (context: GeneratorRunContext | null) => {
        if (!context) return;
        projectState.setActiveProject(context.projectId);
        const slugOrId = context.projectSlug ?? projectSlugParam ?? context.projectId;
        const params = new URLSearchParams({
            tab: 'library',
            project: slugOrId,
            asset: context.asset.id,
            version: context.version.id,
            action: 'diff'
        });
        void goto(`/projects?${params.toString()}`);
    };

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

    <ProjectWorkspaceBanner context="Generator runs and artifacts from this page are recorded under your active workspace." />

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
            />
        {/if}
    {:else if activeStep === 'destination'}
        {@const activeContext = generatorContexts[activeGenerator]}
        <section class="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
            <header class="space-y-2">
                <p class="text-xs font-semibold uppercase tracking-[0.35em] text-sky-500">Destination</p>
                <h3 class="text-xl font-semibold text-slate-700">Choose where the module is stored</h3>
                <p class="text-sm text-slate-500">
                    Confirm the workspace, naming, and metadata before heading to the review step. Toggle auto-save off if you only
                    need a one-off download.
                </p>
            </header>

            <div class="grid gap-4 md:grid-cols-2">
                <label class="space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                    <span>Workspace project</span>
                    <select
                        class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700"
                        value={activeProjectValue?.id ?? ''}
                        onchange={(event) => updateActiveProject((event.currentTarget as HTMLSelectElement).value)}
                    >
                        {#if !projectOptions.length}
                            <option value="" disabled>Loading projects…</option>
                        {:else}
                            {#each projectOptions as projectOption}
                                <option value={projectOption.id}>{projectOption.name}</option>
                            {/each}
                        {/if}
                    </select>
                </label>
                <label class="space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                    <span>Auto-save to project library</span>
                    <button
                        type="button"
                        class={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-sm font-semibold transition ${
                            autoSaveEnabled
                                ? 'border-emerald-300 bg-emerald-50 text-emerald-600'
                                : 'border-slate-200 bg-white text-slate-500'
                        }`}
                        onclick={() => (autoSaveEnabled = !autoSaveEnabled)}
                    >
                        <span>{autoSaveEnabled ? 'Enabled — runs are saved with validation summaries.' : 'Disabled — runs only render Terraform.'}</span>
                        <span class={`h-3 w-3 rounded-full ${autoSaveEnabled ? 'bg-emerald-500' : 'bg-slate-300'}`}></span>
                    </button>
                </label>
            </div>

            {#if autoSaveEnabled}
                {#if activeContext}
                    <div class="grid gap-4 md:grid-cols-2">
                        <label class="space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                            <span>Asset name</span>
                            <input class={inputClass} type="text" bind:value={destinationAssetName} placeholder={activeContext.asset.name} />
                        </label>
                        <label class="space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                            <span>Tags (comma separated)</span>
                            <input class={inputClass} type="text" bind:value={destinationAssetTags} placeholder="prod,baseline" />
                        </label>
                        <label class="md:col-span-2 space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                            <span>Description</span>
                            <textarea class={textareaClass} rows={3} bind:value={destinationAssetDescription}></textarea>
                        </label>
                    </div>
                    {#if destinationError}
                        <p class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-600">{destinationError}</p>
                    {/if}
                    <div class="flex flex-wrap items-center gap-3">
                        <button
                            type="button"
                            class={actionClass}
                            onclick={handleSaveDestination}
                            disabled={destinationSaving}
                        >
                            {destinationSaving ? 'Saving…' : 'Save destination updates'}
                        </button>
                        <button class={secondaryButtonClass} type="button" onclick={moveToReview}>
                            Continue to review
                        </button>
                        <button class={secondaryButtonClass} type="button" onclick={moveToConfigure}>
                            Back to inputs
                        </button>
                    </div>
                {:else}
                    <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                        Generate the module with auto-save enabled to edit destination metadata and quick links.
                    </div>
                    <div class="flex flex-wrap gap-3">
                        <button class={secondaryButtonClass} type="button" onclick={moveToConfigure}>
                            Back to inputs
                        </button>
                    </div>
                {/if}
            {:else}
                <div class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                    Auto-save is disabled. The generator will render Terraform for download/copy without creating project runs or
                    library assets.
                </div>
                <div class="flex flex-wrap gap-3">
                    <button class={secondaryButtonClass} type="button" onclick={moveToConfigure}>
                        Back to inputs
                    </button>
                    <button class={secondaryButtonClass} type="button" onclick={moveToReview}>
                        Continue to review
                    </button>
                </div>
            {/if}
        </section>
    {:else}
        {@const activeResult = getResultForGenerator(activeGenerator)}
        {@const reviewContext = generatorContexts[activeGenerator]}
        {@const reviewValidationStatus = validationStatusLabel(reviewContext?.version.validation_summary ?? null)}
        {@const reviewValidationMessage = reviewContext ? validationMessage(reviewContext.version.validation_summary ?? null) : null}
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

            {#if reviewContext}
                <div class="space-y-2 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                    <div class="flex flex-wrap items-center gap-3">
                        <span
                            class={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] ${
                                validationStatusBadgeClass(reviewValidationStatus)
                            }`}
                        >
                            Validation {reviewValidationStatus}
                        </span>
                        <div class="ml-auto flex flex-wrap gap-2">
                            <button type="button" class={resultButtonClass} onclick={() => openLibraryForContext(reviewContext)}>
                                Open in library
                            </button>
                            <button type="button" class={resultButtonClass} onclick={() => openDiffForContext(reviewContext)}>
                                Diff vs previous
                            </button>
                        </div>
                    </div>
                    {#if reviewValidationMessage}
                        <pre class="overflow-auto rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
{reviewValidationMessage}</pre>
                    {/if}
                </div>
            {/if}

            {#if generatorOverride && generatorOverride.generatorId === activeGenerator}
                <div class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700 space-y-2">
                    <p class="font-semibold">Validation failed</p>
                    <p class="mt-1 text-xs">
                    Fix the reported issues and regenerate, or continue and override validation in your workspace. Use the project
                    generator log to inspect the saved run and library asset.
                </p>
                {#if generatorOverride.message}
                    <pre class="overflow-auto rounded-xl border border-amber-300 bg-white/80 p-3 text-xs text-amber-800">
{generatorOverride.message}</pre>
                {/if}
                <div class="flex flex-wrap gap-2">
                    <button
                        type="button"
                        class={resultButtonClass}
                        onclick={forceSaveCurrentGenerator}
                        disabled={awsBusy || azureBusy || sbBusy || funcBusy || apimBusy}
                    >
                        Force save anyway
                    </button>
                    <button
                        type="button"
                        class="rounded-xl border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-500 transition hover:bg-slate-100"
                        onclick={() => (generatorOverride = null)}
                    >
                        Dismiss
                    </button>
                </div>
            </div>
        {/if}

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
