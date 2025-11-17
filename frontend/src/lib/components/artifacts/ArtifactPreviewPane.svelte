<script lang="ts">
	export let label = 'Preview';
	export let content: string | null = null;
	export let loading = false;
	export let error: string | null = null;
</script>

<section class="space-y-2">
	<div class="flex items-center justify-between">
		<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{label}</p>
		{#if loading}
			<span class="text-[0.6rem] font-semibold uppercase tracking-[0.2em] text-slate-400">Loading…</span>
		{/if}
	</div>
	{#if error}
		<p class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-600">
			{error}
		</p>
	{:else if !content}
		<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-500">
			No preview available. Select a file to load its contents.
		</p>
	{:else}
		<pre class="max-h-96 overflow-auto rounded-2xl border border-slate-200 bg-slate-50 p-4 font-mono text-[0.75rem] text-slate-700">{content}</pre>
	{/if}
</section>
