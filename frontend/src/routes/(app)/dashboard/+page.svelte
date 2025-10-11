<script lang="ts">
	const cards = [
		{ title: 'Reports', value: '0', description: 'Saved scan summaries' },
		{ title: 'Knowledge Docs', value: '0', description: 'Markdown references indexed' },
		{ title: 'Last Scan', value: '—', description: 'Severity snapshot pending API wiring' }
	];
</script>

<section class="space-y-8">
	<header class="flex flex-col gap-2">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Overview</p>
		<h2 class="text-3xl font-semibold text-white">Platform health</h2>
		<p class="max-w-2xl text-sm text-slate-400">
			This dashboard will surface real-time reviewer throughput, severity trends, and knowledge-index coverage once the
			new SvelteKit frontend is connected to the FastAPI backend.
		</p>
	</header>

	<div class="grid gap-4 md:grid-cols-3">
		{#each cards as card}
			<div class="rounded-3xl border border-white/5 bg-slate-900/70 p-6 shadow-lg shadow-slate-950/40">
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">{card.title}</p>
				<p class="mt-4 text-4xl font-semibold text-white">{card.value}</p>
				<p class="mt-2 text-sm text-slate-400">{card.description}</p>
			</div>
		{/each}
	</div>
</section>
