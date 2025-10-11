<script lang="ts">
    import { API_BASE } from '$lib/api/client';

    const { data } = $props();
    const token = data.token as string | null;

    let files = $state<FileList | null>(null);
    let terraformValidate = $state(false);
    let saveReport = $state(true);
    let isSubmitting = $state(false);
    let error = $state<string | null>(null);
    let result = $state<{ id?: string | null; summary?: Record<string, unknown>; report?: Record<string, unknown> } | null>(null);

    const submitScan = async (event: SubmitEvent) => {
        event.preventDefault();
        error = null;
        result = null;

        if (!token) {
            error = 'API token missing. Sign in to generate one or configure TFM_API_TOKEN on the server.';
            return;
        }
        if (!files || files.length === 0) {
            error = 'Attach at least one .tf or .zip file to scan.';
            return;
        }

        const formData = new FormData();
        Array.from(files).forEach((file) => formData.append('files', file));
        formData.append('terraform_validate', terraformValidate ? 'true' : 'false');
        formData.append('save', saveReport ? 'true' : 'false');

        isSubmitting = true;
        try {
            const response = await fetch(`${API_BASE}/scan/upload`, {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${token}`
                },
                body: formData
            });
            if (!response.ok) {
                const detail = await response.text();
                throw new Error(detail || `Scan failed with status ${response.status}`);
            }
            result = await response.json();
        } catch (err) {
            error = err instanceof Error ? err.message : 'Unexpected error while running scan';
        } finally {
            isSubmitting = false;
        }
    };

    const severityEntries = () => {
        const summary = result?.summary as { severity_counts?: Record<string, number> } | undefined;
        const counts = summary?.severity_counts;
        if (!counts) return [] as Array<[string, number]>;
        return Object.entries(counts).map(([sev, count]) => [sev, Number(count ?? 0)] as [string, number]);
    };
</script>

<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Reviewer</p>
        <h2 class="text-3xl font-semibold text-white">Upload Terraform for analysis</h2>
        <p class="max-w-3xl text-sm text-slate-400">
            Drop one or more Terraform modules (individual <code class="rounded bg-slate-900/70 px-1 py-0.5 text-xs text-slate-200">.tf</code> files or zipped directories).
            The backend will unpack archives, apply the configured review rules, and optionally persist the report for later lookup.
        </p>
    </header>

    <form class="space-y-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40" onsubmit={submitScan}>
        <div class="space-y-4">
            <label class="block text-sm font-semibold text-slate-200">
                <span class="uppercase tracking-[0.3em] text-slate-500">Terraform files / archives</span>
                <input
                    class="mt-2 w-full cursor-pointer rounded-2xl border border-dashed border-sky-500/40 bg-slate-900/60 px-4 py-6 text-sm text-slate-300 transition hover:border-sky-400 hover:bg-slate-900/70"
                    type="file"
                    multiple
                    accept=".tf,.zip"
                    bind:files
                    aria-label="Terraform files or zip archives"
                />
            </label>

            <div class="grid gap-4 md:grid-cols-2">
                <label class="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-sm text-slate-200">
                    <input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/60" type="checkbox" bind:checked={terraformValidate} />
                    <span>
                        <span class="font-semibold text-white">Run <code class="rounded bg-slate-800 px-1 py-0.5 text-xs text-slate-200">terraform validate</code></span>
                        <span class="block text-xs text-slate-400">Requires terraform binary on the API host.</span>
                    </span>
                </label>
                <label class="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-sm text-slate-200">
                    <input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/60" type="checkbox" bind:checked={saveReport} />
                    <span>
                        <span class="font-semibold text-white">Store report in database</span>
                        <span class="block text-xs text-slate-400">Enables follow-up review from the Reports tab.</span>
                    </span>
                </label>
            </div>
        </div>

        {#if error}
            <div class="rounded-2xl border border-rose-500/50 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                {error}
            </div>
        {/if}

        <button
            class="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-900/40 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={isSubmitting}
        >
            {#if isSubmitting}
                <span class="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-transparent"></span>
                Running scan…
            {:else}
                Run scan
            {/if}
        </button>
    </form>

    {#if result}
        <section class="space-y-4 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40">
            <header class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Scan summary</p>
                    <h3 class="text-xl font-semibold text-white">{result.id ?? 'Unsaved result'}</h3>
                </div>
                {#if result.id}
                    <div class="flex flex-wrap gap-2">
                        <a
                            class="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
                            href={`${API_BASE}/reports/${result.id}`}
                            target="_blank"
                            rel="noreferrer"
                        >
                            JSON
                        </a>
                        <a
                            class="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
                            href={`${API_BASE}/reports/${result.id}/csv`}
                        >
                            CSV
                        </a>
                        <a
                            class="rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
                            href={`${API_BASE}/reports/${result.id}/html`}
                            target="_blank"
                            rel="noreferrer"
                        >
                            HTML
                        </a>
                    </div>
                {/if}
            </header>

            <div class="grid gap-4 md:grid-cols-3">
                <div class="rounded-2xl border border-white/5 bg-slate-900/70 p-4">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Issues found</p>
                    <p class="mt-3 text-3xl font-semibold text-white">{(result.summary as { issues_found?: number })?.issues_found ?? 0}</p>
                </div>
                <div class="rounded-2xl border border-white/5 bg-slate-900/70 p-4">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Waived</p>
                    <p class="mt-3 text-3xl font-semibold text-white">{(result.report as { waived_findings?: unknown[] })?.waived_findings?.length ?? 0}</p>
                </div>
                <div class="rounded-2xl border border-white/5 bg-slate-900/70 p-4">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Files scanned</p>
                    <p class="mt-3 text-3xl font-semibold text-white">{(result.summary as { files_scanned?: number })?.files_scanned ?? 0}</p>
                </div>
            </div>

            <section class="space-y-2">
                <h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Severity distribution</h4>
                {#if severityEntries().length}
                    <ul class="space-y-2 text-sm text-slate-200">
                        {#each severityEntries() as [severity, count]}
                            <li class="flex items-center justify-between rounded-xl border border-white/5 bg-slate-900/60 px-4 py-2">
                                <span class="uppercase tracking-[0.2em] text-slate-400">{severity}</span>
                                <span class="font-semibold">{count}</span>
                            </li>
                        {/each}
                    </ul>
                {:else}
                    <p class="rounded-xl border border-white/5 bg-slate-900/60 px-4 py-3 text-sm text-slate-400">
                        No severity counts reported.
                    </p>
                {/if}
            </section>

            <details class="rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-sm text-slate-300">
                <summary class="cursor-pointer text-slate-200 focus:outline-none">Raw summary payload</summary>
                <pre class="mt-3 overflow-auto rounded-xl bg-slate-950/80 p-3 text-xs text-slate-200">{JSON.stringify(result.summary, null, 2)}</pre>
            </details>
        </section>
    {/if}
</section>
