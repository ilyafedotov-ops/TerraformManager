<script lang="ts">
    import { generateAwsS3, type AwsS3GeneratorPayload } from '$lib/api/client';

    const environments = ['dev', 'stage', 'prod'];

    let bucketName = $state('my-secure-logs-bucket');
    let region = $state('us-east-1');
    let environment = $state('prod');
    let ownerTag = $state('platform-team');
    let costCenterTag = $state('ENG-SRE');
    let forceDestroy = $state(false);
    let versioning = $state(true);
    let enforceSecureTransport = $state(true);
    let kmsKeyId = $state('');

    let includeBackend = $state(false);
    let backendBucket = $state('terraform-state-bucket');
    let backendKey = $state('s3/baseline/terraform.tfstate');
    let backendRegion = $state('us-east-1');
    let backendTable = $state('terraform_locks');

    let isSubmitting = $state(false);
    let error = $state<string | null>(null);
    let result = $state<{ filename: string; content: string } | null>(null);

    const buildPayload = (): AwsS3GeneratorPayload => ({
        bucket_name: bucketName,
        region,
        environment,
        owner_tag: ownerTag,
        cost_center_tag: costCenterTag,
        force_destroy: forceDestroy,
        versioning,
        enforce_secure_transport: enforceSecureTransport,
        kms_key_id: kmsKeyId || null,
        backend: includeBackend
            ? {
                  bucket: backendBucket,
                  key: backendKey,
                  region: backendRegion,
                  dynamodb_table: backendTable
              }
            : null
    });

    const handleSubmit = async (event: SubmitEvent) => {
        event.preventDefault();
        error = null;
        result = null;

        if (!bucketName.trim()) {
            error = 'Bucket name is required.';
            return;
        }

        if (includeBackend && (!backendBucket.trim() || !backendKey.trim() || !backendRegion.trim() || !backendTable.trim())) {
            error = 'Backend configuration requires bucket, key, region, and DynamoDB table.';
            return;
        }

        isSubmitting = true;
        try {
            result = await generateAwsS3(fetch, buildPayload());
        } catch (err) {
            error = err instanceof Error ? err.message : 'Failed to generate Terraform module.';
        } finally {
            isSubmitting = false;
        }
    };

    const copyToClipboard = async () => {
        if (!result) return;
        try {
            await navigator.clipboard.writeText(result.content);
            error = 'Copied to clipboard.';
        } catch (err) {
            error = err instanceof Error ? err.message : 'Unable to copy to clipboard.';
        }
    };

    const downloadFile = () => {
        if (!result) return;
        const blob = new Blob([result.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = result.filename;
        link.click();
        URL.revokeObjectURL(url);
    };
</script>

<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Blueprint Studio</p>
        <h2 class="text-3xl font-semibold text-white">AWS S3 secure baseline</h2>
        <p class="max-w-3xl text-sm text-slate-400">
            Generate a hardened S3 module with encryption, public access blocking, optional KMS keys, and secure transport
            enforcement. Additional generators will land here as the SvelteKit migration progresses.
        </p>
    </header>

    <form class="grid gap-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]" onsubmit={handleSubmit}>
        <div class="space-y-6">
            <div class="grid gap-4 md:grid-cols-2">
                <label class="space-y-2 text-sm font-medium text-slate-200">
                    <span>Bucket name</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        bind:value={bucketName}
                        placeholder="my-secure-logs-bucket"
                    />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-200">
                    <span>Region</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        bind:value={region}
                        placeholder="us-east-1"
                    />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-200">
                    <span>Environment</span>
                    <select
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        bind:value={environment}
                    >
                        {#each environments as env}
                            <option value={env}>{env}</option>
                        {/each}
                    </select>
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-200">
                    <span>Owner tag</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        bind:value={ownerTag}
                    />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-200">
                    <span>Cost center tag</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        bind:value={costCenterTag}
                    />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-200">
                    <span>KMS key ARN (optional)</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        bind:value={kmsKeyId}
                        placeholder="arn:aws:kms:..."
                    />
                </label>
            </div>

            <div class="grid gap-4 md:grid-cols-2">
                <label class="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-slate-200">
                    <input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={forceDestroy} />
                    <span class="flex-1">
                        <span class="font-semibold text-white">Enable force destroy</span>
                        <p class="text-xs text-slate-400">Use cautiously for non-production buckets.</p>
                    </span>
                </label>
                <label class="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-slate-200">
                    <input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={versioning} />
                    <span class="flex-1">
                        <span class="font-semibold text-white">Enable versioning</span>
                        <p class="text-xs text-slate-400">Protects against accidental deletion/overwrite.</p>
                    </span>
                </label>
                <label class="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-slate-200">
                    <input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={enforceSecureTransport} />
                    <span class="flex-1">
                        <span class="font-semibold text-white">Enforce TLS-only access</span>
                        <p class="text-xs text-slate-400">Adds bucket policy to block non-TLS requests.</p>
                    </span>
                </label>
                <label class="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-sm text-slate-200">
                    <input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={includeBackend} />
                    <span class="flex-1">
                        <span class="font-semibold text-white">Include remote state backend</span>
                        <p class="text-xs text-slate-400">Emits terraform backend "s3" block.</p>
                    </span>
                </label>
            </div>

            {#if includeBackend}
                <div class="grid gap-4 md:grid-cols-2">
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>State bucket</span>
                        <input
                            class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                            type="text"
                            bind:value={backendBucket}
                        />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>State key</span>
                        <input
                            class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                            type="text"
                            bind:value={backendKey}
                        />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>State region</span>
                        <input
                            class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                            type="text"
                            bind:value={backendRegion}
                        />
                    </label>
                    <label class="space-y-2 text-sm font-medium text-slate-200">
                        <span>DynamoDB lock table</span>
                        <input
                            class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                            type="text"
                            bind:value={backendTable}
                        />
                    </label>
                </div>
            {/if}

            {#if error}
                <div class="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-xs text-rose-100">{error}</div>
            {/if}

            <button
                class="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-900/40 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={isSubmitting}
            >
                {#if isSubmitting}
                    <span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
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
                    <li>• Public access block enforced for account-wide compliance.</li>
                    <li>• Server-side encryption defaults to AES256 or the supplied KMS key.</li>
                    <li>• Optional secure transport bucket policy guards against HTTP requests.</li>
                    <li>• Remote state backend is optional and disabled by default.</li>
                </ul>
            </div>

            {#if result}
                <div class="space-y-3 rounded-3xl border border-white/5 bg-slate-900/70 p-5">
                    <div class="flex items-center justify-between gap-3">
                        <div>
                            <p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Output</p>
                            <h4 class="text-sm font-semibold text-white">{result.filename}</h4>
                        </div>
                        <div class="flex gap-2">
                            <button
                                class="rounded-xl border border-white/10 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
                                type="button"
                                onclick={copyToClipboard}
                            >
                                Copy
                            </button>
                            <button
                                class="rounded-xl border border-white/10 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
                                type="button"
                                onclick={downloadFile}
                            >
                                Download
                            </button>
                        </div>
                    </div>
                    <pre class="max-h-96 overflow-auto rounded-2xl bg-slate-950/70 p-4 text-xs text-slate-200">{result.content}</pre>
                </div>
            {:else}
                <div class="rounded-3xl border border-dashed border-white/10 bg-slate-900/50 p-5 text-sm text-slate-400">
                    Generated Terraform will appear here once you submit the form.
                </div>
            {/if}
        </aside>
    </form>
</section>
