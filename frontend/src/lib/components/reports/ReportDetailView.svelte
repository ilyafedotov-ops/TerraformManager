<script lang="ts">
import { browser } from '$app/environment';
import { createEventDispatcher } from 'svelte';
import { deleteReport, type ReportDetail, ApiError } from '$lib/api/client';
import ReportActions from '$lib/components/reports/ReportActions.svelte';
import RunArtifactsPanel from '$lib/components/projects/RunArtifactsPanel.svelte';
import ProjectWorkspaceBanner from '$lib/components/projects/ProjectWorkspaceBanner.svelte';
import { notifyError, notifySuccess } from '$lib/stores/notifications';

interface Props {
	report: ReportDetail | null;
	reportId?: string | null;
	error?: string | null;
	token?: string | null;
	projectId?: string | null;
	projectSlug?: string | null;
	backHref?: string | null;
	showBackLink?: boolean;
	showWorkspaceBanner?: boolean;
}

const {
	report,
	reportId = report?.id ?? null,
	error = null,
	token = null,
	projectId = null,
	projectSlug = null,
	backHref = undefined,
	showBackLink = true,
	showWorkspaceBanner = true
}: Props = $props();

const dispatch = createEventDispatcher<{ close: void; deleted: { id: string } }>();

const resolvedReportId = reportId ?? report?.id ?? null;
const fallbackBackHref = (() => {
	const identifier = projectSlug ?? projectId ?? null;
	if (!identifier) {
		return '/projects';
	}
	const params = new URLSearchParams();
	params.set('project', identifier);
	params.set('tab', 'reports');
	return `/projects?${params.toString()}`;
})();
const resolvedBackHref = backHref === undefined ? fallbackBackHref : backHref;
const useBackButton = resolvedBackHref === null;

let deleting = $state(false);
let deleteError = $state<string | null>(null);

const severityEntries = report?.summary?.severity_counts
	? Object.entries(report.summary.severity_counts)
			.map(([key, value]) => [key, Number(value ?? 0)] as [string, number])
			.sort((a, b) => b[1] - a[1])
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
	} catch (_error) {
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
	if (!token || !resolvedReportId) {
		deleteError = 'Missing API token; cannot delete report.';
		return;
	}
	if (browser) {
		const confirmed = window.confirm(`Delete report ${resolvedReportId}? This action cannot be undone.`);
		if (!confirmed) {
			return;
		}
	}
	deleting = true;
	deleteError = null;
	try {
		await deleteReport(fetch, token, resolvedReportId);
		notifySuccess(`Report ${resolvedReportId} deleted.`);
		dispatch('deleted', { id: resolvedReportId });
		dispatch('close');
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

<section class="space-y-6 overflow-x-hidden rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
	<header class="space-y-2">
		{#if showBackLink}
			{#if useBackButton}
				<button
					type="button"
					class="text-left text-xs font-semibold uppercase tracking-[0.3em] text-slate-400 transition hover:text-sky-500"
					onclick={() => dispatch('close')}
				>
					← Back to reports
				</button>
			{:else if resolvedBackHref}
				<a
					class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400 transition hover:text-sky-500"
					href={resolvedBackHref}
				>
					← Back to reports
				</a>
			{/if}
		{/if}
		<h2 class="break-words text-2xl font-semibold text-slate-700 sm:text-3xl">
			Report {resolvedReportId ?? '—'}
		</h2>
		<p class="max-w-2xl text-sm text-slate-500">
			Download artifacts or inspect severity trends from this run. The embedded findings table utilises the existing FastAPI viewer endpoints.
		</p>
	</header>

	{#if error}
		<div class="rounded-3xl border border-rose-300 bg-rose-50 px-6 py-4 text-sm text-rose-700">
			<strong class="font-semibold">Unable to load report.</strong>
			<span class="ml-2 text-rose-600">{error}</span>
		</div>
	{/if}

	{#if showWorkspaceBanner}
		<ProjectWorkspaceBanner context="Correlate this report with workspace runs to access linked artifacts and history." />
	{/if}

	{#if report}
		<div class="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-lg shadow-slate-300/30">
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
					id={resolvedReportId ?? ''}
					viewHref={null}
					showView={false}
					deleting={deleting}
					deleteEnabled={Boolean(token && resolvedReportId)}
					on:delete={() => void handleDelete()}
				/>
			</div>
			{#if deleteError}
				<div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-700">{deleteError}</div>
			{/if}

			<RunArtifactsPanel
				token={token ?? null}
				title="Project run context"
				emptyMessage="Select a project in the sidebar to correlate this report with recorded runs."
				highlightReportId={resolvedReportId ?? undefined}
			/>

			<div class="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
				<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Issues found</p>
					<p class="mt-3 text-3xl font-semibold text-slate-700 sm:text-4xl">{issuesFound}</p>
				</div>
				<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Findings</p>
					<p class="mt-3 text-3xl font-semibold text-slate-700 sm:text-4xl">{findingCount}</p>
				</div>
				<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 sm:col-span-2 md:col-span-1">
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
					<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
						<div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Total monthly</p>
							<p class="mt-2 text-2xl font-semibold">{formatCurrency(totalMonthlyCost)}</p>
						</div>
						<div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Monthly delta</p>
							<p class="mt-2 text-2xl font-semibold">{formatCurrency(diffMonthlyCost)}</p>
						</div>
						<div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Total hourly</p>
							<p class="mt-2 text-2xl font-semibold">{formatCurrency(totalHourlyCost)}</p>
						</div>
						<div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Hourly delta</p>
							<p class="mt-2 text-2xl font-semibold">{formatCurrency(diffHourlyCost)}</p>
						</div>
					</div>

					{#if costProjects.length}
						<div class="rounded-2xl border border-slate-200 bg-white p-4">
							<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Project breakdown</h4>
							<ul class="mt-3 space-y-2 text-sm text-slate-600">
								{#each costProjects as project (project.name ?? project.path ?? Math.random())}
									<li class="flex flex-wrap items-center justify-between rounded-2xl border border-slate-100 px-3 py-2">
										<div>
											<p class="font-semibold text-slate-700">{project.name ?? project.path ?? 'Project'}</p>
											<p class="text-xs text-slate-400">{project.path ?? '—'}</p>
										</div>
										<div class="text-right">
											<p class="text-sm font-semibold text-slate-700">
												{formatCurrency(project.monthly_cost ?? null)}
											</p>
											<p class="text-xs text-slate-500">
												Δ {formatCurrency(project.diff_monthly_cost ?? null)}
											</p>
										</div>
									</li>
								{/each}
							</ul>
						</div>
					{/if}

					{#if costErrors.length}
						<div class="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-amber-500">Cost warnings</p>
							<ul class="mt-2 space-y-1">
								{#each costErrors as warning, index}
									<li class="rounded-xl bg-white/60 px-3 py-2">{warning ?? `Warning ${index + 1}`}</li>
								{/each}
							</ul>
						</div>
					{/if}
				</section>
			{/if}

			<section class="space-y-4">
				<h3 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Plan drift</h3>
				{#if driftError}
					<div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
						<strong class="font-semibold">Unable to compute drift.</strong>
						<span class="ml-2 text-rose-600">{driftError}</span>
					</div>
				{:else if driftCountEntries.length}
					<ul class="space-y-2 text-sm text-slate-600">
						{#each driftCountEntries as [kind, count]}
							<li class="flex items-center justify-between rounded-2xl border border-slate-100 px-3 py-2">
								<span class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{kind}</span>
								<span class="text-base text-slate-700">{count}</span>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
						No drift metrics recorded for this run.
					</p>
				{/if}

				{#if driftHasChanges}
					<div class="grid gap-4 md:grid-cols-2">
						<div class="rounded-2xl border border-slate-200 bg-white p-4">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Resource changes</p>
							{#if driftResourceChanges.length}
								<ul class="mt-3 space-y-2 text-sm text-slate-600">
									{#each driftResourceChanges as change, index}
										<li class="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2">
											<p class="font-semibold text-slate-700">
												{change.address ?? `Change ${index + 1}`}
											</p>
											<p class="text-xs text-slate-500">Action: {change.action ?? '—'}</p>
										</li>
									{/each}
								</ul>
							{:else}
								<p class="mt-2 text-sm text-slate-500">No resource changes recorded.</p>
							{/if}
						</div>
						<div class="rounded-2xl border border-slate-200 bg-white p-4">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Output changes</p>
							{#if driftOutputChanges.length}
								<ul class="mt-3 space-y-2 text-sm text-slate-600">
									{#each driftOutputChanges as change, index}
										<li class="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2">
											<p class="font-semibold text-slate-700">
												{change.name ?? `Output ${index + 1}`}
											</p>
											<p class="text-xs text-slate-500">
												Action: {change.actions?.length ? change.actions.join(', ') : '—'}
											</p>
										</li>
									{/each}
								</ul>
							{:else}
								<p class="mt-2 text-sm text-slate-500">No output changes recorded.</p>
							{/if}
						</div>
					</div>
				{/if}
			</section>

			<section class="space-y-4">
				<h3 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Findings (preview)</h3>
				{#if displayedFindings.length}
					<ul class="space-y-2 text-sm text-slate-600">
						{#each displayedFindings as finding, index}
							<li class="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2">
								<p class="font-semibold text-slate-700">
									{finding.rule_id ?? `Finding ${index + 1}`}
								</p>
								<p class="text-xs text-slate-500">
									Resource: {finding.resource_address ?? finding.resource_name ?? '—'}
								</p>
								<p class="mt-1 text-slate-600">{finding.description ?? 'Description unavailable.'}</p>
							</li>
						{/each}
					</ul>
					{#if findings.length > displayedFindings.length}
						<p class="text-xs text-slate-500">
							Showing {displayedFindings.length} of {findings.length} findings.
						</p>
					{/if}
				{:else}
					<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
						No findings recorded for this run.
					</p>
				{/if}
			</section>
		</div>
	{:else if !error}
		<p class="text-sm text-slate-500">Report details will appear here once loaded.</p>
	{/if}
</section>
