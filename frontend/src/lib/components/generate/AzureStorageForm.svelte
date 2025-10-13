<script lang="ts">
    import { enhance } from '$app/forms';
    import type { SubmitFunction } from '@sveltejs/kit';
    import type { GeneratorResult } from '$lib/api/client';
    import type { GeneratorFormStyles } from './types';

    export let styles: GeneratorFormStyles;
    export let resourceGroupName: string;
    export let accountName: string;
    export let location: string;
    export let environment: string;
    export let replication: string;
    export let ownerTag: string;
    export let costCenterTag: string;
    export let enableVersioning: boolean;
    export let restrictNetwork: boolean;
    export let includeBackend: boolean;
    export let includePrivateEndpoint: boolean;
    export let allowedIps: string;
    export let backendResourceGroup: string;
    export let backendAccount: string;
    export let backendContainer: string;
    export let backendKey: string;
    export let privateEndpointName: string;
    export let privateEndpointConnection: string;
    export let privateEndpointSubnet: string;
    export let privateDnsZoneId: string;
    export let privateDnsZoneGroup: string;
    export let status: string | null;
    export let busy: boolean;
    export let result: GeneratorResult | null;
    export let onSubmit: (event: SubmitEvent) => void;
    export let onCopy: () => void;
    export let onDownload: () => void;
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
                <span>Storage account name</span>
                <input class={styles.input} type="text" bind:value={accountName} />
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
                <span>Replication</span>
                <input class={styles.input} type="text" bind:value={replication} placeholder="LRS" />
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
                <input class={styles.checkboxInput} type="checkbox" bind:checked={enableVersioning} />
                <span>Enable blob versioning</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={restrictNetwork} />
                <span>Restrict network access</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={includeBackend} />
                <span>Include Terraform backend</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={includePrivateEndpoint} />
                <span>Create private endpoint</span>
            </label>
        </div>

        {#if restrictNetwork}
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Allowed IPv4 ranges (one per line)</span>
                <textarea class={`${styles.textarea} h-28`} bind:value={allowedIps}></textarea>
            </label>
        {/if}

        {#if includeBackend}
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

        {#if includePrivateEndpoint}
            <div class="grid gap-4 md:grid-cols-2">
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Private endpoint name</span>
                    <input class={styles.input} type="text" bind:value={privateEndpointName} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Service connection name</span>
                    <input class={styles.input} type="text" bind:value={privateEndpointConnection} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Subnet ID</span>
                    <input class={styles.input} type="text" bind:value={privateEndpointSubnet} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>Private DNS zone ID (optional)</span>
                    <input class={styles.input} type="text" bind:value={privateDnsZoneId} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>DNS zone group name</span>
                    <input class={styles.input} type="text" bind:value={privateDnsZoneGroup} />
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
                <li>• HTTPS-only enforced and public access disabled by default.</li>
                <li>• Optional private endpoint with DNS attachments for internal workloads.</li>
                <li>• Network restrictions require explicit CIDR allow-lists.</li>
                <li>• Remote state backend wiring for Terraform teams.</li>
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
