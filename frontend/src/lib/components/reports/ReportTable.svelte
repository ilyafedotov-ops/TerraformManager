<script lang="ts">
import ReportActions from '$lib/components/reports/ReportActions.svelte';
import type { ReportSummary } from '$lib/api/client';
import { createEventDispatcher } from 'svelte';

/**
 * Present a table of report summaries with contextual actions sourced from the reviewer API.
 */
interface Props {
    reports: ReportSummary[];
    apiBase: string;
    token?: string | null;
    deletingId?: string | null;
}

const props: Props = $props();

const dispatch = createEventDispatcher<{ delete: { id: string } }>();

const formatDate = (value?: string) => {
	if (!value) return '—';
	const date = new Date(value);
	return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
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

const formatCurrency = (amount: number | null | undefined, currency?: string | null) => {
    if (amount === null || amount === undefined) return '—';
    if (!currency) {
        return amount.toFixed(2);
    }
    try {
        return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
    } catch (error) {
        return `${currency} ${amount.toFixed(2)}`;
    }
};

const costDelta = (summary?: ReportSummary['summary']) => {
    const cost = summary?.cost;
    if (!cost) return '—';
    const value = cost.diff_monthly_cost ?? cost.total_monthly_cost ?? null;
    return formatCurrency(value, cost.currency ?? undefined);
};

const driftStatus = (summary?: ReportSummary['summary']) => {
    const drift = summary?.drift;
    if (!drift) return '—';
    const total = drift.total_changes ?? 0;
    const label = drift.has_changes ? 'Changes' : 'No drift';
    return `${label} (${total})`;
};

const isDeleting = (id: string) => props.deletingId === id;
</script>

<div class="overflow-x-auto rounded-3xl border border-blueGray-200 bg-white shadow-xl shadow-blueGray-300/40">
	<table class="min-w-full divide-y divide-blueGray-100 text-sm">
		<thead class="bg-blueGray-50 text-xs uppercase tracking-[0.3em] text-blueGray-400">
			<tr>
				<th class="px-6 py-4 text-left">Report ID</th>
				<th class="px-6 py-4 text-left">Created</th>
				<th class="px-6 py-4 text-left">Severity</th>
				<th class="px-6 py-4 text-left">Issues</th>
				<th class="px-6 py-4 text-left">Cost Δ</th>
				<th class="px-6 py-4 text-left">Drift</th>
				<th class="px-6 py-4 text-right">Actions</th>
			</tr>
		</thead>
		<tbody class="divide-y divide-blueGray-100 text-blueGray-500">
			{#each props.reports as report (report.id)}
				<tr class="hover:bg-lightBlue-50">
					<td class="px-6 py-4 font-mono text-sm text-blueGray-600">{report.id}</td>
					<td class="px-6 py-4">{formatDate(report.created_at)}</td>
					<td class="px-6 py-4 uppercase tracking-[0.2em] text-blueGray-500">{severityLabel(report.summary)}</td>
					<td class="px-6 py-4">{issuesCount(report.summary)}</td>
					<td class="px-6 py-4">{costDelta(report.summary)}</td>
					<td class="px-6 py-4">{driftStatus(report.summary)}</td>
					<td class="px-6 py-4 text-right">
						<ReportActions
							id={report.id}
							apiBase={props.apiBase}
							viewHref={`/reports/${report.id}`}
							deleting={isDeleting(report.id)}
							deleteEnabled={Boolean(props.token)}
							on:delete={() => dispatch('delete', { id: report.id })}
						/>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
