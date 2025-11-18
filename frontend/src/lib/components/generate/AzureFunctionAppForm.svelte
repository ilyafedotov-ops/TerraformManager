<script lang="ts">
    import type { GeneratorResult } from '$lib/api/client';
    import type { GeneratorFormStyles } from './types';

    export let styles: GeneratorFormStyles;
    export let resourceGroupName: string;
    export let functionAppName: string;
    export let storageAccountName: string;
    export let appServicePlanName: string;
    export let location: string;
    export let environment: string;
    export let runtime: string;
    export let runtimeVersion: string;
    export let appServicePlanSku: string;
    export let storageReplication: string;
    export let enableVnetIntegration: boolean;
    export let subnetId: string;
    export let enableInsights: boolean;
    export let insightsName: string;
    export let diagnosticsEnabled: boolean;
    export let diagnosticsWorkspaceId: string;
    export let diagnosticsLogCategories: string;
    export let diagnosticsMetricCategories: string;
    export let ownerTag: string;
    export let costCenterTag: string;
    export let status: string | null;
    export let busy: boolean;
    export let result: GeneratorResult | null;
    export let onSubmit: (event: SubmitEvent) => void;
    export let onCopy: () => void;
    export let onDownload: () => void;
</script>

<form
    method="POST"
    class="grid gap-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]"
    on:submit={onSubmit}
>
    <div class="space-y-6">
        <div class="grid gap-4 md:grid-cols-2">
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Resource group name</span>
                <input class={styles.input} type="text" bind:value={resourceGroupName} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Function App name</span>
                <input class={styles.input} type="text" bind:value={functionAppName} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Storage account name</span>
                <input class={styles.input} type="text" bind:value={storageAccountName} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>App Service plan name</span>
                <input class={styles.input} type="text" bind:value={appServicePlanName} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Location</span>
                <input class={styles.input} type="text" bind:value={location} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Environment</span>
                <input class={styles.input} type="text" bind:value={environment} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Runtime</span>
                <input class={styles.input} type="text" bind:value={runtime} placeholder="dotnet | node | python" />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Runtime version</span>
                <input class={styles.input} type="text" bind:value={runtimeVersion} placeholder="8" />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>App Service plan SKU</span>
                <input class={styles.input} type="text" bind:value={appServicePlanSku} placeholder="EP1" />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Storage replication</span>
                <input class={styles.input} type="text" bind:value={storageReplication} placeholder="LRS" />
            </label>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={enableVnetIntegration} />
                <span>Enable VNet integration</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={enableInsights} />
                <span>Enable Application Insights</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={diagnosticsEnabled} />
                <span>Enable diagnostics</span>
            </label>
        </div>

        {#if enableVnetIntegration}
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>VNet subnet resource ID</span>
                <input class={styles.input} type="text" bind:value={subnetId} />
            </label>
        {/if}

        {#if enableInsights}
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Application Insights name</span>
                <input class={styles.input} type="text" bind:value={insightsName} />
            </label>
        {/if}

        {#if diagnosticsEnabled}
            <div class="grid gap-4 md:grid-cols-2">
                <label class="space-y-2 text-sm font-medium text-slate-600 md:col-span-2">
                    <span>Log Analytics workspace resource ID</span>
                    <input class={styles.input} type="text" bind:value={diagnosticsWorkspaceId} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Log categories</span>
                    <textarea class={`${styles.textarea} h-24`} bind:value={diagnosticsLogCategories}></textarea>
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Metric categories</span>
                    <textarea class={`${styles.textarea} h-24`} bind:value={diagnosticsMetricCategories}></textarea>
                </label>
            </div>
        {/if}

        <div class="grid gap-4 md:grid-cols-2">
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Owner tag</span>
                <input class={styles.input} type="text" bind:value={ownerTag} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Cost center tag</span>
                <input class={styles.input} type="text" bind:value={costCenterTag} />
            </label>
        </div>

        {#if status}
            <div class={styles.status} role="status" aria-live="polite">{status}</div>
        {/if}

        <button class={styles.primaryAction} type="submit" disabled={busy}>
            {#if busy}
                <span class={styles.spinner}></span>
                Generating…
            {:else}
                Generate module
            {/if}
        </button>
    </div>

    <aside class="space-y-4">
        <div class="rounded-3xl border border-slate-200 bg-slate-50 p-5">
            <h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Best practice highlights</h3>
            <ul class="mt-3 space-y-2 text-xs text-slate-500">
                <li>• Managed identity enabled by default for secure downstream access.</li>
                <li>• Application Insights provisioned for telemetry and monitoring.</li>
                <li>• FTPS disabled and TLS 1.2 enforced for inbound traffic.</li>
                <li>• Optional VNet integration for private outbound traffic.</li>
            </ul>
        </div>

        {#if result}
            <div class={styles.resultContainer}>
                <header class={styles.resultHeader}>
                    <div>
                        <p class={styles.resultTitle}>{result.filename}</p>
                    </div>
                    <div class={styles.resultActions}>
                        <button class={styles.resultButton} type="button" on:click={onCopy}>
                            Copy
                        </button>
                        <button class={styles.resultButton} type="button" on:click={onDownload}>
                            Download
                        </button>
                    </div>
                </header>
                <pre class={styles.resultContent}>{result.content}</pre>
            </div>
        {:else}
            <div class={styles.placeholder}>Generated Terraform will appear here.</div>
        {/if}
    </aside>
</form>
