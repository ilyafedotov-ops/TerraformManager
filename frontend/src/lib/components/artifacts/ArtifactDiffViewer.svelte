<script lang="ts">
	import type { Diff } from 'diff-match-patch';
	import DiffMatchPatch from 'diff-match-patch';

	type DiffChunk = Diff;

	const {
		currentKey = 'A',
		currentContent = null,
		previousKey = 'B',
		previousContent = null,
		loading = false,
		error = null
	} = $props<{
		currentKey?: string;
		currentContent?: string | null;
		previousKey?: string;
		previousContent?: string | null;
		loading?: boolean;
		error?: string | null;
	}>();

	let diffChunks = $state<DiffChunk[]>([]);

	const computeDiff = () => {
		if (!currentContent || !previousContent) {
			diffChunks = [];
			return;
		}
		const dmp = new DiffMatchPatch();
		const diffs = dmp.diff_main(previousContent, currentContent);
		dmp.diff_cleanupSemantic(diffs);
		diffChunks = diffs;
	};

	$effect(() => {
		computeDiff();
	});
</script>

<div class="space-y-3">
	<div class="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
		<span>Diff {previousKey} → {currentKey}</span>
		{#if loading}
			<span class="rounded-full border border-slate-200 px-2 py-[2px] text-[0.6rem] text-slate-500">Loading…</span>
		{/if}
	</div>
	{#if error}
		<p class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-600">{error}</p>
	{:else if !currentContent || !previousContent}
		<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-500">
			{#if !currentContent}
				Preview the artifact to generate a diff.
			{:else}
				No previous run available for comparison.
			{/if}
		</p>
	{:else if !diffChunks.length}
		<p class="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs text-emerald-600">
			No differences detected between the selected runs.
		</p>
	{:else}
		<pre class="overflow-auto rounded-2xl border border-slate-200 bg-slate-50 p-3 font-mono text-[0.75rem] leading-relaxed">
			{#each diffChunks as [type, text], _index}
				<span
					class={type === 0
						? 'text-slate-700'
						: type === 1
						? 'bg-emerald-50 text-emerald-700'
						: 'bg-rose-50 text-rose-700'}
				>
					{text}
				</span>
			{/each}
		</pre>
	{/if}
</div>
