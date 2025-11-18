<script lang="ts">
    import type { GeneratorResult } from '$lib/api/client';
    import type { GeneratorFormStyles } from './types';

    export let styles: GeneratorFormStyles;
    export let resourceGroupName: string;
    export let serviceName: string;
    export let location: string;
    export let environment: string;
    export let publisherName: string;
    export let publisherEmail: string;
    export let sku: string;
    export let capacity: string;
    export let zones: string;
    export let vnetType: string;
    export let subnetId: string;
    export let identityType: string;
    export let customProperties: string;
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
                <span>API Management name</span>
                <input class={styles.input} type="text" bind:value={serviceName} />
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
                <span>Publisher name</span>
                <input class={styles.input} type="text" bind:value={publisherName} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Publisher email</span>
                <input class={styles.input} type="email" bind:value={publisherEmail} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>SKU</span>
                <input class={styles.input} type="text" bind:value={sku} placeholder="Premium_1" />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Capacity (optional)</span>
                <input class={styles.input} type="text" bind:value={capacity} placeholder="1" />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600 md:col-span-2">
                <span>Availability zones (one per line)</span>
                <textarea class={`${styles.textarea} h-24`} bind:value={zones}></textarea>
            </label>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Virtual network type</span>
                <select class={styles.input} bind:value={vnetType}>
                    <option value="None">None</option>
                    <option value="External">External</option>
                    <option value="Internal">Internal</option>
                </select>
            </label>
            {#if vnetType !== 'None'}
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Subnet ID</span>
                    <input class={styles.input} type="text" bind:value={subnetId} />
                </label>
            {/if}
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Managed identity type</span>
                <select class={styles.input} bind:value={identityType}>
                    <option value="SystemAssigned">SystemAssigned</option>
                    <option value="UserAssigned">UserAssigned</option>
                    <option value="SystemAssigned, UserAssigned">SystemAssigned, UserAssigned</option>
                </select>
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600 md:col-span-2">
                <span>Custom properties (key=value per line)</span>
                <textarea class={`${styles.textarea} h-24`} bind:value={customProperties}></textarea>
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Owner tag</span>
                <input class={styles.input} type="text" bind:value={ownerTag} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Cost center tag</span>
                <input class={styles.input} type="text" bind:value={costCenterTag} />
            </label>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={diagnosticsEnabled} />
                <span>Enable diagnostics</span>
            </label>
        </div>

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
                <li>• Managed identity enabled for downstream Azure resource access.</li>
                <li>• Optional VNet integration and zone redundancy for production deployments.</li>
                <li>• Diagnostics pipeline ready for Log Analytics.</li>
                <li>• Custom properties allow explicit gateway hardening.</li>
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
