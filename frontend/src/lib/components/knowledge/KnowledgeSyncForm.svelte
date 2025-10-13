<script lang="ts">
import type { KnowledgeSyncResult } from '$lib/api/client';
import { createEventDispatcher } from 'svelte';

/**
 * Form controls for syncing external knowledge repositories and displaying outcomes.
 */
export let sources: string;
export let isSyncing = false;
export let status: string | null = null;
export let results: KnowledgeSyncResult[] = [];
export let tokenPresent = false;

const dispatch = createEventDispatcher<{ sync: void }>();
const handleSubmit = () => dispatch('sync');
</script>

<section class="space-y-4 rounded-3xl border border-slate-200 bg-white p-5">
	<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Sync external sources</h3>
	<p class="text-xs text-slate-500">
		Pull Markdown documentation from GitHub repositories (public or accessible with configured credentials). Each
		repository is cloned as a ZIP and stored under
		<code class="rounded bg-white px-1 py-0.5 text-xs text-slate-600">knowledge/external</code>.
	</p>
	<label class="block space-y-2 text-xs font-medium text-slate-600">
		<span>Repositories (one per line)</span>
		<textarea
			class="h-24 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
			bind:value={sources}
			placeholder="https://github.com/hashicorp/policy-library-azure-storage-terraform"
		></textarea>
	</label>
	{#if status}
		<div class="rounded-2xl border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600">{status}</div>
	{/if}
	<button
		class="inline-flex items-center gap-2 rounded-2xl border border-sky-200 px-4 py-2 text-xs font-semibold text-sky-600 transition hover:bg-sky-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
		type="button"
		onclick={handleSubmit}
		disabled={isSyncing || !tokenPresent}
	>
		{#if isSyncing}
			<span class="h-4 w-4 animate-spin rounded-full border-2 border-sky-200 border-t-transparent"></span>
			Syncing…
		{:else}
			Run sync
		{/if}
	</button>
	{#if !tokenPresent}
		<p class="text-xs text-rose-500">API token required to run knowledge sync.</p>
	{/if}

	{#if results.length}
		<div class="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
			<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
				Synced repositories ({results.length})
			</h4>
			<ul class="space-y-2 text-xs text-slate-600">
				{#each results as item (item.source)}
					<li class="flex flex-col gap-1 rounded-xl border border-slate-200 bg-white px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
						<span class="break-all font-mono text-[0.7rem] text-slate-500">{item.source}</span>
						<span class="text-[0.65rem] uppercase tracking-[0.2em] text-slate-400">
							{item.files.length} file{item.files.length === 1 ? '' : 's'}
						</span>
					</li>
				{/each}
			</ul>
		</div>
	{/if}
</section>
