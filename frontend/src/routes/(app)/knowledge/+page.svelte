<script lang="ts">
    import { API_BASE, type KnowledgeItem } from '$lib/api/client';

    const { data } = $props();
    let query = $state<string>(data.query ?? 'terraform security best practices');
    let topK = $state<number>(data.topK ?? 3);
    let results = $state<KnowledgeItem[]>(data.items ?? []);
    let error = $state<string | null>(data.error ?? null);
    let isSearching = $state(false);

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
            window.history.replaceState(window.history.state, '', url.toString());
        } catch (err) {
            error = err instanceof Error ? err.message : 'Unable to fetch knowledge results.';
        } finally {
            isSearching = false;
        }
    };

    const previewContent = (item: KnowledgeItem) => item.content;
    const knowledgeHref = (item: KnowledgeItem) => `/knowledge/${item.source}`;
</script>

<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Knowledge base</p>
        <h2 class="text-3xl font-semibold text-white">Search internal remediation guides</h2>
        <p class="max-w-3xl text-sm text-slate-400">
            Results are served by the Python RAG index (`backend.rag`). Use this tool to surface best practices, remediation
            snippets, and architectural context while triaging reviewer findings.
        </p>
    </header>

    <div class="space-y-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40">
        <form class="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,220px)]" onsubmit={runSearch}>
            <label class="block space-y-2 text-sm font-medium text-slate-200">
                <span class="uppercase tracking-[0.3em] text-slate-500">Search term</span>
                <input
                    class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                    type="search"
                    placeholder="e.g. AWS S3 encryption, Azure diagnostics"
                    bind:value={query}
                    name="q"
                />
            </label>
            <label class="block space-y-2 text-sm font-medium text-slate-200">
                <span class="uppercase tracking-[0.3em] text-slate-500">Top results</span>
                <input
                    class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                    type="number"
                    min="1"
                    max="10"
                    bind:value={topK}
                    name="top_k"
                />
            </label>
            <div class="md:col-span-2 flex flex-wrap items-center justify-between gap-3">
                {#if error}
                    <div class="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-xs text-rose-100">
                        {error}
                    </div>
                {/if}
                <button
                    class="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-md shadow-sky-900/40 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:cursor-not-allowed disabled:opacity-60"
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
                <h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">Results</h3>
                <p class="text-xs text-slate-500">Showing {results.length} matched documents.</p>
            </header>

            {#if results.length === 0 && !error}
                <p class="rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-sm text-slate-400">
                    No documents matched. Broaden the query or add new Markdown files under <code class="rounded bg-slate-900/70 px-1 py-0.5 text-xs text-slate-200">knowledge/</code> then run
                    <code class="rounded bg-slate-900/70 px-1 py-0.5 text-xs text-slate-200">python -m backend.cli reindex</code>.
                </p>
            {:else}
                <ul class="space-y-4">
                    {#each results as item (item.source)}
                        <li class="space-y-3 rounded-2xl border border-white/5 bg-slate-900/70 p-5">
                            <div class="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">{item.source}</p>
                                    <p class="text-xs text-slate-500">Score: {item.score.toFixed(2)}</p>
                                </div>
                                <a
                                    class="inline-flex items-center gap-2 rounded-xl border border-white/10 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
                                    href={knowledgeHref(item)}
                                    target="_blank"
                                    rel="noreferrer"
                                >
                                    Open markdown
                                </a>
                            </div>
                            <pre class="overflow-auto whitespace-pre-wrap rounded-xl bg-slate-950/70 p-4 text-xs text-slate-200">{previewContent(item)}</pre>
                        </li>
                    {/each}
                </ul>
            {/if}
        </section>
    </div>
</section>
