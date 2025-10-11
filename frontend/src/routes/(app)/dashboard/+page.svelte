<script lang="ts">
	const { data } = $props();
	const stats = data.stats;
	const error = data.error as string | undefined;

	const severityEntries = stats
		? Object.entries(stats.severityCounts)
				.map(([key, value]) => [key, Number(value ?? 0)] as [string, number])
				.sort((a, b) => b[1] - a[1])
		: [];
	const lastReport = stats?.last;
	const lastSummary = lastReport?.summary;
	const topSeverityCount = severityEntries.length ? Math.max(severityEntries[0][1], 1) : 1;
</script>

<section class="space-y-8">
	<header class="flex flex-col gap-2">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Overview</p>
		<h2 class="text-3xl font-semibold text-white">Platform health</h2>
		<p class="max-w-2xl text-sm text-slate-400">
			High-level metrics pulled directly from the FastAPI reviewer. Counts update whenever new reports are stored via the
			CLI, Streamlit legacy UI, or this SvelteKit interface.
		</p>
	</header>

	{#if error}
		<div class="rounded-3xl border border-rose-500/40 bg-rose-500/10 px-6 py-4 text-sm text-rose-200">
			<strong class="font-semibold">Unable to load dashboard data.</strong>
			<span class="ml-2 text-rose-100/80">{error}</span>
		</div>
	{/if}

	{#if stats}
		<div class="grid gap-4 md:grid-cols-3">
			<div class="rounded-3xl border border-white/5 bg-slate-900/70 p-6 shadow-lg shadow-slate-950/40">
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Reports indexed</p>
				<p class="mt-4 text-4xl font-semibold text-white">{stats.reports}</p>
				<p class="mt-2 text-sm text-slate-400">
					Latest {Math.min(stats.reports, 20)} runs pulled from the reviewer database.
				</p>
			</div>
			<div class="rounded-3xl border border-white/5 bg-slate-900/70 p-6 shadow-lg shadow-slate-950/40">
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Top severity</p>
				{#if severityEntries.length}
					<p class="mt-4 text-4xl font-semibold text-white">{severityEntries[0][0]}</p>
					<p class="mt-2 text-sm text-slate-400">
						{severityEntries[0][1]} findings across recent reports.
					</p>
				{:else}
					<p class="mt-4 text-4xl font-semibold text-white">—</p>
					<p class="mt-2 text-sm text-slate-400">No findings recorded yet.</p>
				{/if}
			</div>
			<div class="rounded-3xl border border-white/5 bg-slate-900/70 p-6 shadow-lg shadow-slate-950/40">
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Last report</p>
				<p class="mt-4 text-2xl font-semibold text-white">
					{lastReport ? lastReport.id : 'Awaiting scan'}
				</p>
				<p class="mt-2 text-sm text-slate-400">
					{#if lastSummary}
						{lastSummary.issues_found ?? 0} issues • {Object.values(lastSummary.severity_counts ?? {}).reduce((sum, v) => sum + Number(v ?? 0), 0)} findings
					{:else}
						Run a scan to populate this view.
					{/if}
				</p>
			</div>
		</div>

		<section class="space-y-4">
			<header class="flex items-center justify-between">
				<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">Severity distribution</h3>
				{#if stats.reports > 0}
					<p class="text-xs text-slate-400">Aggregated across {stats.reports} report{stats.reports === 1 ? '' : 's'}.</p>
				{/if}
			</header>

			{#if severityEntries.length}
				<div class="space-y-3">
					{#each severityEntries as [severity, count]}
						<div class="flex items-center gap-4 rounded-2xl border border-white/5 bg-slate-900/60 px-4 py-3">
							<div class="w-32 text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">{severity}</div>
							<div class="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
								<div
									class="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600"
									style={`width: ${Math.min(100, (count / topSeverityCount) * 100)}%`}
								></div>
							</div>
							<div class="w-12 text-right font-semibold text-slate-200">{count}</div>
						</div>
					{/each}
				</div>
			{:else}
				<div class="rounded-3xl border border-white/5 bg-slate-950/70 px-6 py-6 text-sm text-slate-400">
					Run your first scan to populate severity trends.
				</div>
			{/if}
		</section>
	{:else if !error}
		<div class="rounded-3xl border border-white/5 bg-slate-950/70 px-6 py-6 text-sm text-slate-400">
			Fetching report metrics...
		</div>
	{/if}
</section>
