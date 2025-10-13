<script lang="ts">
	import { onDestroy } from 'svelte';
	import AuthEventTimeline from '$lib/components/dashboard/AuthEventTimeline.svelte';
import StatCard from '$lib/components/dashboard/StatCard.svelte';
import StepBar from '$lib/components/dashboard/StepBar.svelte';
import SeverityDistribution from '$lib/components/dashboard/SeverityDistribution.svelte';
	import type { AuthEvent } from '$lib/api/client';
import type { DashboardStats } from '$lib/types/dashboard';

	const { data } = $props();
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
			CLI or this SvelteKit interface (the legacy Streamlit UI has been retired).
		</p>
	</header>

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
