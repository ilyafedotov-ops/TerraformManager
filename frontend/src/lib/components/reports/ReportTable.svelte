<script lang="ts">
import ReportActions from '$lib/components/reports/ReportActions.svelte';
import { API_BASE, type ReportSummary } from '$lib/api/client';
import { createEventDispatcher } from 'svelte';

/**
 * Present a table of report summaries with contextual actions sourced from the reviewer API.
 */
interface Props {
    reports: ReportSummary[];
    apiBase?: string;
    token?: string | null;
    deletingId?: string | null;
    selectable?: boolean;
    selectedId?: string | null;
    projectId?: string | null;
}

const props: Props = $props();

const dispatch = createEventDispatcher<{ delete: { id: string }; select: { id: string } }>();

const formatDate = (value?: string | null) => {
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
	} catch (_error) {
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

const apiBase = props.apiBase ?? API_BASE;
const isDeleting = (id: string) => props.deletingId === id;

const isSelected = (id: string) => props.selectedId === id;
const viewProjectId = props.projectId ?? null;

const statusBadgeClass = (status?: string | null) => {
    const value = status?.toLowerCase() ?? 'pending';
    switch (value) {
        case 'resolved':
            return 'bg-emerald-100 text-emerald-700 border-emerald-200';
        case 'in_review':
            return 'bg-sky-100 text-sky-700 border-sky-200';
        case 'changes_requested':
            return 'bg-amber-100 text-amber-700 border-amber-200';
        case 'waived':
            return 'bg-slate-200 text-slate-700 border-slate-300';
        default:
            return 'bg-slate-100 text-slate-600 border-slate-200';
    }
};

const formatStatus = (status?: string | null) => {
    if (!status) return 'Pending';
    return status
        .split('_')
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ');
};

const formatDueDate = (value?: string | null) => {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleDateString();
};

const handleRowClick = (report: ReportSummary) => {
    if (!props.selectable) return;
    dispatch('select', { id: report.id });
};
</script>

<div class="overflow-x-auto rounded-3xl border border-slate-200 bg-white shadow-xl shadow-slate-300/40">
    <div class="min-w-max">
        <table class="w-full divide-y divide-slate-100 text-sm">
            <thead class="bg-slate-50 text-xs uppercase tracking-[0.3em] text-slate-400">
                <tr>
                    <th class="whitespace-nowrap px-4 py-4 text-left sm:px-6">Report ID</th>
                    <th class="whitespace-nowrap px-4 py-4 text-left sm:px-6">Created</th>
                    <th class="whitespace-nowrap px-4 py-4 text-left sm:px-6">Status</th>
                    <th class="whitespace-nowrap px-4 py-4 text-left sm:px-6">Assignee</th>
                    <th class="whitespace-nowrap px-4 py-4 text-left sm:px-6">Due</th>
                    <th class="whitespace-nowrap px-4 py-4 text-left sm:px-6">Severity</th>
                    <th class="whitespace-nowrap px-4 py-4 text-left sm:px-6">Issues</th>
                    <th class="whitespace-nowrap px-4 py-4 text-left sm:px-6">Cost Δ</th>
                    <th class="whitespace-nowrap px-4 py-4 text-left sm:px-6">Drift</th>
                    <th class="whitespace-nowrap px-4 py-4 text-right sm:px-6">Actions</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 text-slate-500">
                {#each props.reports as report (report.id)}
                    <tr
                        class={`transition ${props.selectable ? 'cursor-pointer hover:bg-sky-50' : ''} ${isSelected(report.id) ? 'bg-sky-50' : ''}`}
                        onclick={() => handleRowClick(report)}
                    >
                        <td class="whitespace-nowrap px-4 py-4 font-mono text-sm text-slate-600 sm:px-6">{report.id}</td>
                        <td class="whitespace-nowrap px-4 py-4 sm:px-6">{formatDate(report.created_at)}</td>
                        <td class="px-4 py-4 sm:px-6">
                            <span class={`inline-flex items-center whitespace-nowrap rounded-full border px-3 py-1 text-xs font-semibold ${statusBadgeClass(report.review_status)}`}>
                                {formatStatus(report.review_status)}
                            </span>
                        </td>
                        <td class="max-w-[200px] truncate px-4 py-4 text-slate-600 sm:px-6" title={report.review_assignee ?? ''}>{report.review_assignee ?? '—'}</td>
                        <td class="whitespace-nowrap px-4 py-4 sm:px-6">{formatDueDate(report.review_due_at)}</td>
                        <td class="whitespace-nowrap px-4 py-4 uppercase tracking-[0.2em] text-slate-500 sm:px-6">{severityLabel(report.summary)}</td>
                        <td class="whitespace-nowrap px-4 py-4 sm:px-6">{issuesCount(report.summary)}</td>
                        <td class="whitespace-nowrap px-4 py-4 sm:px-6">{costDelta(report.summary)}</td>
                        <td class="whitespace-nowrap px-4 py-4 sm:px-6">{driftStatus(report.summary)}</td>
                        <td class="whitespace-nowrap px-4 py-4 text-right sm:px-6" onclick={(event) => event.stopPropagation()}>
                            <ReportActions
                                id={report.id}
                                apiBase={apiBase}
                                projectId={viewProjectId}
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
</div>
