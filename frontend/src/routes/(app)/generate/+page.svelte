<script lang="ts">
    import {
        generateAwsS3,
        generateAzureStorageAccount,
        type AwsS3GeneratorPayload,
        type AzureStorageGeneratorPayload,
        type GeneratorResult
    } from '$lib/api/client';

    type GeneratorId = 'aws_s3' | 'azure_storage';

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
        }
    ];

    let activeGenerator = $state<GeneratorId>('aws_s3');

    const inputClass =
        'w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40';
    const textareaClass =
        'w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40';
    const checkboxClass = 'flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-slate-200';
    const checkboxInputClass = 'h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/50';
    const statusClass = 'rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-2 text-xs text-slate-200';
    const actionClass =
        'inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-900/40 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:cursor-not-allowed disabled:opacity-60';
    const spinnerClass = 'h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent';
    const resultClass = 'space-y-3 rounded-3xl border border-white/5 bg-slate-900/70 p-5';
    const resultHeaderClass = 'flex items-center justify-between gap-3';
    const resultTitleClass = 'text-sm font-semibold text-white';
    const resultActionsClass = 'flex gap-2';
    const resultButtonClass =
        'rounded-xl border border-white/10 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white';
    const resultContentClass = 'max-h-96 overflow-auto rounded-2xl bg-slate-950/70 p-4 text-xs text-slate-200';
    const placeholderClass = 'rounded-3xl border border-dashed border-white/10 bg-slate-900/60 p-5 text-sm text-slate-400';

    // AWS S3 state
    let awsBucketName = $state('my-secure-logs-bucket');
    let awsRegion = $state('us-east-1');
    let awsEnvironment = $state('prod');
    let awsOwnerTag = $state('platform-team');
    let awsCostCenterTag = $state('ENG-SRE');
    let awsForceDestroy = $state(false);
    let awsVersioning = $state(true);
    let awsEnforceSecureTransport = $state(true);
    let awsKmsKeyId = $state('');
    let awsIncludeBackend = $state(false);
    let awsBackendBucket = $state('terraform-state-bucket');
    let awsBackendKey = $state('s3/baseline/terraform.tfstate');
    let awsBackendRegion = $state('us-east-1');
    let awsBackendTable = $state('terraform_locks');
    let awsResult = $state<GeneratorResult | null>(null);
    let awsStatus = $state<string | null>(null);
    let awsBusy = $state(false);

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

    const handleAwsSubmit = async (event: SubmitEvent) => {
        event.preventDefault();
        awsStatus = null;
        awsResult = null;
        if (!awsBucketName.trim()) {
            awsStatus = 'Bucket name is required.';
            return;
        }
        if (awsIncludeBackend && (!awsBackendBucket.trim() || !awsBackendKey.trim() || !awsBackendTable.trim())) {
            awsStatus = 'Provide backend bucket, key, and DynamoDB table.';
            return;
        }
        awsBusy = true;
        try {
            awsResult = await generateAwsS3(fetch, buildAwsPayload());
            awsStatus = 'Terraform module generated successfully.';
        } catch (error) {
            awsStatus = error instanceof Error ? error.message : 'Failed to generate AWS S3 module.';
        } finally {
            awsBusy = false;
        }
    };

    const copyAws = async () => {
        if (!awsResult) return;
        try {
            await navigator.clipboard.writeText(awsResult.content);
            awsStatus = 'Copied to clipboard.';
        } catch (error) {
            awsStatus = error instanceof Error ? error.message : 'Unable to copy to clipboard.';
        }
    };

    const downloadAws = () => {
        if (!awsResult) return;
        const blob = new Blob([awsResult.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = awsResult.filename;
        link.click();
        URL.revokeObjectURL(url);
    };

    // Azure storage state
    let azureRgName = $state('rg-app');
    let azureSaName = $state('stapp1234567890');
    let azureLocation = $state('eastus');
    let azureEnvironment = $state('prod');
    let azureReplication = $state('LRS');
    let azureVersioning = $state(true);
    let azureOwnerTag = $state('platform-team');
    let azureCostCenterTag = $state('ENG-SRE');
    let azureRestrictNetwork = $state(true);
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

    const buildAzurePayload = (): AzureStorageGeneratorPayload => ({
        resource_group_name: azureRgName,
        storage_account_name: azureSaName,
        location: azureLocation,
        environment: azureEnvironment,
        replication: azureReplication,
        versioning: azureVersioning,
        owner_tag: azureOwnerTag,
        cost_center_tag: azureCostCenterTag,
        restrict_network: azureRestrictNetwork,
        allowed_ips: azureAllowedIps
            .split(/\r?\n|,/)
            .map((ip) => ip.trim())
            .filter(Boolean),
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

    const handleAzureSubmit = async (event: SubmitEvent) => {
        event.preventDefault();
        azureStatus = null;
        azureResult = null;
        if (!azureRgName.trim() || !azureSaName.trim()) {
            azureStatus = 'Resource group and storage account names are required.';
            return;
        }
        if (azureIncludeBackend && (!azureBackendRg.trim() || !azureBackendAccount.trim() || !azureBackendContainer.trim() || !azureBackendKey.trim())) {
            azureStatus = 'Provide resource group, storage account, container, and key for remote state.';
            return;
        }
        if (azureRestrictNetwork && !azureAllowedIps.trim()) {
            azureStatus = 'Specify at least one CIDR range when network restrictions are enabled.';
            return;
        }
        if (azureIncludePrivateEndpoint && (!azurePrivateEndpointSubnet.trim() || !azurePrivateEndpointName.trim())) {
            azureStatus = 'Private endpoint subnet and name are required.';
            return;
        }
        azureBusy = true;
        try {
            azureResult = await generateAzureStorageAccount(fetch, buildAzurePayload());
            azureStatus = 'Terraform module generated successfully.';
        } catch (error) {
            azureStatus = error instanceof Error ? error.message : 'Failed to generate Azure storage module.';
        } finally {
            azureBusy = false;
        }
    };

    const copyAzure = async () => {
        if (!azureResult) return;
        try {
            await navigator.clipboard.writeText(azureResult.content);
            azureStatus = 'Copied to clipboard.';
        } catch (error) {
            azureStatus = error instanceof Error ? error.message : 'Unable to copy to clipboard.';
        }
    };

    const downloadAzure = () => {
        if (!azureResult) return;
        const blob = new Blob([azureResult.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = azureResult.filename;
        link.click();
        URL.revokeObjectURL(url);
    };
</script>

<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Blueprint Studio</p>
        <h2 class="text-3xl font-semibold text-white">Generate hardened Terraform modules</h2>
        <p class="max-w-3xl text-sm text-slate-400">
            Select a generator and tailor the inputs to your environment. Generated Terraform can be copied directly into your
            codebase or downloaded as a `.tf` file.
        </p>
    </header>

    <nav class="flex flex-wrap gap-3">
        {#each generators as option}
            <button
                class={`rounded-2xl border px-4 py-2 text-sm font-semibold transition ${
                    activeGenerator === option.id
                        ? 'border-sky-400/50 bg-sky-500/10 text-sky-200'
                        : 'border-white/10 bg-slate-900/70 text-slate-300 hover:border-sky-400/30'
                }`}
                type="button"
                onclick={() => (activeGenerator = option.id)}
            >
                {option.label}
            </button>
        {/each}
    </nav>

    <p class="text-xs text-slate-400">{generators.find((g) => g.id === activeGenerator)?.description}</p>

    {#if activeGenerator === 'aws_s3'}
        <form class="grid gap-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]" onsubmit={handleAwsSubmit}>
            <div class="space-y-6">
                <div class="grid gap-4 md:grid-cols-2">
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Bucket name</span>
                        <input class={inputClass} type="text" bind:value={awsBucketName} placeholder="my-secure-logs-bucket" />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Region</span>
                        <input class={inputClass} type="text" bind:value={awsRegion} placeholder="us-east-1" />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Environment</span>
                        <input class={inputClass} type="text" bind:value={awsEnvironment} placeholder="prod" />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Owner tag</span>
                        <input class={inputClass} type="text" bind:value={awsOwnerTag} />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Cost center tag</span>
                        <input class={inputClass} type="text" bind:value={awsCostCenterTag} />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>KMS key ARN (optional)</span>
                        <input class={inputClass} type="text" bind:value={awsKmsKeyId} placeholder="arn:aws:kms:..." />
                    </label>
                </div>

                <div class="grid gap-4 md:grid-cols-2">
                    <label class={checkboxClass}>
                        <input class={checkboxInputClass} type="checkbox" bind:checked={awsForceDestroy} />
                        <span>Enable force destroy</span>
                    </label>
                    <label class={checkboxClass}>
                        <input class={checkboxInputClass} type="checkbox" bind:checked={awsVersioning} />
                        <span>Enable versioning</span>
                    </label>
                    <label class={checkboxClass}>
                        <input class={checkboxInputClass} type="checkbox" bind:checked={awsEnforceSecureTransport} />
                        <span>Enforce TLS-only access</span>
                    </label>
                    <label class={checkboxClass}>
                        <input class={checkboxInputClass} type="checkbox" bind:checked={awsIncludeBackend} />
                        <span>Include remote state backend</span>
                    </label>
                </div>

                {#if awsIncludeBackend}
                    <div class="grid gap-4 md:grid-cols-2">
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>State bucket</span>
                            <input class={inputClass} type="text" bind:value={awsBackendBucket} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>State key</span>
                            <input class={inputClass} type="text" bind:value={awsBackendKey} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>State region</span>
                            <input class={inputClass} type="text" bind:value={awsBackendRegion} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>DynamoDB lock table</span>
                            <input class={inputClass} type="text" bind:value={awsBackendTable} />
                        </label>
                    </div>
                {/if}

                {#if awsStatus}
                    <div class={statusClass}>{awsStatus}</div>
                {/if}

                <button class={actionClass} type="submit" disabled={awsBusy}>
                    {#if awsBusy}
                        <span class={spinnerClass}></span>
                        Generating…
                    {:else}
                        Generate module
                    {/if}
                </button>
            </div>

            <aside class="space-y-4">
                <div class="rounded-3xl border border-white/5 bg-slate-900/70 p-5">
                    <h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">Best practice highlights</h3>
                    <ul class="mt-3 space-y-2 text-xs text-slate-300">
                        <li>• Public access block enforced to prevent ACL misconfiguration.</li>
                        <li>• Server-side encryption defaults to AES256 or the supplied KMS key.</li>
                        <li>• Optional TLS-only bucket policy protects against HTTP traffic.</li>
                        <li>• Remote state backend emitted on demand for multi-team state.</li>
                    </ul>
                </div>

                {#if awsResult}
                    <div class={resultClass}>
                        <header class={resultHeaderClass}>
                            <div>
                                <p class={resultTitleClass}>{awsResult.filename}</p>
                            </div>
                            <div class={resultActionsClass}>
                                <button class={resultButtonClass} type="button" onclick={copyAws}>Copy</button>
                                <button class={resultButtonClass} type="button" onclick={downloadAws}>Download</button>
                            </div>
                        </header>
                        <pre class={resultContentClass}>{awsResult.content}</pre>
                    </div>
                {:else}
                    <div class={placeholderClass}>Generated Terraform will appear here.</div>
                {/if}
            </aside>
        </form>
    {:else if activeGenerator === 'azure_storage'}
        <form class="grid gap-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]" onsubmit={handleAzureSubmit}>
            <div class="space-y-6">
                <div class="grid gap-4 md:grid-cols-2">
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Resource group name</span>
                        <input class={inputClass} type="text" bind:value={azureRgName} />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Storage account name</span>
                        <input class={inputClass} type="text" bind:value={azureSaName} />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Location</span>
                        <input class={inputClass} type="text" bind:value={azureLocation} />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Environment</span>
                        <input class={inputClass} type="text" bind:value={azureEnvironment} />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Replication</span>
                        <input class={inputClass} type="text" bind:value={azureReplication} placeholder="LRS" />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Owner tag</span>
                        <input class={inputClass} type="text" bind:value={azureOwnerTag} />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Cost center tag</span>
                        <input class={inputClass} type="text" bind:value={azureCostCenterTag} />
                    </label>
                </div>

                <div class="grid gap-4 md:grid-cols-2">
                    <label class={checkboxClass}>
                        <input class={checkboxInputClass} type="checkbox" bind:checked={azureVersioning} />
                        <span>Enable blob versioning</span>
                    </label>
                    <label class={checkboxClass}>
                        <input class={checkboxInputClass} type="checkbox" bind:checked={azureRestrictNetwork} />
                        <span>Restrict network access</span>
                    </label>
                    <label class={checkboxClass}>
                        <input class={checkboxInputClass} type="checkbox" bind:checked={azureIncludeBackend} />
                        <span>Include Terraform backend</span>
                    </label>
                    <label class={checkboxClass}>
                        <input class={checkboxInputClass} type="checkbox" bind:checked={azureIncludePrivateEndpoint} />
                        <span>Create private endpoint</span>
                    </label>
                </div>

                {#if azureRestrictNetwork}
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>Allowed IPv4 ranges (one per line)</span>
                        <textarea class={`${textareaClass} h-28`} bind:value={azureAllowedIps}></textarea>
                    </label>
                {/if}

                {#if azureIncludeBackend}
                    <div class="grid gap-4 md:grid-cols-2">
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>State resource group</span>
                            <input class={inputClass} type="text" bind:value={azureBackendRg} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>State storage account</span>
                            <input class={inputClass} type="text" bind:value={azureBackendAccount} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>State container</span>
                            <input class={inputClass} type="text" bind:value={azureBackendContainer} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>State blob key</span>
                            <input class={inputClass} type="text" bind:value={azureBackendKey} />
                        </label>
                    </div>
                {/if}

                {#if azureIncludePrivateEndpoint}
                    <div class="grid gap-4 md:grid-cols-2">
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>Private endpoint name</span>
                            <input class={inputClass} type="text" bind:value={azurePrivateEndpointName} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>Service connection name</span>
                            <input class={inputClass} type="text" bind:value={azurePrivateEndpointConnection} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>Subnet ID</span>
                            <input class={inputClass} type="text" bind:value={azurePrivateEndpointSubnet} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>Private DNS zone ID (optional)</span>
                            <input class={inputClass} type="text" bind:value={azurePrivateDnsZoneId} />
                        </label>
                        <label class="space-y-2 text-sm font-medium text-slate-200">
                            <span>DNS zone group name</span>
                            <input class={inputClass} type="text" bind:value={azurePrivateDnsZoneGroup} />
                        </label>
                    </div>
                {/if}

                {#if azureStatus}
                    <div class={statusClass}>{azureStatus}</div>
                {/if}

                <button class={actionClass} type="submit" disabled={azureBusy}>
                    {#if azureBusy}
                        <span class={spinnerClass}></span>
                        Generating…
                    {:else}
                        Generate module
                    {/if}
                </button>
            </div>

            <aside class="space-y-4">
                <div class="rounded-3xl border border-white/5 bg-slate-900/70 p-5">
                    <h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">Best practice highlights</h3>
                    <ul class="mt-3 space-y-2 text-xs text-slate-300">
                        <li>• HTTPS-only and TLS 1.2 enforced by default.</li>
                        <li>• Optional network rules for approved CIDR ranges.</li>
                        <li>• Private endpoint scaffolding with DNS integration support.</li>
                        <li>• Remote state backend available for Terraform workflows.</li>
                    </ul>
                </div>

                {#if azureResult}
                    <div class={resultClass}>
                        <header class={resultHeaderClass}>
                            <div>
                                <p class={resultTitleClass}>{azureResult.filename}</p>
                            </div>
                            <div class={resultActionsClass}>
                                <button class={resultButtonClass} type="button" onclick={copyAzure}>Copy</button>
                                <button class={resultButtonClass} type="button" onclick={downloadAzure}>Download</button>
                            </div>
                        </header>
                        <pre class={resultContentClass}>{azureResult.content}</pre>
                    </div>
                {:else}
                    <div class={placeholderClass}>Generated Terraform will appear here.</div>
                {/if}
            </aside>
        </form>
    {/if}
</section>
