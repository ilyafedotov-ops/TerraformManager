<script lang="ts">
import { browser } from '$app/environment';
import {
	listReports,
	deleteReport,
	updateReportReviewMetadata,
	listReportComments,
	createReportComment,
	deleteReportComment,
	ApiError,
	type ReportSummary,
	type ReportListResponse,
	type ReportComment,
	type ListReportsParams
} from '$lib/api/client';
import ReportTable from '$lib/components/reports/ReportTable.svelte';
import RunArtifactsPanel from '$lib/components/projects/RunArtifactsPanel.svelte';
import ProjectWorkspaceBanner from '$lib/components/projects/ProjectWorkspaceBanner.svelte';
import { notifyError } from '$lib/stores/notifications';

interface Props {
	token?: string | null;
	projectId?: string | null;
	projectSlug?: string | null;
	initialReports?: ReportListResponse | null;
	initialError?: string;
	showWorkspaceBanner?: boolean;
	heading?: string;
	description?: string;
}

const {
	token = null,
	projectId = null,
	projectSlug = null,
	initialReports = null,
	initialError = undefined,
	showWorkspaceBanner = true,
	heading = 'Saved reviewer results',
	description = 'Track reviewer assignments, resolve findings, and export artifacts from saved scans. Use the filters to focus on a review queue or severity band.'
}: Props = $props();

const projectIdentifier = $derived(projectId ?? null);
const workspaceKey = $derived(projectSlug ?? projectIdentifier ?? null);
const initialItems = initialReports?.items ?? [];

let error = $state<string | undefined>(initialError);
let reportsPayload = $state<ReportListResponse | null>(initialReports);
let reports = $state<ReportSummary[]>(initialItems);
let deleteStatus = $state<string | null>(null);
let deletingId = $state<string | null>(null);
let isLoading = $state(false);
let filterError = $state<string | null>(null);
let pageSize = $state<number>(initialReports?.limit ?? 50);
let offset = $state<number>(initialReports?.offset ?? 0);
let selectedStatuses = $state<string[]>([]);
let searchTerm = $state('');
let assigneeFilter = $state('');
let selectedReportId = $state<string | null>(null);
let selectedReport = $state<ReportSummary | null>(null);
let reviewForm = $state({
	review_status: 'pending',
	review_assignee: '',
	review_due_at: '',
	review_notes: ''
});
let reviewSaving = $state(false);
let reviewMessage = $state<string | null>(null);
let reviewError = $state<string | null>(null);
let comments = $state<ReportComment[]>([]);
let commentsLoading = $state(false);
let commentDraft = $state('');
let commentError = $state<string | null>(null);

const statusOptions = ['pending', 'in_review', 'changes_requested', 'resolved', 'waived'] as const;
let statusCounts = $state<Record<string, number>>({});
let sortedSeverityCounts = $state<Array<[string, number]>>([]);
let totalCount = $state<number>(initialReports?.total_count ?? initialItems.length ?? 0);

const toErrorMessage = (err: unknown): string => {
	if (err instanceof ApiError) {
		const detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
		return detail ? `${err.message}: ${detail}` : err.message;
	}
	if (err instanceof Error) {
		return err.message;
	}
	return 'Unexpected error occurred.';
};

const formatDateTime = (value?: string | null) => {
	if (!value) return '—';
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return value;
	return date.toLocaleString();
};

const formatStatusLabel = (value: string) =>
	value
		.split('_')
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(' ');

const topSeverityLabel = (summary?: ReportSummary['summary']) => {
	const counts = summary?.severity_counts;
	if (!counts) return '—';
	const [severity] =
		Object.entries(counts)
			.sort((a, b) => Number(b[1] ?? 0) - Number(a[1] ?? 0))[0] ?? [];
	return severity ?? '—';
};

const toDateInputValue = (value?: string | null) => {
	if (!value) return '';
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return '';
	return date.toISOString().slice(0, 10);
};

const fromDateInputValue = (value: string) => {
	if (!value) return null;
	return new Date(`${value}T00:00:00Z`).toISOString();
};

const buildListParams = (overrides: Partial<ListReportsParams> = {}): ListReportsParams => {
	const statuses = overrides?.status ?? (selectedStatuses.length ? selectedStatuses : undefined);
	const params = {
		limit: overrides?.limit ?? pageSize,
		offset: overrides?.offset ?? offset,
		status: statuses,
		assignee: overrides?.assignee ?? (assigneeFilter ? assigneeFilter : undefined),
		search: overrides?.search ?? (searchTerm ? searchTerm : undefined),
		created_after: overrides?.created_after,
		created_before: overrides?.created_before,
		order: overrides?.order ?? 'desc',
		project_id: projectIdentifier ?? undefined
	};
	return params;
};

const syncReviewForm = (record: ReportSummary | null) => {
	if (!record) {
		reviewForm = {
			review_status: 'pending',
			review_assignee: '',
			review_due_at: '',
			review_notes: ''
		};
		return;
	}
	reviewForm = {
		review_status: record.review_status ?? 'pending',
		review_assignee: record.review_assignee ?? '',
		review_due_at: toDateInputValue(record.review_due_at),
		review_notes: record.review_notes ?? ''
	};
};

const refreshReports = async (overrides: Partial<ListReportsParams> = {}) => {
	const identifier = projectIdentifier;
	if (!token || !identifier) {
		filterError = !token ? 'Missing API token' : 'Project context missing';
		return;
	}
	isLoading = true;
	filterError = null;
	try {
		const params = buildListParams(overrides);
		const response = await listReports(fetch, token, params);
		reportsPayload = response;
		reports = response.items ?? [];
		offset = response.offset;
		pageSize = response.limit;
		if (selectedReportId && !(response.items ?? []).some((item) => item.id === selectedReportId)) {
			selectedReportId = null;
			comments = [];
		}
		error = undefined;
	} catch (err) {
		filterError = toErrorMessage(err);
		reportsPayload = null;
		reports = [];
	} finally {
		isLoading = false;
	}
};

const handleDelete = async (id: string) => {
	if (!token) {
		deleteStatus = 'Missing API token; cannot delete reports.';
		return;
	}
	if (browser) {
		const confirmed = window.confirm(`Delete report ${id}? This action cannot be undone.`);
		if (!confirmed) {
			return;
		}
	}
	deletingId = id;
	deleteStatus = null;
	try {
		await deleteReport(fetch, token, id);
		deleteStatus = `Report ${id} deleted.`;
		await refreshReports({ offset: 0 });
	} catch (err) {
		deleteStatus = toErrorMessage(err);
	} finally {
		deletingId = null;
	}
};

const toggleStatus = async (value: string) => {
	selectedStatuses = selectedStatuses.includes(value)
		? selectedStatuses.filter((status) => status !== value)
		: [...selectedStatuses, value];
	await refreshReports({ offset: 0 });
};

const clearFilters = async () => {
	selectedStatuses = [];
	searchTerm = '';
	assigneeFilter = '';
	await refreshReports({ offset: 0 });
};

const changePageSize = async (size: number) => {
	pageSize = size;
	await refreshReports({ limit: size, offset: 0 });
};

const submitSearch = async (event?: Event) => {
	event?.preventDefault();
	await refreshReports({ offset: 0 });
};

const goToPage = async (nextOffset: number) => {
	await refreshReports({ offset: nextOffset });
};

const selectReport = async (id: string | null) => {
	selectedReportId = id;
	const record = reports.find((item) => item.id === id);
	selectedReport = record ?? null;
	syncReviewForm(record ?? null);
	reviewMessage = null;
	reviewError = null;
	commentDraft = '';
	commentError = null;
	if (record && token) {
		await loadComments(id!);
	} else {
		comments = [];
	}
};

const saveReviewMetadata = async () => {
	if (!token || !selectedReportId) return;
	reviewSaving = true;
	reviewError = null;
	reviewMessage = null;
	const payload = {
		review_status: reviewForm.review_status,
		review_assignee: reviewForm.review_assignee.trim() || null,
		review_due_at: reviewForm.review_due_at ? fromDateInputValue(reviewForm.review_due_at) : null,
		review_notes: reviewForm.review_notes.trim() || null
	};
	try {
		const response = await updateReportReviewMetadata(fetch, token, selectedReportId, payload);
		reports = reports.map((item) =>
			item.id === selectedReportId
				? {
					...item,
					review_status: response.review_status ?? item.review_status,
					review_assignee: response.review_assignee ?? item.review_assignee,
					review_due_at: response.review_due_at ?? item.review_due_at,
					review_notes: response.review_notes ?? item.review_notes,
					updated_at: response.updated_at ?? item.updated_at
				}
				: item
		);
		if (reportsPayload) {
			reportsPayload = {
				...reportsPayload,
				items: [...reports]
			};
		}
		reviewMessage = 'Review metadata saved.';
		await refreshReports();
	} catch (err) {
		reviewError = toErrorMessage(err);
	} finally {
		reviewSaving = false;
	}
};

const loadComments = async (reportId: string) => {
	if (!token) return;
	commentsLoading = true;
	commentError = null;
	try {
		comments = await listReportComments(fetch, token, reportId);
	} catch (err) {
		commentError = toErrorMessage(err);
		comments = [];
	} finally {
		commentsLoading = false;
	}
};

const submitComment = async (event?: Event) => {
	event?.preventDefault();
	if (!token || !selectedReportId) return;
	const trimmed = commentDraft.trim();
	if (!trimmed) {
		commentError = 'Enter a comment before posting.';
		return;
	}
	commentError = null;
	try {
		const comment = await createReportComment(fetch, token, selectedReportId, trimmed);
		comments = [...comments, comment];
		commentDraft = '';
		await refreshReports();
	} catch (err) {
		commentError = toErrorMessage(err);
	}
};

const removeComment = async (commentId: string) => {
	if (!token || !selectedReportId) return;
	try {
		await deleteReportComment(fetch, token, selectedReportId, commentId);
		comments = comments.filter((comment) => comment.id !== commentId);
		await refreshReports();
	} catch (err) {
		commentError = toErrorMessage(err);
	}
};

let lastPayloadKey: string | null = null;
$effect(() => {
	const aggregates = reportsPayload?.aggregates;
	const payloadKey = reportsPayload ? `${reportsPayload.offset}:${reportsPayload.total_count}` : null;
	if (payloadKey !== lastPayloadKey) {
		lastPayloadKey = payloadKey;
	}
	if (aggregates) {
		statusCounts = (aggregates.status_counts ?? {}) as Record<string, number>;
		sortedSeverityCounts = Object.entries((aggregates.severity_counts ?? {}) as Record<string, number>)
			.map(([severity, value]) => [severity, Number(value ?? 0)] as [string, number])
			.sort((a, b) => b[1] - a[1]);
	} else {
		const fallbackStatus: Record<string, number> = {};
		const fallbackSeverity: Record<string, number> = {};
		for (const record of reports) {
			const key = (record.review_status ?? 'pending').toLowerCase();
			fallbackStatus[key] = (fallbackStatus[key] ?? 0) + 1;
			const counts = record.summary?.severity_counts ?? {};
			for (const [severity, value] of Object.entries(counts)) {
				fallbackSeverity[severity] = (fallbackSeverity[severity] ?? 0) + Number(value ?? 0);
			}
		}
		statusCounts = fallbackStatus;
		sortedSeverityCounts = Object.entries(fallbackSeverity).sort((a, b) => b[1] - a[1]);
	}
	totalCount = reportsPayload?.total_count ?? reports.length;
});

let lastReportKey: string | null = null;
$effect(() => {
	const record = reports.find((item) => item.id === selectedReportId) ?? null;
	selectedReport = record;
	syncReviewForm(record);
	if (!record) {
		comments = [];
		commentDraft = '';
		commentError = null;
	}
	const key = record?.id ?? null;
	if (key !== lastReportKey) {
		lastReportKey = key;
		if (record && token) {
			void loadComments(record.id);
		}
	}
});

let autoLoadKey: string | null = null;
$effect(() => {
	const identifier = projectIdentifier ?? workspaceKey;
	if (!identifier || !token) {
		return;
	}
	const key = `${identifier}:${token}`;
	if (key === autoLoadKey) {
		return;
	}
	autoLoadKey = key;
	if (reportsPayload?.items?.length) {
		return;
	}
	void refreshReports({ offset: 0 }).catch((err) => {
		console.warn('Failed to load project reports', err);
		notifyError('Unable to load project reports.');
	});
});

let lastWorkspaceKey: string | null = null;
$effect(() => {
	const key = workspaceKey;
	if (key === lastWorkspaceKey) {
		return;
	}
	lastWorkspaceKey = key;
	if (!initialReports) {
		reportsPayload = null;
		reports = [];
		offset = 0;
		totalCount = 0;
		deleteStatus = null;
		filterError = null;
	}
	selectedReportId = null;
	selectedReport = null;
	comments = [];
	commentDraft = '';
	commentError = null;
	reviewForm = {
		review_status: 'pending',
		review_assignee: '',
		review_due_at: '',
		review_notes: ''
	};
});
</script>

<section class="space-y-6">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Reports</p>
		<h2 class="text-3xl font-semibold text-slate-700">{heading}</h2>
		<p class="max-w-3xl text-sm text-slate-500">
			{description}
		</p>
	</header>

	{#if showWorkspaceBanner}
		<ProjectWorkspaceBanner context="Reports, comments, and review notes stay scoped to this project workspace." />
	{/if}

	{#if error}
		<div class="rounded-3xl border border-rose-300 bg-rose-50 px-6 py-4 text-sm text-rose-700">
			<strong class="font-semibold">Failed to load reports.</strong>
			<span class="ml-2 text-rose-600">{error}</span>
		</div>
	{/if}

	{#if deleteStatus}
		<div class="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-3 text-xs text-slate-600">{deleteStatus}</div>
	{/if}

	<div class="grid gap-6 xl:grid-cols-[2fr_1fr]">
		<div class="space-y-6">
			<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<div class="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Total</p>
					<p class="mt-3 text-3xl font-semibold text-slate-700">{totalCount}</p>
				</div>
				{#each statusOptions as status}
					<div class="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
						<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{formatStatusLabel(status)}</p>
						<p class="mt-3 text-2xl font-semibold text-slate-700">{statusCounts[status] ?? 0}</p>
					</div>
				{/each}
			</div>

			<div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
				<form
					class="space-y-4"
					onsubmit={(event) => {
						event.preventDefault();
						void submitSearch(event);
					}}
				>
					<div class="grid gap-4 md:grid-cols-3">
						<label class="flex flex-col gap-2 text-sm font-medium text-slate-600">
							<span class="text-xs uppercase tracking-[0.3em] text-slate-400">Search</span>
							<input
								type="search"
								class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
								placeholder="Report ID, notes, assignee"
								bind:value={searchTerm}
							/>
						</label>
						<label class="flex flex-col gap-2 text-sm font-medium text-slate-600">
							<span class="text-xs uppercase tracking-[0.3em] text-slate-400">Assignee</span>
							<input
								type="text"
								class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
								placeholder="alice@example.com"
								bind:value={assigneeFilter}
							/>
						</label>
						<label class="flex flex-col gap-2 text-sm font-medium text-slate-600">
							<span class="text-xs uppercase tracking-[0.3em] text-slate-400">Page size</span>
							<select
								class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
								value={pageSize}
								onchange={(event) => void changePageSize(Number((event.currentTarget as HTMLSelectElement).value))}
							>
								<option value="20">20</option>
								<option value="50">50</option>
								<option value="100">100</option>
							</select>
						</label>
					</div>

					<div class="flex flex-wrap gap-3">
						{#each statusOptions as status}
							<button
								type="button"
								onclick={() => void toggleStatus(status)}
								class={`rounded-2xl border px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] transition ${
									selectedStatuses.includes(status)
										? 'border-sky-400 bg-sky-50 text-sky-600'
										: 'border-slate-200 bg-slate-50 text-slate-500 hover:border-slate-300'
								}`}
							>
								{formatStatusLabel(status)}
							</button>
						{/each}
					</div>

					<div class="flex flex-wrap items-center gap-3">
						<button
							type="submit"
							class="inline-flex items-center rounded-2xl bg-sky-500 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-600"
						>
							Apply filters
						</button>
						<button
							type="button"
							class="inline-flex items-center rounded-2xl border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
							onclick={() => void clearFilters()}
						>
							Clear
						</button>
						{#if filterError}
							<span class="text-xs text-rose-500">{filterError}</span>
						{/if}
					</div>
				</form>
			</div>

			<div>
				<ReportTable
					token={token}
					projectId={projectIdentifier ?? undefined}
					data={reportsPayload}
					items={reports}
					isLoading={isLoading}
					offset={offset}
					limit={pageSize}
					on:pageChange={(event) => void goToPage(event.detail)}
					on:select={(event) => void selectReport(event.detail)}
					on:delete={(event) => void handleDelete(event.detail)}
					deletingId={deletingId}
					selectedId={selectedReportId}
				/>
			</div>
		</div>
		<div class="space-y-6">
			<section class="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/30">
				<header class="space-y-1 border-b border-slate-100 pb-3">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Review metadata</p>
					{#if selectedReport}
						<h3 class="text-xl font-semibold text-slate-700">Report {selectedReport.id}</h3>
						<p class="text-xs text-slate-500">Created {formatDateTime(selectedReport.created_at)}</p>
					{:else}
						<h3 class="text-xl font-semibold text-slate-700">Select a report</h3>
						<p class="text-xs text-slate-500">Choose a report to edit review metadata.</p>
					{/if}
				</header>
				{#if selectedReport}
					<form class="space-y-4 text-sm text-slate-600" onsubmit={(event) => event.preventDefault()}>
						<label class="block text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
							Status
							<select
								class="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
								bind:value={reviewForm.review_status}
							>
								{#each statusOptions as status}
									<option value={status}>{formatStatusLabel(status)}</option>
								{/each}
							</select>
						</label>
						<label class="block text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
							Assignee
							<input
								class="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
								type="text"
								placeholder="owner@example.com"
								bind:value={reviewForm.review_assignee}
							/>
						</label>
						<label class="block text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
							Review due date
							<input
								class="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
								type="date"
								bind:value={reviewForm.review_due_at}
							/>
						</label>
						<label class="block text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
							Notes
							<textarea
								class="mt-2 min-h-[5rem] w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
								placeholder="Approval details, waivers, or remediation hints"
								bind:value={reviewForm.review_notes}
							></textarea>
						</label>
						<div class="flex flex-wrap items-center gap-3 text-xs">
							<button
								type="button"
								class={`rounded-2xl bg-sky-500 px-4 py-2 font-semibold text-white shadow-sm transition hover:bg-sky-600 ${
									reviewSaving ? 'cursor-wait opacity-70' : ''
								}`}
								onclick={() => void saveReviewMetadata()}
								disabled={reviewSaving}
							>
								{reviewSaving ? 'Saving…' : 'Save metadata'}
							</button>
							{#if reviewMessage}
								<span class="text-emerald-600">{reviewMessage}</span>
							{/if}
							{#if reviewError}
								<span class="text-rose-500">{reviewError}</span>
							{/if}
						</div>
					</form>
				{:else}
					<p class="text-sm text-slate-500">Select a report to edit metadata.</p>
				{/if}
			</section>

			<section class="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/30">
				<header class="space-y-1">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Severity distribution</p>
					<p class="text-sm text-slate-500">Top severity: {topSeverityLabel(selectedReport?.summary)}</p>
				</header>
				{#if sortedSeverityCounts.length}
					<ul class="mt-4 space-y-2 text-sm text-slate-600">
						{#each sortedSeverityCounts as [severity, count]}
							<li class="flex items-center justify-between rounded-2xl border border-slate-100 px-3 py-2">
								<span class="font-semibold uppercase tracking-[0.3em] text-slate-400">{severity}</span>
								<span class="text-base text-slate-700">{count}</span>
							</li>
						{/each}
					</ul>
				{:else}
					<p class="mt-3 text-sm text-slate-500">No severity data available.</p>
				{/if}
			</section>

			<section class="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/30">
				<header class="space-y-1">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Comments</p>
					<p class="text-sm text-slate-500">
						{#if selectedReport}
							Reviewers can coordinate remediation steps inline.
						{:else}
							Select a report to view discussion.
						{/if}
					</p>
				</header>
				{#if selectedReport}
					<form class="mt-3 space-y-3" onsubmit={(event) => void submitComment(event)}>
						<textarea
							class="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
							placeholder="Share remediation updates..."
							bind:value={commentDraft}
						></textarea>
						<div class="flex flex-wrap items-center gap-2 text-xs">
							<button
								type="submit"
								class="rounded-2xl bg-sky-500 px-4 py-2 font-semibold text-white shadow-sm transition hover:bg-sky-600"
							>
								Post comment
							</button>
							{#if commentError}
								<span class="text-rose-500">{commentError}</span>
							{/if}
						</div>
					</form>
					<div class="mt-4 space-y-2">
						{#if commentsLoading}
							<p class="text-sm text-slate-500">Loading comments…</p>
						{:else if !comments.length}
							<p class="text-sm text-slate-500">No comments yet.</p>
						{:else}
							<ul class="space-y-2 text-sm text-slate-600">
								{#each comments as comment (comment.id)}
									<li class="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2">
										<div class="flex items-center justify-between text-xs text-slate-400">
											<span>{comment.author ?? 'Reviewer'}</span>
											<span>{formatDateTime(comment.created_at)}</span>
										</div>
										<p class="mt-1 text-slate-600">{comment.body}</p>
										<button
											type="button"
											class="mt-2 text-xs font-semibold text-rose-500"
											onclick={() => void removeComment(comment.id)}
										>
											Delete
										</button>
									</li>
								{/each}
							</ul>
						{/if}
					</div>
				{:else}
					<p class="mt-3 text-sm text-slate-500">Select a report to view and add comments.</p>
				{/if}
			</section>
		</div>
	</div>

	<section>
		<RunArtifactsPanel
			token={token}
			title="Run artifacts"
			emptyMessage="Generate a run to browse its output artifacts."
		/>
	</section>
</section>
