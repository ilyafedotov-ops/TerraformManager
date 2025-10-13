<script lang="ts">
    import { API_BASE, syncKnowledge, type KnowledgeItem, type KnowledgeSyncResult } from '$lib/api/client';
    import { goto } from '$app/navigation';
    import { notifyError, notifySuccess } from '$lib/stores/notifications';
    import KnowledgeResults from '$lib/components/knowledge/KnowledgeResults.svelte';
    import KnowledgeSyncForm from '$lib/components/knowledge/KnowledgeSyncForm.svelte';

    const { data } = $props();
    let query = $state<string>(data.query ?? 'terraform security best practices');
    let topK = $state<number>(data.topK ?? 3);
    let results = $state<KnowledgeItem[]>(data.items ?? []);
    let error = $state<string | null>(data.error ?? null);
    let isSearching = $state(false);
    const token = data.token as string | null;

    let syncSources = $state<string>('https://github.com/hashicorp/policy-library-azure-storage-terraform');
    let syncResults = $state<KnowledgeSyncResult[]>([]);
    let syncStatus = $state<string | null>(null);
    let isSyncing = $state(false);

    const runSearch = async (event?: SubmitEvent) => {
        event?.preventDefault();
        error = null;
        isSearching = true;
        try {
            const response = await fetch(
                `${API_BASE}/knowledge/search?q=${encodeURIComponent(query)}&top_k=${Math.min(Math.max(topK, 1), 10)}`
            );
            if (!response.ok) {
                const detail = await response.text();
                throw new Error(detail || `Request failed (${response.status})`);
            }
            const payload = (await response.json()) as { items: KnowledgeItem[] };
            results = payload.items;
            const url = new URL(window.location.href);
            url.searchParams.set('q', query);
            url.searchParams.set('top_k', String(topK));
            await goto(`${url.pathname}${url.search}`, {
                replaceState: true,
                keepFocus: true,
                noScroll: true
            });
        } catch (err) {
            const message = err instanceof Error ? err.message : 'Unable to fetch knowledge results.';
            error = message;
            notifyError(message);
        } finally {
            isSearching = false;
        }
    };

    const parseSources = (): string[] =>
        syncSources
            .split(/\r?\n|,/)
            .map((src) => src.trim())
            .filter(Boolean);

    const runSync = async () => {
        syncStatus = null;
        syncResults = [];
        if (!token) {
            syncStatus = 'API token required to run knowledge sync.';
            notifyError(syncStatus);
            return;
        }
        const sources = parseSources();
        if (!sources.length) {
            syncStatus = 'Provide at least one GitHub repository URL.';
            notifyError(syncStatus);
            return;
        }
        isSyncing = true;
        try {
            syncResults = await syncKnowledge(fetch, token, sources);
            syncStatus = 'Knowledge sync completed.';
            notifySuccess(`Knowledge sync completed for ${syncResults.length} source${syncResults.length === 1 ? '' : 's'}.`);
        } catch (err) {
            syncStatus = err instanceof Error ? err.message : 'Knowledge sync failed.';
            notifyError(syncStatus);
        } finally {
            isSyncing = false;
        }
    };
</script>

<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Knowledge base</p>
        <h2 class="text-3xl font-semibold text-slate-700">Search internal remediation guides</h2>
        <p class="max-w-3xl text-sm text-slate-500">
            Results are served by the Python RAG index (`backend.rag`). Use this tool to surface best practices, remediation
            snippets, and architectural context while triaging reviewer findings.
        </p>
    </header>

    <div class="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
        <form class="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,220px)]" onsubmit={runSearch}>
            <label class="block space-y-2 text-sm font-medium text-slate-600">
                <span class="uppercase tracking-[0.3em] text-slate-400">Search term</span>
                <input
                    class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    type="search"
                    placeholder="e.g. AWS S3 encryption, Azure diagnostics"
                    bind:value={query}
                    name="q"
                />
            </label>
            <label class="block space-y-2 text-sm font-medium text-slate-600">
                <span class="uppercase tracking-[0.3em] text-slate-400">Top results</span>
                <input
                    class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    type="number"
                    min="1"
                    max="10"
                    bind:value={topK}
                    name="top_k"
                />
            </label>
            <div class="md:col-span-2 flex flex-wrap items-center justify-between gap-3">
                {#if error}
                    <div class="rounded-xl border border-rose-300 bg-rose-50 px-4 py-2 text-xs text-rose-700">
                        {error}
                    </div>
                {/if}
                <button
                    class="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-md shadow-sky-300/50 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
                    type="submit"
                    disabled={isSearching}
                >
                    {#if isSearching}
                        <span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                        Searching…
                    {:else}
                        Search knowledge
                    {/if}
                </button>
            </div>
        </form>

        <section class="space-y-4">
            <header class="flex items-center justify-between">
                <h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Results</h3>
                <p class="text-xs text-slate-400">Showing {results.length} matched documents.</p>
            </header>

            <KnowledgeResults items={results} error={error} />
        </section>

        <KnowledgeSyncForm
            bind:sources={syncSources}
            status={syncStatus}
            results={syncResults}
            isSyncing={isSyncing}
            tokenPresent={Boolean(token)}
            on:sync={runSync}
        />
    </div>
</section>
