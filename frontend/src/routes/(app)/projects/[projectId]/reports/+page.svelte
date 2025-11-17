<script lang="ts">
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
import { browser } from '$app/environment';
import type { PageData, PageProps } from './$types';

	const { data, params } = $props<{ data: PageData; params: PageProps['params'] }>();
const token = data.token as string | null;
const projectId = params.projectId ?? null;
const initialPayload = (data.reports ?? null) as ReportListResponse | null;
let error = $state<string | undefined>(data.error as string | undefined);
let reportsPayload = $state<ReportListResponse | null>(initialPayload);
let reports = $state<ReportSummary[]>(initialPayload?.items ?? []);
let deleteStatus = $state<string | null>(null);
let deletingId = $state<string | null>(null);
let isLoading = $state(false);
let filterError = $state<string | null>(null);
let pageSize = $state<number>(initialPayload?.limit ?? 50);
let offset = $state<number>(initialPayload?.offset ?? 0);
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
let totalCount = $state<number>(initialPayload?.total_count ?? 0);

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
		order: overrides?.order ?? 'desc'
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
	if (!token) return;
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

const submitSearch = async (event?: Event) => {
	event?.preventDefault();
	await refreshReports({ offset: 0 });
};

const changePageSize = async (value: number) => {
	pageSize = value;
	await refreshReports({ limit: value, offset: 0 });
};

const goToPreviousPage = async () => {
	if (offset <= 0) return;
	const nextOffset = Math.max(offset - pageSize, 0);
	await refreshReports({ offset: nextOffset });
};

const goToNextPage = async () => {
	if (!reportsPayload?.has_more) return;
	const nextOffset = reportsPayload.next_offset ?? offset + pageSize;
	await refreshReports({ offset: nextOffset });
};

const selectReport = async (id: string) => {
	if (selectedReportId === id) {
		return;
	}
	const record = reports.find((item) => item.id === id) ?? null;
	selectedReportId = record ? id : null;
	syncReviewForm(record ?? null);
	reviewMessage = null;
	reviewError = null;
	commentDraft = '';
	commentError = null;
	if (record && token) {
		await loadComments(id);
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

$effect(() => {
	const aggregates = reportsPayload?.aggregates;
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

$effect(() => {
	const record = reports.find((item) => item.id === selectedReportId) ?? null;
	selectedReport = record;
	syncReviewForm(record);
	if (!record) {
		comments = [];
		commentDraft = '';
		commentError = null;
	}
});

</script>

<section class="space-y-6">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Reports</p>
		<h2 class="text-3xl font-semibold text-slate-700">Saved reviewer results</h2>
		<p class="max-w-3xl text-sm text-slate-500">
			Track reviewer assignments, resolve findings, and export artifacts from saved scans. Use the filters to focus on a
			review queue or severity band.
		</p>
	</header>

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
						onclick={() => void clearFilters()}
							class="inline-flex items-center rounded-2xl border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-100"
						>
							Reset
						</button>
						{#if filterError}
							<span class="text-xs text-rose-600">{filterError}</span>
						{/if}
					</div>
				</form>

				{#if sortedSeverityCounts.length}
					<div class="mt-6 space-y-2">
						<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Severity breakdown</p>
						<ul class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
							{#each sortedSeverityCounts as [severity, count]}
								<li class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
									<span class="font-semibold uppercase tracking-[0.25em] text-slate-500">{severity}</span>
									<span class="ml-3 text-slate-700">{count}</span>
								</li>
							{/each}
						</ul>
					</div>
				{/if}
			</div>

			{#if isLoading}
				<div class="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6 text-sm text-slate-500">Loading reports…</div>
			{/if}

			{#if !isLoading && reports.length === 0}
				<div class="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6 text-sm text-slate-500">
					{#if projectId}
						No saved reports are linked to this project yet. Run <code class="rounded bg-slate-100 px-1 py-0.5 text-xs text-slate-600">python -m backend.cli scan sample --project-id {projectId} --out tmp/report.json</code> or upload Terraform from the Review tab to log a report.
					{:else}
						No reports match the current filters. Run <code class="rounded bg-slate-100 px-1 py-0.5 text-xs text-slate-600">python -m backend.cli scan sample --out tmp/report.json</code> to generate a sample review.
					{/if}
				</div>
			{/if}

			{#if reports.length}
                <ReportTable
                    reports={reports}
                    projectId={projectId}
                    token={token}
					deletingId={deletingId}
					selectable={true}
					selectedId={selectedReportId}
					on:delete={(event) => void handleDelete(event.detail.id)}
					on:select={(event) => void selectReport(event.detail.id)}
				/>

				<div class="flex flex-col gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm shadow-slate-300/40 sm:flex-row sm:items-center sm:justify-between">
					<span>
						Page {Math.floor(offset / pageSize) + 1} · Showing {reports.length} of {totalCount} reports
					</span>
					<div class="flex items-center gap-2">
					<button
						type="button"
						onclick={() => void goToPreviousPage()}
							disabled={offset <= 0}
							class="inline-flex items-center rounded-2xl border border-slate-200 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
						>
							Prev
						</button>
					<button
						type="button"
						onclick={() => void goToNextPage()}
							disabled={!reportsPayload?.has_more}
							class="inline-flex items-center rounded-2xl border border-slate-200 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
						>
							Next
						</button>
					</div>
				</div>
			{/if}
		</div>

		<aside class="space-y-6">
			<div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
				<h3 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Review inspector</h3>
				{#if selectedReport}
					{@const active = selectedReport as ReportSummary}
					<div class="mt-4 space-y-4 text-sm text-slate-600">
						<div class="space-y-2">
							<p class="font-semibold text-slate-700">Report {active.id}</p>
							<p class="text-xs text-slate-500">Created {formatDateTime(active.created_at)} · Updated {formatDateTime(active.updated_at)}</p>
							<p class="text-xs text-slate-500">Severity top: {topSeverityLabel(active.summary)} · Issues {active.summary?.issues_found ?? 0}</p>
						</div>

					<form
						class="space-y-3"
						onsubmit={(event) => {
							event.preventDefault();
							void saveReviewMetadata();
						}}
					>
							<label class="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
								<span>Status</span>
								<select
									class="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
									bind:value={reviewForm.review_status}
								>
									{#each statusOptions as status}
										<option value={status}>{formatStatusLabel(status)}</option>
									{/each}
								</select>
							</label>

							<label class="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
								<span>Assignee</span>
								<input
									type="text"
									class="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
									placeholder="owner@example.com"
									bind:value={reviewForm.review_assignee}
								/>
							</label>

							<label class="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
								<span>Due date</span>
								<input
									type="date"
									class="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
									bind:value={reviewForm.review_due_at}
								/>
							</label>

							<label class="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
								<span>Notes</span>
								<textarea
									rows="3"
									class="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
									placeholder="State, escalations, or follow-ups"
									bind:value={reviewForm.review_notes}
								></textarea>
							</label>

							<div class="flex items-center gap-3">
								<button
									type="submit"
									disabled={reviewSaving}
									class="inline-flex items-center rounded-2xl bg-sky-500 px-5 py-2 text-sm font-semibold text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
								>
									{reviewSaving ? 'Saving…' : 'Save review' }
								</button>
								{#if reviewError}
									<span class="text-xs text-rose-600">{reviewError}</span>
								{:else if reviewMessage}
									<span class="text-xs text-emerald-600">{reviewMessage}</span>
								{/if}
							</div>
						</form>

						<section class="space-y-3">
							<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Discussion</h4>
							{#if commentsLoading}
								<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">Loading comments…</p>
							{:else if comments.length === 0}
								<p class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">No comments yet. Start the thread below.</p>
							{:else}
								<ul class="space-y-3">
									{#each comments as comment}
										<li class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
											<div class="flex items-start justify-between gap-3">
												<div>
													<p class="font-semibold text-slate-700">{comment.author ?? 'Reviewer'}</p>
													<p class="text-[0.7rem] text-slate-400">{formatDateTime(comment.created_at)}</p>
												</div>
								<button
									type="button"
									class="text-[0.65rem] font-semibold uppercase tracking-[0.25em] text-rose-500 transition hover:text-rose-600"
									onclick={() => void removeComment(comment.id)}
												>
													Remove
												</button>
											</div>
											<p class="mt-2 text-slate-600">{comment.body}</p>
										</li>
									{/each}
								</ul>
							{/if}

							<form
								class="space-y-2"
								onsubmit={(event) => {
									event.preventDefault();
									void submitComment(event);
								}}
							>
								<textarea
									rows="2"
									class="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-1 focus:ring-sky-400"
									placeholder="Add to the review log"
									bind:value={commentDraft}
								></textarea>
								<div class="flex items-center gap-3">
									<button
										type="submit"
										class="inline-flex items-center rounded-2xl border border-slate-200 px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500 transition hover:bg-slate-100"
									>
										Post
									</button>
									{#if commentError}
										<span class="text-xs text-rose-600">{commentError}</span>
									{/if}
								</div>
							</form>
						</section>
					</div>
				{:else}
					<p class="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-500">
						Select a report to manage review assignments and comments.
					</p>
				{/if}
			</div>

			<ProjectWorkspaceBanner context="Select a workspace to filter artifacts and contextualize saved reports." />

			<RunArtifactsPanel
				token={token}
				title="Project artifacts"
				emptyMessage="Select a project in the sidebar to explore run artifacts alongside saved reports."
			/>
		</aside>
	</div>
</section>
