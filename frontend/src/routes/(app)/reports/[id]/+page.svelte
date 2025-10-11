<script lang="ts">
	import { env } from '$env/dynamic/public';
	import type { ReportDetail } from '$lib/api/client';

	const { data, params } = $props();
	const report = data.report as ReportDetail | null;
	const error = data.error as string | undefined;
	const apiBase = (env.PUBLIC_API_BASE ?? 'http://localhost:8787').replace(/\/$/, '');

	const severityEntries = report?.summary?.severity_counts
		? Object.entries(report.summary.severity_counts).map(([key, value]) => [key, Number(value ?? 0)] as [string, number]).sort((a, b) => b[1] - a[1])
		: [];

	const issuesFound = report?.summary?.issues_found ?? 0;
	const formatDate = (value?: string) => {
		if (!value) return '';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) {
			return value;
		}
		return date.toLocaleString();
	};
	const generatedAt = formatDate(report?.summary?.generated_at ?? report?.summary?.created_at);

	const findingCount = report?.findings?.length ?? 0;
</script>

<section class="space-y-6">
	<header class="space-y-2">
		<a class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500 hover:text-sky-300" href="/reports">
			← Back to reports
		</a>
		<h2 class="text-3xl font-semibold text-white">Report {params.id}</h2>
		<p class="max-w-2xl text-sm text-slate-400">
			Download artifacts or inspect severity trends from this run. The embedded findings table will land in a follow-up
			iteration utilising the existing FastAPI viewer endpoints.
		</p>
	</header>

	{#if error}
		<div class="rounded-3xl border border-rose-500/40 bg-rose-500/10 px-6 py-4 text-sm text-rose-100">
			<strong class="font-semibold">Unable to load report.</strong>
			<span class="ml-2 text-rose-100/80">{error}</span>
		</div>
	{/if}

	{#if report}
		<div class="space-y-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40">
			<div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
				<div class="flex flex-wrap gap-3 text-xs text-slate-400">
					<span class="rounded-xl border border-white/10 px-3 py-1">
						Findings: <strong class="text-slate-200">{findingCount}</strong>
					</span>
					<span class="rounded-xl border border-white/10 px-3 py-1">
						Issues tracked: <strong class="text-slate-200">{issuesFound}</strong>
					</span>
					{#if generatedAt}
						<span class="rounded-xl border border-white/10 px-3 py-1">
							Generated: <strong class="text-slate-200">{generatedAt}</strong>
						</span>
					{/if}
				</div>
				<div class="flex flex-wrap gap-2">
					<a
						class="rounded-2xl border border-white/10 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
						href={`${apiBase}/reports/${params.id}`}
						target="_blank"
						rel="noreferrer"
					>
						Download JSON
					</a>
					<a
						class="rounded-2xl border border-white/10 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
						href={`${apiBase}/reports/${params.id}/csv`}
					>
						Download CSV
					</a>
					<a
						class="rounded-2xl border border-white/10 px-4 py-2 text-xs font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white"
						href={`${apiBase}/reports/${params.id}/html`}
						target="_blank"
						rel="noreferrer"
					>
						Open HTML
					</a>
				</div>
			</div>

			<div class="grid gap-4 md:grid-cols-3">
				<div class="rounded-2xl border border-white/5 bg-slate-900/80 p-4">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Issues found</p>
					<p class="mt-3 text-4xl font-semibold text-white">{issuesFound}</p>
				</div>
				<div class="rounded-2xl border border-white/5 bg-slate-900/80 p-4">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Findings</p>
					<p class="mt-3 text-4xl font-semibold text-white">{findingCount}</p>
				</div>
				<div class="rounded-2xl border border-white/5 bg-slate-900/80 p-4">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Top severity</p>
					<p class="mt-3 text-2xl font-semibold text-white">
						{severityEntries.length ? severityEntries[0][0] : '—'}
					</p>
				</div>
			</div>

			<section class="space-y-3">
				<h3 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Severity breakdown</h3>
				{#if severityEntries.length}
					<div class="space-y-2">
						{#each severityEntries as [severity, count]}
							<div class="flex items-center gap-4 rounded-2xl border border-white/5 bg-slate-900/60 px-4 py-3 text-sm">
								<span class="w-28 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{severity}</span>
								<span class="flex-1 text-slate-200">{count}</span>
							</div>
						{/each}
					</div>
				{:else}
					<p class="rounded-2xl border border-white/5 bg-slate-900/60 px-4 py-3 text-sm text-slate-400">
						No severity counts recorded for this run.
					</p>
				{/if}
			</section>

			<div class="rounded-2xl border border-dashed border-slate-700/60 bg-slate-900/50 p-6 text-sm text-slate-300">
				<p class="font-medium text-slate-100">Findings preview</p>
				{#if findingCount}
					<p class="mt-2">
						Inline filtering and diff previews will surface here. In the interim, use the HTML button above or call
						<code class="rounded bg-slate-900/70 px-1 py-0.5 text-xs text-slate-200">GET /ui/reports/{params.id}/viewer</code> to interact with the
						legacy viewer.
					</p>
				{:else}
					<p class="mt-2">Great news—no active findings recorded for this run.</p>
				{/if}
			</div>
		</div>
	{:else if !error}
		<div class="rounded-3xl border border-white/5 bg-slate-950/80 px-6 py-6 text-sm text-slate-400">
			Loading report details...
		</div>
	{/if}
</section>
