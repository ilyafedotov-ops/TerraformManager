<script lang="ts">
    import { enhance } from '$app/forms';
    import type { SubmitFunction } from '@sveltejs/kit';
    import type { GeneratorResult } from '$lib/api/client';
    import type { GeneratorFormStyles } from './types';

    export let styles: GeneratorFormStyles;
    export let bucketName: string;
    export let region: string;
    export let environment: string;
    export let ownerTag: string;
    export let costCenterTag: string;
    export let kmsKeyId: string;
    export let forceDestroy: boolean;
    export let versioning: boolean;
    export let enforceSecureTransport: boolean;
    export let includeBackend: boolean;
    export let backendBucket: string;
    export let backendKey: string;
    export let backendRegion: string;
    export let backendTable: string;
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
                <span>Bucket name</span>
                <input class={styles.input} type="text" bind:value={bucketName} placeholder="my-secure-logs-bucket" />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Region</span>
                <input class={styles.input} type="text" bind:value={region} placeholder="us-east-1" />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Environment</span>
                <input class={styles.input} type="text" bind:value={environment} placeholder="prod" />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Owner tag</span>
                <input class={styles.input} type="text" bind:value={ownerTag} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>Cost center tag</span>
                <input class={styles.input} type="text" bind:value={costCenterTag} />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-600">
                <span>KMS key ARN (optional)</span>
                <input class={styles.input} type="text" bind:value={kmsKeyId} placeholder="arn:aws:kms:..." />
            </label>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={forceDestroy} />
                <span>Enable force destroy</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={versioning} />
                <span>Enable versioning</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={enforceSecureTransport} />
                <span>Enforce TLS-only access</span>
            </label>
            <label class={styles.checkboxWrapper}>
                <input class={styles.checkboxInput} type="checkbox" bind:checked={includeBackend} />
                <span>Include remote state backend</span>
            </label>
        </div>

        {#if includeBackend}
            <div class="grid gap-4 md:grid-cols-2">
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>State bucket</span>
                    <input class={styles.input} type="text" bind:value={backendBucket} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>State key</span>
                    <input class={styles.input} type="text" bind:value={backendKey} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>State region</span>
                    <input class={styles.input} type="text" bind:value={backendRegion} />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-600">
                    <span>DynamoDB table (optional)</span>
                    <input class={styles.input} type="text" bind:value={backendTable} />
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
                <li>• Default encryption and public access restrictions applied.</li>
                <li>• TLS enforcement ensures clients use HTTPS for object access.</li>
                <li>• Optional DynamoDB locking to protect Terraform state.</li>
                <li>• Tags baked in for ownership and cost allocation.</li>
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
