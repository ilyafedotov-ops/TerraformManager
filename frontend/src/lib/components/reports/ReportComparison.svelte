<script lang="ts">
import { getReport, type ReportDetail } from '$lib/api/client';
import { notifyError } from '$lib/stores/notifications';

interface Props {
	token?: string | null;
	baseReportId: string;
	compareReportId: string;
	onClose?: () => void;
}

const { token = null, baseReportId, compareReportId, onClose }: Props = $props();

type FindingKey = {
	rule: string;
	severity: string;
	file?: string;
	line?: number;
};

type Finding = Record<string, unknown> & {
	rule?: string;
	severity?: string;
	file?: string;
	line?: number;
};

let baseReport = $state<ReportDetail | null>(null);
let compareReport = $state<ReportDetail | null>(null);
let loading = $state(true);
let error = $state<string | null>(null);
let selectedCategory = $state<'new' | 'resolved' | 'common' | 'changed'>('new');

const getFindingKey = (finding: Finding): string => {
	const rule = finding.rule ?? 'unknown';
	const file = finding.file ?? '';
	const line = finding.line ?? 0;
	return `${rule}::${file}::${line}`;
};

const compareFindings = (base: Finding[], compare: Finding[]) => {
	const baseMap = new Map<string, Finding>();
	const compareMap = new Map<string, Finding>();

	for (const finding of base) {
		baseMap.set(getFindingKey(finding), finding);
	}

	for (const finding of compare) {
		compareMap.set(getFindingKey(finding), finding);
	}

	const newFindings: Finding[] = [];
	const resolvedFindings: Finding[] = [];
	const commonFindings: Array<{ base: Finding; compare: Finding }> = [];
	const changedFindings: Array<{ base: Finding; compare: Finding }> = [];

	for (const [key, finding] of compareMap) {
		if (!baseMap.has(key)) {
			newFindings.push(finding);
		} else {
			const baseFinding = baseMap.get(key)!;
			if (baseFinding.severity !== finding.severity) {
				changedFindings.push({ base: baseFinding, compare: finding });
			} else {
				commonFindings.push({ base: baseFinding, compare: finding });
			}
		}
	}

	for (const [key, finding] of baseMap) {
		if (!compareMap.has(key)) {
			resolvedFindings.push(finding);
		}
	}

	return { newFindings, resolvedFindings, commonFindings, changedFindings };
};

const comparisonResult = $derived.by(() => {
	if (!baseReport?.findings || !compareReport?.findings) {
		return null;
	}

	return compareFindings(
		baseReport.findings as Finding[],
		compareReport.findings as Finding[]
	);
});

const loadReports = async () => {
	if (!token) {
		error = 'Authentication token required';
		loading = false;
		return;
	}

	try {
		loading = true;
		error = null;

		const [base, compare] = await Promise.all([
			getReport(fetch, token, baseReportId),
			getReport(fetch, token, compareReportId)
		]);

		baseReport = base;
		compareReport = compare;
	} catch (err) {
		error = err instanceof Error ? err.message : 'Failed to load reports';
		notifyError(error);
	} finally {
		loading = false;
	}
};

$effect(() => {
	loadReports();
});

const formatSeverity = (severity?: string) => {
	if (!severity) return 'unknown';
	return severity.charAt(0).toUpperCase() + severity.slice(1);
};

const getSeverityColor = (severity?: string) => {
	switch (severity?.toLowerCase()) {
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

const getChangeIcon = (baseSev?: string, compareSev?: string) => {
	const severityLevels: Record<string, number> = {
		critical: 4,
		high: 3,
		medium: 2,
		low: 1
	};
	const baseLevel = severityLevels[baseSev?.toLowerCase() ?? ''] ?? 0;
	const compareLevel = severityLevels[compareSev?.toLowerCase() ?? ''] ?? 0;

	if (compareLevel > baseLevel) {
		return { icon: '↑', color: 'text-red-600', label: 'Increased' };
	} else if (compareLevel < baseLevel) {
		return { icon: '↓', color: 'text-green-600', label: 'Decreased' };
	}
	return { icon: '=', color: 'text-slate-400', label: 'No change' };
};

const formatDate = (dateStr?: string | null) => {
	if (!dateStr) return 'Unknown';
	const date = new Date(dateStr);
	if (Number.isNaN(date.getTime())) return dateStr;
	return date.toLocaleString();
};

type DisplayFinding = Finding | { base: Finding; compare: Finding };

const currentFindings = $derived.by((): DisplayFinding[] => {
	if (!comparisonResult) return [];

	switch (selectedCategory) {
		case 'new':
			return comparisonResult.newFindings;
		case 'resolved':
			return comparisonResult.resolvedFindings;
		case 'common':
			return comparisonResult.commonFindings.map((c) => c.compare);
		case 'changed':
			return comparisonResult.changedFindings;
		default:
			return [];
	}
});
</script>

<div class="space-y-6">
	{#if loading}
		<div class="rounded-2xl border border-slate-200 bg-white p-8">
			<div class="flex items-center justify-center gap-3">
				<div class="h-5 w-5 animate-spin rounded-full border-2 border-sky-600 border-t-transparent"></div>
				<p class="text-sm text-slate-600">Loading reports for comparison...</p>
			</div>
		</div>
	{:else if error}
		<div class="rounded-2xl border border-red-200 bg-red-50 p-6">
			<p class="text-sm font-medium text-red-900">Failed to load reports</p>
			<p class="mt-1 text-sm text-red-700">{error}</p>
		</div>
	{:else if baseReport && compareReport && comparisonResult}
		<div class="space-y-6">
			<div class="flex items-center justify-between gap-4">
				<div>
					<h3 class="text-lg font-semibold text-slate-700">Report Comparison</h3>
					<p class="mt-1 text-sm text-slate-500">
						Comparing changes between two scan reports
					</p>
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
					<p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Base Report</p>
					<p class="mt-1 text-sm font-mono text-slate-700">{baseReportId.slice(0, 8)}...</p>
					<p class="mt-2 text-xs text-slate-500">Created: {formatDate(baseReport.created_at)}</p>
					<p class="mt-1 text-xs text-slate-500">
						Findings: {baseReport.findings?.length ?? 0}
					</p>
				</div>

				<div class="rounded-2xl border border-sky-200 bg-sky-50 p-4">
					<p class="text-xs font-semibold uppercase tracking-wider text-sky-600">Compare Report</p>
					<p class="mt-1 text-sm font-mono text-sky-700">{compareReportId.slice(0, 8)}...</p>
					<p class="mt-2 text-xs text-sky-600">Created: {formatDate(compareReport.created_at)}</p>
					<p class="mt-1 text-xs text-sky-600">
						Findings: {compareReport.findings?.length ?? 0}
					</p>
				</div>
			</div>

			<div class="grid gap-4 sm:grid-cols-4">
				<button
					type="button"
					class="rounded-2xl border p-4 text-left transition {selectedCategory === 'new'
						? 'border-green-300 bg-green-50'
						: 'border-slate-200 bg-white hover:border-green-200'}"
					onclick={() => (selectedCategory = 'new')}
				>
					<p class="text-xs font-semibold uppercase tracking-wider text-slate-400">New Findings</p>
					<p class="mt-2 text-3xl font-bold text-green-600">
						{comparisonResult.newFindings.length}
					</p>
					<p class="mt-1 text-xs text-slate-500">Added in compare report</p>
				</button>

				<button
					type="button"
					class="rounded-2xl border p-4 text-left transition {selectedCategory === 'resolved'
						? 'border-blue-300 bg-blue-50'
						: 'border-slate-200 bg-white hover:border-blue-200'}"
					onclick={() => (selectedCategory = 'resolved')}
				>
					<p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Resolved</p>
					<p class="mt-2 text-3xl font-bold text-blue-600">
						{comparisonResult.resolvedFindings.length}
					</p>
					<p class="mt-1 text-xs text-slate-500">Fixed since base report</p>
				</button>

				<button
					type="button"
					class="rounded-2xl border p-4 text-left transition {selectedCategory === 'changed'
						? 'border-orange-300 bg-orange-50'
						: 'border-slate-200 bg-white hover:border-orange-200'}"
					onclick={() => (selectedCategory = 'changed')}
				>
					<p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Changed</p>
					<p class="mt-2 text-3xl font-bold text-orange-600">
						{comparisonResult.changedFindings.length}
					</p>
					<p class="mt-1 text-xs text-slate-500">Severity changed</p>
				</button>

				<button
					type="button"
					class="rounded-2xl border p-4 text-left transition {selectedCategory === 'common'
						? 'border-slate-400 bg-slate-50'
						: 'border-slate-200 bg-white hover:border-slate-300'}"
					onclick={() => (selectedCategory = 'common')}
				>
					<p class="text-xs font-semibold uppercase tracking-wider text-slate-400">Unchanged</p>
					<p class="mt-2 text-3xl font-bold text-slate-600">
						{comparisonResult.commonFindings.length}
					</p>
					<p class="mt-1 text-xs text-slate-500">Same in both reports</p>
				</button>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-white">
				<div class="border-b border-slate-200 px-6 py-4">
					<h4 class="text-sm font-semibold text-slate-700">
						{selectedCategory === 'new'
							? 'New Findings'
							: selectedCategory === 'resolved'
								? 'Resolved Findings'
								: selectedCategory === 'changed'
									? 'Changed Findings'
									: 'Unchanged Findings'}
						<span class="ml-2 text-slate-400">({currentFindings.length})</span>
					</h4>
				</div>

				<div class="divide-y divide-slate-100">
					{#if currentFindings.length === 0}
						<div class="px-6 py-8 text-center">
							<p class="text-sm text-slate-500">No findings in this category</p>
						</div>
					{:else if selectedCategory === 'changed'}
						{#each comparisonResult.changedFindings as { base, compare }}
							{@const change = getChangeIcon(base.severity, compare.severity)}
							<div class="px-6 py-4">
								<div class="flex items-start gap-3">
									<span class="text-2xl {change.color}" title={change.label}>{change.icon}</span>
									<div class="flex-1">
										<div class="flex items-center gap-2">
											<span
												class="inline-block rounded-md border px-2 py-0.5 text-xs font-medium {getSeverityColor(
													base.severity
												)}"
											>
												{formatSeverity(base.severity)}
											</span>
											<span class="text-slate-400">→</span>
											<span
												class="inline-block rounded-md border px-2 py-0.5 text-xs font-medium {getSeverityColor(
													compare.severity
												)}"
											>
												{formatSeverity(compare.severity)}
											</span>
										</div>
										<p class="mt-2 text-sm font-medium text-slate-700">{compare.rule}</p>
										{#if compare.file}
											<p class="mt-1 text-xs font-mono text-slate-500">
												{compare.file}{compare.line ? `:${compare.line}` : ''}
											</p>
										{/if}
									</div>
								</div>
							</div>
						{/each}
					{:else}
						{#each currentFindings as finding}
							{#if 'base' in finding && 'compare' in finding}
								<div class="px-6 py-4">
									<p class="text-sm text-slate-500">Unexpected data structure</p>
								</div>
							{:else}
								<div class="px-6 py-4">
									<div class="flex items-start gap-3">
										<span
											class="inline-block rounded-md border px-2 py-0.5 text-xs font-medium {getSeverityColor(
												finding.severity
											)}"
										>
											{formatSeverity(finding.severity)}
										</span>
										<div class="flex-1">
											<p class="text-sm font-medium text-slate-700">{finding.rule}</p>
											{#if finding.file}
												<p class="mt-1 text-xs font-mono text-slate-500">
													{finding.file}{finding.line ? `:${finding.line}` : ''}
												</p>
											{/if}
										</div>
									</div>
								</div>
							{/if}
						{/each}
					{/if}
				</div>
			</div>
		</div>
	{/if}
</div>
