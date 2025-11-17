<script lang="ts">
	import { browser } from '$app/environment';
	import type { KnowledgeItem, ProjectDetail, ProjectSummary } from '$lib/api/client';
	import {
		buildProjectKnowledgeQuery,
		deriveProjectKnowledgeKeywords,
		fetchProjectKnowledge
	} from '$lib/api/knowledge';
	import { activeProjectLibrary } from '$lib/stores/project';

	const {
		project = null,
		limit = 3
	}: {
		project?: ProjectSummary | ProjectDetail | null;
		limit?: number;
	} = $props();

	const libraryAssets = $derived($activeProjectLibrary);
	const generatorSlugs = $derived(() => {
		const slugs = new Set<string>();
		for (const asset of libraryAssets) {
			for (const tag of asset.tags ?? []) {
				if (typeof tag === 'string' && tag.startsWith('generator:')) {
					slugs.add(tag.replace(/^generator:/, ''));
				}
			}
		}
		return Array.from(slugs);
	});

	let items = $state<KnowledgeItem[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let lastQuery = $state<string | null>(null);
	let keywords = $state<string[]>([]);
	let requestToken = 0;

	const encodePath = (path: string) =>
		path
			.split('/')
			.map((segment) => encodeURIComponent(segment))
			.join('/');

	const knowledgeHref = (item: KnowledgeItem) => `/knowledge/${encodePath(item.source)}`;

	const snippet = (text: string) => {
		const trimmed = text.trim();
		if (trimmed.length <= 320) {
			return trimmed;
		}
		return `${trimmed.slice(0, 320)}…`;
	};

	const refreshKnowledge = async () => {
		const context = { project, generatorSlugs };
		const query = buildProjectKnowledgeQuery(context);
		keywords = deriveProjectKnowledgeKeywords(context);
		lastQuery = query;

		if (!browser || !query) {
			items = [];
			error = null;
			loading = false;
			return;
		}

		const currentToken = ++requestToken;
		loading = true;
		error = null;
		try {
			const { items: results } = await fetchProjectKnowledge(fetch, context, limit);
			if (currentToken !== requestToken) {
				return;
			}
			items = results;
		} catch (err) {
			if (currentToken !== requestToken) {
				return;
			}
			const message = err instanceof Error ? err.message : 'Failed to load knowledge results.';
			error = message;
			items = [];
		} finally {
			if (currentToken === requestToken) {
				loading = false;
			}
		}
	};

	$effect(() => {
		void refreshKnowledge();
	});
</script>

<section class="space-y-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm shadow-slate-200/50">
	<header class="flex flex-wrap items-start justify-between gap-3">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Contextual knowledge</p>
			<p class="text-sm text-slate-500">
				Suggested remediation articles based on this project’s metadata, generator history, and tags.
			</p>
		</div>
		<a
			class="inline-flex items-center rounded-2xl border border-slate-200 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500 transition hover:border-sky-200 hover:text-sky-600"
			href={lastQuery ? `/knowledge?q=${encodeURIComponent(lastQuery)}` : '/knowledge'}
		>
			Open knowledge base
		</a>
	</header>

	{#if !keywords.length}
		<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
			Add project metadata or promote generator outputs to the library to unlock tailored knowledge suggestions.
		</p>
	{:else if error}
		<p class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-600">{error}</p>
	{:else if loading && items.length === 0}
		<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">Loading knowledge…</p>
	{:else if items.length === 0}
		<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
			No relevant documents found for {keywords.join(', ')}. Try saving more generator outputs or adjusting metadata.
		</p>
	{:else}
		<ul class="space-y-3">
			{#each items as item (item.source)}
				<li class="space-y-2 rounded-2xl border border-slate-200 bg-slate-50 p-4">
					<div class="flex flex-wrap items-center justify-between gap-3">
						<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{item.source}</p>
						<a
							class="inline-flex items-center rounded-xl border border-sky-200 px-3 py-1 text-[0.65rem] font-semibold text-sky-600 transition hover:bg-sky-500 hover:text-white"
							href={knowledgeHref(item)}
							target="_blank"
							rel="noreferrer"
						>
							View doc
						</a>
					</div>
					<p class="text-xs text-slate-600">{snippet(item.content)}</p>
				</li>
			{/each}
		</ul>
	{/if}

	{#if keywords.length}
		<div class="flex flex-wrap gap-2">
			{#each keywords as keyword (keyword)}
				<span class="rounded-full border border-slate-200 bg-white px-3 py-1 text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-slate-400">
					{keyword}
				</span>
			{/each}
			{#if loading}
				<span class="rounded-full border border-slate-200 px-3 py-1 text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-slate-400">
					Loading…
				</span>
			{/if}
		</div>
	{/if}
</section>
