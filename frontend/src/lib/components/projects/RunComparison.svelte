<script lang="ts">
import type { ProjectRunSummary } from '$lib/api/client';

interface Props {
	baseRun: ProjectRunSummary;
	compareRun: ProjectRunSummary;
	onClose?: () => void;
}

const { baseRun, compareRun, onClose }: Props = $props();

const formatDate = (dateStr?: string | null) => {
	if (!dateStr) return 'Unknown';
	const date = new Date(dateStr);
	if (Number.isNaN(date.getTime())) return dateStr;
	return date.toLocaleString();
};

const formatDuration = (start?: string | null, end?: string | null) => {
	if (!start || !end) return '—';
	const startDate = new Date(start);
	const endDate = new Date(end);
	if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return '—';
	const durationMs = endDate.getTime() - startDate.getTime();
	const seconds = Math.floor(durationMs / 1000);
	const minutes = Math.floor(seconds / 60);
	const hours = Math.floor(minutes / 60);

	if (hours > 0) {
		return `${hours}h ${minutes % 60}m`;
	} else if (minutes > 0) {
		return `${minutes}m ${seconds % 60}s`;
	} else {
		return `${seconds}s`;
	}
};

const extractSummaryValue = (summary?: Record<string, unknown>, key?: string): number | null => {
	if (!summary || !key) return null;
	const value = summary[key];
	if (typeof value === 'number') return value;
	if (typeof value === 'string') {
		const parsed = Number.parseFloat(value);
		return Number.isNaN(parsed) ? null : parsed;
	}
	return null;
};

const baseSummary = $derived(baseRun.summary ?? {});
const compareSummary = $derived(compareRun.summary ?? {});

const issuesFoundBase = $derived(extractSummaryValue(baseSummary, 'issues_found'));
const issuesFoundCompare = $derived(extractSummaryValue(compareSummary, 'issues_found'));

const severityCountsBase = $derived((baseSummary.severity_counts ?? {}) as Record<string, number>);
const severityCountsCompare = $derived((compareSummary.severity_counts ?? {}) as Record<string, number>);

const allSeverities = $derived.by(() => {
	const severities = new Set<string>();
	for (const key of Object.keys(severityCountsBase)) severities.add(key);
	for (const key of Object.keys(severityCountsCompare)) severities.add(key);
	return Array.from(severities).sort();
});

const severityChanges = $derived.by(() => {
	return allSeverities.map((severity) => {
		const baseCount = severityCountsBase[severity] ?? 0;
		const compareCount = severityCountsCompare[severity] ?? 0;
		const delta = compareCount - baseCount;
		return { severity, baseCount, compareCount, delta };
	});
});

const statusChanged = $derived(baseRun.status !== compareRun.status);
const issuesDelta = $derived(
	issuesFoundCompare !== null && issuesFoundBase !== null
		? issuesFoundCompare - issuesFoundBase
		: null
);

const getSeverityColor = (severity: string) => {
	switch (severity.toLowerCase()) {
		case 'critical':
			return 'text-red-600 bg-red-50 border-red-200';
		case 'high':
			return 'text-orange-600 bg-orange-50 border-orange-200';
		case 'medium':
			return 'text-yellow-600 bg-yellow-50 border-yellow-200';
		case 'low':
			return 'text-blue-600 bg-blue-50 border-blue-200';
		default:
			return 'text-slate-600 bg-slate-50 border-slate-200';
	}
};

const getDeltaColor = (delta: number) => {
	if (delta > 0) return 'text-red-600';
	if (delta < 0) return 'text-green-600';
	return 'text-slate-400';
};

const getDeltaIcon = (delta: number) => {
	if (delta > 0) return '↑';
	if (delta < 0) return '↓';
	return '=';
};
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between gap-4">
		<div>
			<h3 class="text-lg font-semibold text-slate-700">Run Comparison</h3>
			<p class="mt-1 text-sm text-slate-500">Comparing changes between two project runs</p>
		</div>
		{#if onClose}
			<button
				type="button"
				class="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100"
				onclick={onClose}
			>
				Close
			</button>
		{/if}
	</div>

	<div class="grid gap-4 sm:grid-cols-2">
		<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Base Run</p>
			<p class="mt-1 text-sm font-medium text-slate-700">{baseRun.label}</p>
			<div class="mt-3 space-y-1 text-xs text-slate-500">
				<p>
					<span class="font-medium">Kind:</span>
					{baseRun.kind}
				</p>
				<p>
					<span class="font-medium">Status:</span>
					<span class="rounded-md border border-slate-200 bg-white px-2 py-0.5 font-mono text-[0.65rem]">
						{baseRun.status}
					</span>
				</p>
				<p>
					<span class="font-medium">Created:</span>
					{formatDate(baseRun.created_at)}
				</p>
				{#if baseRun.started_at && baseRun.finished_at}
					<p>
						<span class="font-medium">Duration:</span>
						{formatDuration(baseRun.started_at, baseRun.finished_at)}
					</p>
				{/if}
			</div>
		</div>

		<div class="rounded-2xl border border-sky-200 bg-sky-50 p-4">
			<p class="text-xs font-semibold uppercase tracking-wider text-sky-600">Compare Run</p>
			<p class="mt-1 text-sm font-medium text-sky-700">{compareRun.label}</p>
			<div class="mt-3 space-y-1 text-xs text-sky-600">
				<p>
					<span class="font-medium">Kind:</span>
					{compareRun.kind}
				</p>
				<p>
					<span class="font-medium">Status:</span>
					<span
						class="rounded-md border border-sky-300 bg-white px-2 py-0.5 font-mono text-[0.65rem] {statusChanged
							? 'text-orange-600'
							: 'text-sky-600'}"
					>
						{compareRun.status}
						{#if statusChanged}
							<span class="ml-1 text-orange-500">changed</span>
						{/if}
					</span>
				</p>
				<p>
					<span class="font-medium">Created:</span>
					{formatDate(compareRun.created_at)}
				</p>
				{#if compareRun.started_at && compareRun.finished_at}
					<p>
						<span class="font-medium">Duration:</span>
						{formatDuration(compareRun.started_at, compareRun.finished_at)}
					</p>
				{/if}
			</div>
		</div>
	</div>

	{#if issuesFoundBase !== null || issuesFoundCompare !== null}
		<div class="rounded-2xl border border-slate-200 bg-white p-6">
			<h4 class="mb-4 text-sm font-semibold text-slate-700">Summary Changes</h4>
			<div class="grid gap-4 sm:grid-cols-2">
				<div>
					<p class="text-xs font-medium uppercase tracking-wider text-slate-400">Issues Found</p>
					<div class="mt-2 flex items-baseline gap-2">
						<p class="text-3xl font-bold text-slate-700">{issuesFoundBase ?? '—'}</p>
						<p class="text-xl text-slate-400">→</p>
						<p class="text-3xl font-bold text-sky-600">{issuesFoundCompare ?? '—'}</p>
						{#if issuesDelta !== null}
							<p class="text-sm font-medium {getDeltaColor(issuesDelta)}">
								{getDeltaIcon(issuesDelta)}
								{Math.abs(issuesDelta)}
							</p>
						{/if}
					</div>
				</div>
			</div>
		</div>

		{#if allSeverities.length > 0}
			<div class="rounded-2xl border border-slate-200 bg-white">
				<div class="border-b border-slate-200 px-6 py-4">
					<h4 class="text-sm font-semibold text-slate-700">Severity Changes</h4>
				</div>
				<div class="divide-y divide-slate-100">
					{#each severityChanges as { severity, baseCount, compareCount, delta }}
						<div class="px-6 py-4">
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-3">
									<span
										class="inline-block rounded-md border px-2 py-0.5 text-xs font-medium {getSeverityColor(
											severity
										)}"
									>
										{severity.charAt(0).toUpperCase() + severity.slice(1)}
									</span>
									<div class="flex items-baseline gap-2 text-sm">
										<span class="font-medium text-slate-600">{baseCount}</span>
										<span class="text-slate-400">→</span>
										<span class="font-medium text-sky-600">{compareCount}</span>
									</div>
								</div>
								{#if delta !== 0}
									<p class="text-sm font-medium {getDeltaColor(delta)}">
										{getDeltaIcon(delta)}
										{Math.abs(delta)}
									</p>
								{:else}
									<p class="text-xs text-slate-400">No change</p>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{:else}
		<div class="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-center">
			<p class="text-sm text-slate-500">No summary data available for these runs</p>
		</div>
	{/if}

	{#if baseRun.parameters || compareRun.parameters}
		<details class="group rounded-2xl border border-slate-200 bg-slate-50">
			<summary class="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-600 transition hover:text-slate-700">
				Parameters Comparison
			</summary>
			<div class="border-t border-slate-200 p-4">
				<div class="grid gap-4 sm:grid-cols-2">
					<div>
						<p class="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
							Base Parameters
						</p>
						{#if baseRun.parameters && Object.keys(baseRun.parameters).length > 0}
							<pre
								class="overflow-auto rounded-xl border border-slate-200 bg-white p-3 font-mono text-xs text-slate-600">
{JSON.stringify(baseRun.parameters, null, 2)}</pre>
						{:else}
							<p class="text-sm text-slate-400">No parameters</p>
						{/if}
					</div>
					<div>
						<p class="mb-2 text-xs font-semibold uppercase tracking-wider text-sky-600">
							Compare Parameters
						</p>
						{#if compareRun.parameters && Object.keys(compareRun.parameters).length > 0}
							<pre
								class="overflow-auto rounded-xl border border-sky-200 bg-white p-3 font-mono text-xs text-sky-600">
{JSON.stringify(compareRun.parameters, null, 2)}</pre>
						{:else}
							<p class="text-sm text-sky-400">No parameters</p>
						{/if}
					</div>
				</div>
			</div>
		</details>
	{/if}
</div>
