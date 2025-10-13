<script lang="ts">
import type { KnowledgeItem } from '$lib/api/client';

/**
 * List search results from the knowledge base with quick metadata links.
 */
export let items: KnowledgeItem[] = [];
export let error: string | null = null;

const encodePath = (path: string) =>
	path
		.split('/')
		.map((segment) => encodeURIComponent(segment))
		.join('/');

const knowledgeHref = (item: KnowledgeItem) => `/knowledge/${encodePath(item.source)}`;
</script>

{#if error}
	<p class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">{error}</p>
{:else if items.length === 0}
	<p class="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
		No documents matched. Broaden the query or add new Markdown files under
		<code class="rounded bg-white px-1 py-0.5 text-xs text-slate-600">knowledge/</code> then run
		<code class="rounded bg-white px-1 py-0.5 text-xs text-slate-600">python -m backend.cli reindex</code>.
	</p>
{:else}
	<ul class="space-y-4" data-testid="knowledge-results">
		{#each items as item (item.source)}
			<li class="space-y-3 rounded-2xl border border-slate-200 bg-white p-5">
				<div class="flex flex-wrap items-center justify-between gap-3">
					<div class="min-w-0">
						<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{item.source}</p>
						<p class="text-xs text-slate-400">Score: {item.score.toFixed(2)}</p>
					</div>
					<a
						class="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-sky-200 px-3 py-2 text-xs font-semibold text-sky-600 transition hover:bg-sky-500 hover:text-white sm:w-auto"
						href={knowledgeHref(item)}
						target="_blank"
						rel="noreferrer"
					>
						Open markdown
					</a>
				</div>
				<pre class="overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-xs text-slate-600">
{item.content}</pre
				>
			</li>
		{/each}
	</ul>
{/if}
