<script lang="ts">
	const reports = [
		{ id: 'demo-001', created: '—', severity: 'pending', issues: 0 },
		{ id: 'demo-002', created: '—', severity: 'pending', issues: 0 }
	];
</script>

<section class="space-y-8">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Reports</p>
		<h2 class="text-3xl font-semibold text-white">Saved reviewer results</h2>
		<p class="max-w-3xl text-sm text-slate-400">
			This table will hydrate from the FastAPI `/reports` endpoint and support filtering, export, and direct navigation
			to the embedded report viewer.
		</p>
	</header>

	<div class="overflow-hidden rounded-3xl border border-white/5 bg-slate-950/70 shadow-xl shadow-slate-950/40">
		<table class="min-w-full divide-y divide-white/5 text-sm">
			<thead class="bg-slate-900/70 text-xs uppercase tracking-[0.3em] text-slate-500">
				<tr>
					<th class="px-6 py-4 text-left">Report ID</th>
					<th class="px-6 py-4 text-left">Created</th>
					<th class="px-6 py-4 text-left">Severity</th>
					<th class="px-6 py-4 text-left">Issues</th>
					<th class="px-6 py-4 text-right">Actions</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-white/5 text-slate-300">
				{#each reports as report}
					<tr class="hover:bg-slate-900/60">
						<td class="px-6 py-4 font-mono text-sm text-slate-200">{report.id}</td>
						<td class="px-6 py-4">{report.created}</td>
						<td class="px-6 py-4 uppercase tracking-[0.2em] text-slate-400">{report.severity}</td>
						<td class="px-6 py-4">{report.issues}</td>
						<td class="px-6 py-4 text-right">
							<a
								class="inline-flex items-center gap-2 rounded-xl bg-sky-500/10 px-4 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-500/20"
								href={`/reports/${report.id}`}
							>
								View
							</a>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</section>
