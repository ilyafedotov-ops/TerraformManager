<script lang="ts">
	import { onDestroy } from 'svelte';
import { goto } from '$app/navigation';
import { page } from '$app/stores';
	import AuthEventTimeline from '$lib/components/dashboard/AuthEventTimeline.svelte';
	import StatCard from '$lib/components/dashboard/StatCard.svelte';
	import StepBar from '$lib/components/dashboard/StepBar.svelte';
	import SeverityDistribution from '$lib/components/dashboard/SeverityDistribution.svelte';
import ProjectKnowledgePanel from '$lib/components/projects/ProjectKnowledgePanel.svelte';
	import type { AuthEvent } from '$lib/api/client';
	import type { DashboardStats } from '$lib/types/dashboard';
	import { activeProject, activeProjectRuns, projectState } from '$lib/stores/project';

const { data } = $props();
const projectSlug = $derived($page.params.projectSlug ?? null);
const projectBasePath = $derived(projectSlug ? `/projects/${projectSlug}` : '/projects');
const projectReportsHref = $derived(projectSlug ? `${projectBasePath}/reports` : '/projects');
const projectGenerateHref = $derived(projectSlug ? `${projectBasePath}/generate` : '/projects');
	const statsSource = data.stats as DashboardStats | Promise<DashboardStats | null> | null;
	const errorSource = data.error as string | Promise<string | null> | null;
	const authEventsSource = data.authEvents as AuthEvent[] | Promise<AuthEvent[]> | null;
	const authEventsErrorSource = data.authEventsError as string | Promise<string | null> | null;

	const isPromise = <T>(value: T | Promise<T>): value is Promise<T> =>
		typeof value === 'object' && value !== null && typeof (value as Promise<T>).then === 'function';

let stats = $state<DashboardStats | null>(null);
let resolvedError = $state<string | null>(null);
let isLoading = $state<boolean>(isPromise(statsSource));
let authEvents = $state<AuthEvent[]>(Array.isArray(authEventsSource) ? authEventsSource : []);
let eventsLoading = $state<boolean>(isPromise(authEventsSource));
let authEventsError = $state<string | null>(null);

	if (isPromise(statsSource)) {
		let active = true;
		statsSource
			.then((value) => {
				if (active) {
					stats = value;
				}
			})
			.catch(() => {
				if (active) {
					stats = null;
				}
			})
			.finally(() => {
				if (active) {
					isLoading = false;
				}
			});
		onDestroy(() => {
			active = false;
		});
	} else {
		stats = statsSource ?? null;
		isLoading = false;
	}

	if (isPromise(errorSource)) {
		let active = true;
		errorSource
			.then((value) => {
				if (active) {
					resolvedError = value ?? null;
				}
			})
			.catch((error) => {
				if (active) {
					resolvedError =
						error instanceof Error ? error.message : String(error ?? 'Failed to load dashboard data');
				}
			});
		onDestroy(() => {
			active = false;
		});
	} else {
		resolvedError = errorSource ?? null;
	}

	if (isPromise(authEventsSource)) {
		let active = true;
		authEventsSource
			.then((value) => {
				if (active) {
					authEvents = value ?? [];
				}
			})
			.catch(() => {
				if (active) {
					authEvents = [];
				}
			})
			.finally(() => {
				if (active) {
					eventsLoading = false;
				}
			});
		onDestroy(() => {
			active = false;
		});
	} else if (Array.isArray(authEventsSource)) {
		authEvents = authEventsSource;
		eventsLoading = false;
	} else {
		authEvents = [];
		eventsLoading = false;
	}

	if (isPromise(authEventsErrorSource)) {
		let active = true;
		authEventsErrorSource
			.then((value) => {
				if (active) {
					authEventsError = value ?? null;
				}
			})
			.catch((error) => {
				if (active) {
					authEventsError =
						error instanceof Error ? error.message : String(error ?? 'Failed to load activity data');
				}
			});
		onDestroy(() => {
			active = false;
		});
	} else {
		authEventsError = authEventsErrorSource ?? null;
	}

const lastReport = $derived(stats?.last);
const lastSummary = $derived(lastReport?.summary);
const lastSummaryFindings = $derived(
	(() =>
		lastSummary
			? Object.values(lastSummary.severity_counts ?? {}).reduce((total, value) => total + Number(value ?? 0), 0)
			: 0)()
);

const topSeverityLabel = $derived(
	(() => {
		if (!stats) return '—';
		const [severity] = Object.entries(stats.severityCounts ?? {})
			.map(([key, value]) => [key, Number(value ?? 0)] as [string, number])
			.sort((a, b) => b[1] - a[1])[0] ?? [];
		return severity ?? '—';
	})()
);

const topSeverityCount = $derived(
	(() => {
		if (!stats) return 0;
		const [, count] = Object.entries(stats.severityCounts ?? {})
			.map(([key, value]) => [key, Number(value ?? 0)] as [string, number])
			.sort((a, b) => b[1] - a[1])[0] ?? [];
		return count ?? 0;
	})()
);

const hasSeverityData = $derived(topSeverityCount > 0);

	const activeProjectSummary = $derived($activeProject);
	const recentRuns = $derived($activeProjectRuns.slice(0, 3));
	const hasProjects = $derived($projectState.projects.length > 0);
	const isProjectLoading = $derived($projectState.loading);

	const handleStartRun = async () => {
		await goto(projectGenerateHref);
	};

	const handleReviewRuns = async () => {
		await goto(projectReportsHref);
	};

	const stepItems = [
		{
			title: 'Scan',
			description: 'Upload Terraform modules for policy checks.',
			status: 'current' as const
		},
		{
			title: 'Review',
			description: 'Assess severity trends & waive eligible findings.',
			status: 'upcoming' as const
		},
		{
			title: 'Export',
			description: 'Share JSON/CSV/HTML outputs with downstream tools.',
			status: 'upcoming' as const
		}
	];
</script>

<section class="space-y-8">
	<header class="flex flex-col gap-2">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Overview</p>
		<h2 class="text-3xl font-semibold text-slate-700">Platform health</h2>
	<p class="max-w-2xl text-sm text-slate-500">
		High-level metrics pulled directly from the FastAPI reviewer. Counts update whenever new reports are stored via the
		Projects workspace or this SvelteKit interface (the legacy Streamlit UI has been retired).
	</p>
	</header>

	<section class="rounded-3xl border border-slate-200 bg-white px-6 py-5 shadow-sm shadow-slate-200">
		<div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
			<div>
				<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Project workspace</p>
				{#if activeProjectSummary}
					<h3 class="mt-1 text-xl font-semibold text-slate-700">{activeProjectSummary.name}</h3>
					<p class="text-sm text-slate-500">
						Using slug
						<span class="rounded-full bg-slate-100 px-2 py-[2px] text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-slate-500">
							{activeProjectSummary.slug}
						</span>
					</p>
				{:else if isProjectLoading}
					<p class="text-sm text-slate-500">Loading projects…</p>
				{:else if hasProjects}
					<p class="text-sm text-slate-500">Select a project from the sidebar to see run history.</p>
				{:else}
			<p class="text-sm text-slate-500">
				No projects yet. Create one from the Projects page to bootstrap a workspace, then refresh.
			</p>
				{/if}
			</div>
			<div class="flex flex-wrap gap-3">
				<button
					type="button"
					class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-50"
					onclick={handleReviewRuns}
				>
					View Reports
				</button>
				<button
					type="button"
					class="rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-sky-200 transition hover:bg-sky-600"
					onclick={handleStartRun}
				>
					Start New Run
				</button>
			</div>
		</div>
		{#if recentRuns.length}
			<div class="mt-5 grid gap-3 md:grid-cols-3">
				{#each recentRuns as run (run.id)}
					<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
						<p class="text-sm font-semibold text-slate-700">{run.label}</p>
						<p class="mt-1 text-[0.7rem] uppercase tracking-[0.2em] text-slate-400">{run.kind}</p>
						<p class="mt-2 inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-[2px] text-[0.6rem] font-semibold uppercase tracking-[0.2em] text-slate-500">
							{run.status}
						</p>
						{#if run.created_at}
							<p class="mt-1 text-[0.65rem] text-slate-400">Created {run.created_at}</p>
						{/if}
						{#if run.summary && Object.keys(run.summary).length}
							<p class="mt-2 text-[0.65rem] text-slate-500">
								Summary fields: {Object.keys(run.summary).slice(0, 3).join(', ')}
								{#if Object.keys(run.summary).length > 3}
									…
								{/if}
							</p>
						{/if}
					</div>
				{/each}
			</div>
		{:else if activeProjectSummary && !isProjectLoading}
			<p class="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-xs text-slate-500">
				No runs recorded for this project yet. Use the generator or review flows to create the first run.
			</p>
		{/if}
	</section>

	{#if resolvedError}
		<div class="rounded-3xl border border-rose-300 bg-rose-50 px-6 py-4 text-sm text-rose-700">
			<strong class="font-semibold">Unable to load dashboard data.</strong>
			<span class="ml-2 text-rose-600">{resolvedError}</span>
		</div>
	{/if}

	{#if stats}
		<div class="grid gap-4 md:grid-cols-3">
			<StatCard
				title="Reports indexed"
				value={stats.reports}
				description={`Latest ${Math.min(stats.reports, 20)} runs pulled from the reviewer database.`}
			/>
			<StatCard
				title="Top severity"
				value={topSeverityLabel}
				description={
					hasSeverityData
						? `${topSeverityCount} findings across recent reports.`
						: 'No findings recorded yet.'
				}
				accent={hasSeverityData ? 'warning' : 'default'}
			/>
			<StatCard
				title="Last report"
				value={lastReport ? lastReport.id : 'Awaiting scan'}
				description={
					lastSummary
						? `${lastSummary.issues_found ?? 0} issues • ${lastSummaryFindings} findings`
						: 'Run a scan to populate this view.'
				}
				accent={lastSummary && (lastSummary.issues_found ?? 0) > 0 ? 'danger' : 'success'}
			/>
		</div>

		<div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
			<StepBar steps={stepItems} />
		</div>

		<SeverityDistribution stats={stats} recentLimit={5} />
	{:else if isLoading}
		<div class="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6 text-sm text-slate-500">
			Fetching report metrics...
		</div>
	{:else}
		<div class="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6 text-sm text-slate-500">
			No dashboard statistics are available yet. Run your first scan to populate this view.
		</div>
	{/if}

	<ProjectKnowledgePanel project={activeProjectSummary} />

	<div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
		<header class="mb-4 space-y-2">
			<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Security</p>
			<h3 class="text-2xl font-semibold text-slate-700">Recent account activity</h3>
			<p class="text-sm text-slate-500">
				Events log authentication activity (login, refresh, session revocation) with IP and user-agent metadata to help
				triage unusual access patterns.
			</p>
		</header>

		{#if authEventsError}
			<div class="mb-4 rounded-3xl border border-rose-300 bg-rose-50 px-6 py-4 text-sm text-rose-700">
				<strong class="font-semibold">Unable to load activity.</strong>
				<span class="ml-2 text-rose-600">{authEventsError}</span>
			</div>
		{/if}

		{#if authEvents.length}
			<AuthEventTimeline events={authEvents} />
		{:else if eventsLoading}
			<div class="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6 text-sm text-slate-500">
				Loading recent authentication events…
			</div>
		{:else}
			<div class="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6 text-sm text-slate-500">
				No recent authentication events recorded yet. Activity will appear here after sign-ins or session changes.
			</div>
		{/if}
	</div>
</section>
