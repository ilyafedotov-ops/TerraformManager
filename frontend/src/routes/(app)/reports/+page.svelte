<script lang="ts">
	import { env } from '$env/dynamic/public';
	import type { ReportSummary } from '$lib/api/client';

	const { data } = $props();
	const reports = data.reports as ReportSummary[];
	const error = data.error as string | undefined;

	const apiBase = (env.PUBLIC_API_BASE ?? 'http://localhost:8787').replace(/\/$/, '');

	const formatDate = (value?: string) => {
		if (!value) return '—';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return value;
		return date.toLocaleString();
	};

	const severityLabel = (summary?: ReportSummary['summary']) => {
		const counts = summary?.severity_counts;
		if (!counts) return '—';
		const [severity] =
			Object.entries(counts)
				.map(([key, value]) => [key, Number(value ?? 0)] as [string, number])
				.sort((a, b) => b[1] - a[1])[0] ?? [];
		return severity ?? '—';
	};

	const issuesCount = (summary?: ReportSummary['summary']) => summary?.issues_found ?? 0;
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

	{#if error}
		<div class="rounded-3xl border border-rose-500/40 bg-rose-500/10 px-6 py-4 text-sm text-rose-200">
			<strong class="font-semibold">Failed to load reports.</strong>
			<span class="ml-2 text-rose-100/80">{error}</span>
		</div>
	{/if}

	{#if reports.length}
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
							<td class="px-6 py-4">{formatDate(report.created_at)}</td>
							<td class="px-6 py-4 uppercase tracking-[0.2em] text-slate-400">{severityLabel(report.summary)}</td>
							<td class="px-6 py-4">{issuesCount(report.summary)}</td>
							<td class="px-6 py-4 text-right">
								<div class="flex flex-wrap justify-end gap-2">
									<a
										class="inline-flex items-center gap-2 rounded-xl bg-sky-500/10 px-4 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-500/20"
										href={`/reports/${report.id}`}
									>
										View
									</a>
									<a
										class="inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
										href={`${apiBase}/reports/${report.id}`}
										target="_blank"
										rel="noreferrer"
									>
										JSON
									</a>
									<a
										class="inline-flex items-center gap-2 rounded-xl border border-white/10 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
										href={`${apiBase}/reports/${report.id}/csv`}
									>
										CSV
									</a>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else if !error}
		<div class="rounded-3xl border border-white/5 bg-slate-950/70 px-6 py-6 text-sm text-slate-400">
			No reports saved yet. Run <code class="rounded bg-slate-900/70 px-1 py-0.5 text-xs text-slate-200">python -m backend.cli scan sample --out tmp/report.json</code> to generate one.
		</div>
	{/if}
</section>
