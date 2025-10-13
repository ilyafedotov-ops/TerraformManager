<script lang="ts">
    import { enhance } from '$app/forms';
    import type { SubmitFunction } from '@sveltejs/kit';
    import type { GeneratorResult } from '$lib/api/client';
    import type { GeneratorFormStyles } from './types';
    import type { ServiceBusPreset } from './models';

    export let styles: GeneratorFormStyles;
    export let presets: ServiceBusPreset[];
    export let presetId: string;
    export let resourceGroupName: string;
    export let namespaceName: string;
    export let location: string;
    export let environment: string;
    export let sku: string;
    export let capacity: string;
    export let zoneRedundant: boolean;
    export let ownerTag: string;
    export let costCenterTag: string;
    export let restrictNetwork: boolean;
    export let privateEndpointEnabled: boolean;
    export let privateEndpointName: string;
    export let privateEndpointSubnet: string;
    export let privateEndpointZones: string;
    export let diagnosticsEnabled: boolean;
    export let diagnosticsWorkspaceId: string;
    export let diagnosticsLogCategories: string;
    export let diagnosticsMetricCategories: string;
    export let cmkEnabled: boolean;
    export let cmkKeyId: string;
    export let cmkIdentityId: string;
    export let queueNames: string;
    export let topicNames: string;
    export let backendEnabled: boolean;
    export let backendResourceGroup: string;
    export let backendAccount: string;
    export let backendContainer: string;
    export let backendKey: string;
    export let status: string | null;
    export let busy: boolean;
    export let result: GeneratorResult | null;
    export let onSubmit: (event: SubmitEvent) => void;
    export let onCopy: () => void;
    export let onDownload: () => void;
    export let applyPreset: (presetId: string) => void;
    export let enhanceAction: SubmitFunction | null = null;
</script>

<form
    method="POST"
    class="grid gap-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]"
    on:submit={onSubmit}
    use:enhance={enhanceAction ?? undefined}
>
    <div class="space-y-6">
        <div class="grid gap-4 md:grid-cols-2">
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Resource group name</span>
                <input class={styles.input} type="text" bind:value={resourceGroupName} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Namespace name</span>
                <input class={styles.input} type="text" bind:value={namespaceName} />
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
                <span>SKU</span>
                <input class={styles.input} type="text" bind:value={sku} placeholder="Premium" />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Capacity (optional)</span>
                <input class={styles.input} type="text" bind:value={capacity} placeholder="1" />
            </label>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
            <div class="md:col-span-2 flex flex-wrap items-end gap-3">
                <label class="flex flex-1 flex-col space-y-2 text-sm font-medium text-slate-600">
                    <span>Preset template</span>
                    <select class={styles.input} bind:value={presetId}>
                        {#each presets as preset}
                            <option value={preset.id}>{preset.label}</option>
                        {/each}
                    </select>
                    <span class="text-xs font-normal text-slate-500">
                        {presets.find((preset) => preset.id === presetId)?.description}
                    </span>
                </label>
                <button class={styles.resultButton} type="button" on:click={() => applyPreset(presetId)}>
                    Apply preset
                </button>
            </div>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={zoneRedundant} />
                <span>Enable zone redundancy</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={restrictNetwork} />
                <span>Disable public network access</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={privateEndpointEnabled} />
                <span>Create private endpoint</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={diagnosticsEnabled} />
                <span>Enable diagnostics</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={cmkEnabled} />
                <span>Use customer-managed key</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={backendEnabled} />
                <span>Include Terraform backend</span>
            </label>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Queues (one per line)</span>
                <textarea class={`${styles.textarea} h-32`} bind:value={queueNames}></textarea>
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Topics (one per line)</span>
                <textarea class={`${styles.textarea} h-32`} bind:value={topicNames}></textarea>
            </label>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Owner tag</span>
                <input class={styles.input} type="text" bind:value={ownerTag} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Cost center tag</span>
                <input class={styles.input} type="text" bind:value={costCenterTag} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Customer-managed key ID</span>
                <input class={styles.input} type="text" bind:value={cmkKeyId} disabled={!cmkEnabled} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>User-assigned identity ID (optional)</span>
                <input class={styles.input} type="text" bind:value={cmkIdentityId} disabled={!cmkEnabled} />
            </label>
        </div>

        {#if privateEndpointEnabled}
            <div class="grid gap-4 md:grid-cols-2">
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Private endpoint name</span>
                    <input class={styles.input} type="text" bind:value={privateEndpointName} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Subnet ID</span>
                    <input class={styles.input} type="text" bind:value={privateEndpointSubnet} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600 md:col-span-2">
                    <span>Private DNS zone IDs (comma/newline separated)</span>
                    <textarea class={`${styles.textarea} h-24`} bind:value={privateEndpointZones}></textarea>
                    <p class="text-xs text-slate-500">
                        For example: <code>.../privateDnsZones/privatelink.servicebus.windows.net</code>.
                    </p>
                </label>
            </div>
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
                    <p class="text-xs text-slate-500">Default: <code>OperationalLogs</code>. Separate entries with commas or new lines.</p>
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Metric categories</span>
                    <textarea class={`${styles.textarea} h-24`} bind:value={diagnosticsMetricCategories}></textarea>
                </label>
            </div>
        {/if}

        {#if backendEnabled}
            <div class="grid gap-4 md:grid-cols-2">
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>State resource group</span>
                    <input class={styles.input} type="text" bind:value={backendResourceGroup} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>State storage account</span>
                    <input class={styles.input} type="text" bind:value={backendAccount} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>State container</span>
                    <input class={styles.input} type="text" bind:value={backendContainer} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>State blob key</span>
                    <input class={styles.input} type="text" bind:value={backendKey} />
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
                <li>• Managed identities and CMK support for secure authentication.</li>
                <li>• Private endpoint scaffolding with optional DNS integration.</li>
                <li>• Diagnostics wiring for OperationalLogs and metrics.</li>
                <li>• Remote state backend toggle for Terraform workflows.</li>
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
