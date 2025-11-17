<script lang="ts">
import { deleteReport, type ReportDetail, ApiError } from '$lib/api/client';
import ReportActions from '$lib/components/reports/ReportActions.svelte';
import RunArtifactsPanel from '$lib/components/projects/RunArtifactsPanel.svelte';
import ProjectWorkspaceBanner from '$lib/components/projects/ProjectWorkspaceBanner.svelte';
	import { notifyError, notifySuccess } from '$lib/stores/notifications';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';

	const { data, params } = $props();
	const report = data.report as ReportDetail | null;
	const error = data.error as string | undefined;
	const token = data.token as string | null;
	const projectReportsHref = `/projects/${params.projectId}/reports`;
	let deleting = $state(false);
	let deleteError = $state<string | null>(null);

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
	const costSummary = report?.summary?.cost ?? report?.cost?.summary ?? null;
	const costDetails = report?.cost ?? null;
	const costCurrency = costSummary?.currency ?? costDetails?.currency ?? null;
	const costProjects = costDetails?.projects ?? [];
	const costErrors = costDetails?.errors ?? [];
	const hasCost = Boolean(costSummary || costProjects.length || costErrors.length);
	const totalMonthlyCost = costSummary?.total_monthly_cost ?? null;
	const diffMonthlyCost = costSummary?.diff_monthly_cost ?? null;
	const totalHourlyCost = costSummary?.total_hourly_cost ?? null;
	const diffHourlyCost = costSummary?.diff_hourly_cost ?? null;

	const formatCurrency = (value: number | null | undefined) => {
		if (value === null || value === undefined) return '—';
		if (!costCurrency) return value.toFixed(2);
		try {
			return new Intl.NumberFormat(undefined, { style: 'currency', currency: costCurrency }).format(value);
		} catch (error) {
			return `${costCurrency} ${value.toFixed(2)}`;
		}
	};

	const driftDetails = report?.drift ?? null;
	const driftSummary = report?.summary?.drift ?? driftDetails ?? null;
	const driftCounts = driftSummary?.counts ?? {};
	const driftCountEntries = Object.entries(driftCounts).filter(([, value]) => Number(value ?? 0) > 0);
const driftResourceChanges = driftDetails?.resource_changes ?? [];
const driftOutputChanges = driftDetails?.output_changes ?? [];
const driftError = driftDetails?.error ?? null;
const driftHasChanges = Boolean(driftSummary?.has_changes);
const findings = Array.isArray(report?.findings) ? report?.findings ?? [] : [];
const displayedFindings = findings.slice(0, 50);

	const handleDelete = async () => {
		if (!token) {
			deleteError = 'Missing API token; cannot delete report.';
			return;
		}
		if (browser) {
			const confirmed = window.confirm(`Delete report ${params.id}? This action cannot be undone.`);
			if (!confirmed) {
				return;
			}
		}
		deleting = true;
		deleteError = null;
		try {
			await deleteReport(fetch, token, params.id);
			notifySuccess(`Report ${params.id} deleted.`);
		await goto(projectReportsHref);
		} catch (err) {
			let message = 'Failed to delete report.';
			if (err instanceof ApiError) {
				const detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
				message = detail ? `${err.message}: ${detail}` : err.message;
			} else if (err instanceof Error) {
				message = err.message;
			}
			deleteError = message;
			notifyError(message);
		} finally {
			deleting = false;
		}
	};
</script>

<section class="space-y-6">
	<header class="space-y-2">
		<a class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400 hover:text-sky-500" href={projectReportsHref}>
			← Back to reports
		</a>
		<h2 class="text-3xl font-semibold text-slate-700">Report {params.id}</h2>
		<p class="max-w-2xl text-sm text-slate-500">
			Download artifacts or inspect severity trends from this run. The embedded findings table will land in a follow-up
			iteration utilising the existing FastAPI viewer endpoints.
		</p>
	</header>

	{#if error}
		<div class="rounded-3xl border border-rose-300 bg-rose-50 px-6 py-4 text-sm text-rose-700">
			<strong class="font-semibold">Unable to load report.</strong>
			<span class="ml-2 text-rose-600">{error}</span>
		</div>
	{/if}

	<ProjectWorkspaceBanner context="Correlate this report with workspace runs to access linked artifacts and history." />

	{#if report}
		<div class="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
			<div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
				<div class="flex flex-wrap gap-3 text-xs text-slate-500">
					<span class="rounded-xl border border-slate-200 px-3 py-1">
						Findings: <strong class="text-slate-600">{findingCount}</strong>
					</span>
					<span class="rounded-xl border border-slate-200 px-3 py-1">
						Issues tracked: <strong class="text-slate-600">{issuesFound}</strong>
					</span>
					{#if generatedAt}
						<span class="rounded-xl border border-slate-200 px-3 py-1">
							Generated: <strong class="text-slate-600">{generatedAt}</strong>
						</span>
					{/if}
				</div>
                <ReportActions
                    id={params.id}
                    viewHref={null}
                    showView={false}
                    deleting={deleting}
                    deleteEnabled={Boolean(token)}
                    on:delete={() => void handleDelete()}
                />
			</div>
			{#if deleteError}
				<div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-700">{deleteError}</div>
			{/if}

			<RunArtifactsPanel
				token={token}
				title="Project run context"
				emptyMessage="Select a project in the sidebar to correlate this report with recorded runs."
				highlightReportId={params.id}
			/>

			<div class="grid gap-4 md:grid-cols-3">
				<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Issues found</p>
					<p class="mt-3 text-4xl font-semibold text-slate-700">{issuesFound}</p>
				</div>
				<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Findings</p>
					<p class="mt-3 text-4xl font-semibold text-slate-700">{findingCount}</p>
				</div>
				<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Top severity</p>
					<p class="mt-3 text-2xl font-semibold text-slate-700">
						{severityEntries.length ? severityEntries[0][0] : '—'}
					</p>
				</div>
			</div>

			<section class="space-y-3">
				<h3 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Severity breakdown</h3>
				{#if severityEntries.length}
					<div class="space-y-2">
						{#each severityEntries as [severity, count]}
							<div class="flex items-center gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
								<span class="w-28 text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">{severity}</span>
								<span class="flex-1 text-slate-600">{count}</span>
							</div>
						{/each}
					</div>
				{:else}
					<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
						No severity counts recorded for this run.
					</p>
				{/if}
			</section>

			{#if hasCost}
				<section class="space-y-4">
					<h3 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Cost insights</h3>
					<div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
						<div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Total monthly</p>
							<p class="mt-2 text-2xl font-semibold">{formatCurrency(totalMonthlyCost)}</p>
						</div>
						<div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Δ monthly</p>
							<p class="mt-2 text-2xl font-semibold">{formatCurrency(diffMonthlyCost)}</p>
						</div>
						<div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Total hourly</p>
							<p class="mt-2 text-2xl font-semibold">{formatCurrency(totalHourlyCost)}</p>
						</div>
						<div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Δ hourly</p>
							<p class="mt-2 text-2xl font-semibold">{formatCurrency(diffHourlyCost)}</p>
						</div>
					</div>

					{#if costProjects.length}
						<div class="overflow-x-auto rounded-2xl border border-slate-200">
							<table class="min-w-full divide-y divide-slate-100 text-sm text-slate-600">
								<thead class="bg-slate-50 text-xs uppercase tracking-[0.25em] text-slate-400">
									<tr>
										<th class="px-4 py-3 text-left">Project</th>
										<th class="px-4 py-3 text-left">Path</th>
										<th class="px-4 py-3 text-right">Monthly</th>
										<th class="px-4 py-3 text-right">Δ Monthly</th>
									</tr>
								</thead>
								<tbody class="divide-y divide-slate-100">
									{#each costProjects as project}
										<tr class="bg-white">
											<td class="px-4 py-3">{project?.name ?? '—'}</td>
											<td class="px-4 py-3 text-xs text-slate-500">{project?.path ?? '—'}</td>
											<td class="px-4 py-3 text-right">{formatCurrency((project?.monthly_cost as number | null) ?? null)}</td>
											<td class="px-4 py-3 text-right">{formatCurrency((project?.diff_monthly_cost as number | null) ?? null)}</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}

					{#if costErrors.length}
						<details class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
							<summary class="cursor-pointer font-semibold">Infracost warnings</summary>
							<ul class="mt-2 list-disc space-y-1 pl-5 text-xs">
								{#each costErrors as message}
									<li>{message}</li>
								{/each}
							</ul>
						</details>
					{/if}
				</section>
			{/if}

			{#if driftSummary}
				<section class="space-y-4">
					<h3 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Plan drift</h3>
					{#if driftError}
						<div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{driftError}</div>
					{:else}
						<div class="flex flex-wrap gap-3 text-xs text-slate-500">
							<span class="rounded-xl border border-slate-200 px-3 py-1">Total changes: <strong class="text-slate-600">{driftSummary?.total_changes ?? 0}</strong></span>
							<span class="rounded-xl border border-slate-200 px-3 py-1">Status: <strong class="text-slate-600">{driftHasChanges ? 'Changes detected' : 'No drift'}</strong></span>
						</div>

						{#if driftCountEntries.length}
							<ul class="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
								{#each driftCountEntries as [action, value]}
									<li class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
										<span class="block text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{action}</span>
										<span class="mt-2 text-xl font-semibold text-slate-700">{value}</span>
									</li>
								{/each}
							</ul>
						{/if}

						{#if driftResourceChanges.length}
							<details class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
								<summary class="cursor-pointer font-semibold">Resource changes ({driftResourceChanges.length})</summary>
								<div class="mt-2 space-y-2 text-xs">
									{#each driftResourceChanges as change}
										<div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
											<p class="font-semibold text-slate-700">{(change?.address as string) ?? 'Unknown resource'}</p>
											<p class="text-slate-500">
												Action:
												{change?.action ??
												(Array.isArray(change?.actions) ? change.actions.join(', ') : '—')}
											</p>
										</div>
									{/each}
								</div>
							</details>
						{/if}

						{#if driftOutputChanges.length}
							<details class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
								<summary class="cursor-pointer font-semibold">Output changes ({driftOutputChanges.length})</summary>
								<div class="mt-2 space-y-2 text-xs">
									{#each driftOutputChanges as output}
										<div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
											<p class="font-semibold text-slate-700">{output?.name ?? 'output'}</p>
											<p class="text-slate-500">
												Actions:
												{Array.isArray(output?.actions) ? output.actions.join(', ') : '—'}
											</p>
										</div>
									{/each}
								</div>
							</details>
						{/if}
				{/if}
			</section>
			{/if}

			{#if displayedFindings.length}
				<section class="space-y-4">
					<h3 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
						Findings ({findings.length})
					</h3>
					<div class="overflow-x-auto rounded-2xl border border-slate-200 bg-slate-50">
						<table class="min-w-full divide-y divide-slate-200 text-sm">
							<thead class="bg-slate-100 text-xs uppercase tracking-[0.3em] text-slate-400">
								<tr>
									<th class="px-4 py-3 text-left">Severity</th>
									<th class="px-4 py-3 text-left">Rule</th>
									<th class="px-4 py-3 text-left">Title</th>
									<th class="px-4 py-3 text-left">Location</th>
								</tr>
							</thead>
							<tbody class="divide-y divide-slate-100 text-slate-600">
								{#each displayedFindings as finding, index (finding.id ?? finding.rule ?? index)}
									<tr class="hover:bg-sky-50">
										<td class="px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
											{finding.severity ?? 'unknown'}
										</td>
										<td class="px-4 py-3 font-mono text-xs text-slate-500">
											{finding.rule ?? '—'}
										</td>
										<td class="px-4 py-3 text-sm text-slate-600">
											{finding.title ?? 'Untitled finding'}
										</td>
										<td class="px-4 py-3 text-xs text-slate-500">
											{finding.file ?? '—'}
											{#if finding.line}
												: {finding.line}
											{/if}
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
					{#if findings.length > displayedFindings.length}
						<p class="text-xs text-slate-400">
							Displaying first {displayedFindings.length} findings. Use the JSON or CSV export for the full set.
						</p>
					{/if}
				</section>
			{:else}
				<div class="rounded-2xl border border-dashed border-slate-300/60 bg-slate-100 p-6 text-sm text-slate-500">
					<p class="font-medium text-slate-700">Findings</p>
					<p class="mt-2">Great news—no active findings recorded for this run.</p>
				</div>
			{/if}
		</div>
	{:else if !error}
		<div class="rounded-3xl border border-slate-200 bg-white px-6 py-6 text-sm text-slate-500">
			Loading report details...
		</div>
	{/if}
</section>
