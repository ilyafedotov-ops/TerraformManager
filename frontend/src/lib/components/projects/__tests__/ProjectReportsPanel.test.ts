import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { describe, expect, it, beforeEach, vi } from 'vitest';
import type { ReportListResponse, ReportSummary } from '$lib/api/client';
import RunArtifactsPanelStub from './stubs/RunArtifactsPanelStub.svelte';
import ReportActionsStub from './stubs/ReportActionsStub.svelte';
import ReportTableStub from './stubs/ReportTableStub.svelte';

const {
	mockListReports,
	mockUpdateReportReviewMetadata,
	mockListReportComments,
	mockCreateReportComment,
	mockDeleteReportComment,
	mockDeleteReport
} = vi.hoisted(() => ({
	mockListReports: vi.fn(),
	mockUpdateReportReviewMetadata: vi.fn(),
	mockListReportComments: vi.fn(),
	mockCreateReportComment: vi.fn(),
	mockDeleteReportComment: vi.fn(),
	mockDeleteReport: vi.fn()
}));

vi.mock('$lib/components/projects/RunArtifactsPanel.svelte', () => ({
	default: RunArtifactsPanelStub
}));

vi.mock('$lib/components/reports/ReportActions.svelte', () => ({
	default: ReportActionsStub
}));

vi.mock('$lib/components/reports/ReportTable.svelte', () => ({
	default: ReportTableStub
}));

vi.mock('$lib/api/client', async (importOriginal) => {
	const actual = (await importOriginal()) as typeof import('$lib/api/client');
	return {
		...actual,
		listReports: mockListReports,
		deleteReport: mockDeleteReport,
		updateReportReviewMetadata: mockUpdateReportReviewMetadata,
		listReportComments: mockListReportComments,
		createReportComment: mockCreateReportComment,
		deleteReportComment: mockDeleteReportComment
	};
});

import ProjectReportsPanel from '../ProjectReportsPanel.svelte';

const baseReport: ReportSummary = {
	id: 'rpt-1',
	review_status: 'pending',
	review_assignee: 'alice@example.com',
	review_due_at: '2024-01-01T00:00:00Z',
	created_at: '2024-01-01T00:00:00Z',
	summary: {
		severity_counts: { high: 1 },
		issues_found: 1,
		cost: { diff_monthly_cost: 10, currency: 'USD' },
		drift: { has_changes: true, total_changes: 1 }
	}
};

const baseResponse: ReportListResponse = {
	items: [baseReport],
	total_count: 1,
	limit: 50,
	offset: 0,
	has_more: false,
	aggregates: {
		status_counts: { pending: 1 },
		severity_counts: { high: 1 }
	}
};

describe('ProjectReportsPanel', () => {
	beforeEach(() => {
	mockListReports.mockReset();
	mockUpdateReportReviewMetadata.mockReset();
	mockListReportComments.mockReset();
	mockCreateReportComment.mockReset();
	mockDeleteReportComment.mockReset();
	mockDeleteReport.mockReset();
	mockListReportComments.mockResolvedValue([]);
	mockDeleteReport.mockResolvedValue(undefined);
	});

	it('renders the provided report metrics and table entries', () => {
		const { getByText, getAllByText } = render(ProjectReportsPanel, {
			token: 'token',
			projectId: 'proj-1',
			projectSlug: 'proj-1',
			initialReports: baseResponse,
			showWorkspaceBanner: false
		});

		expect(getByText('Saved reviewer results')).toBeInTheDocument();
		expect(getByText('Total')).toBeInTheDocument();
		expect(getAllByText('Pending').length).toBeGreaterThan(0);
	});

	it('applies filters and refreshes the report list', async () => {
		const filteredReport: ReportSummary = {
			id: 'rpt-2',
			review_status: 'resolved',
			review_assignee: 'team@example.com',
			review_due_at: '2024-02-10T00:00:00Z',
			created_at: '2024-02-01T00:00:00Z',
			summary: {
				severity_counts: { low: 1 },
				issues_found: 0
			}
		};
		mockListReports.mockResolvedValueOnce({
			...baseResponse,
			items: [filteredReport],
			total_count: 1,
			aggregates: {
				status_counts: { resolved: 1 },
				severity_counts: { low: 1 }
			}
		});

		const { getByPlaceholderText, getByText, findByRole } = render(ProjectReportsPanel, {
			token: 'token',
			projectId: 'proj-1',
			projectSlug: 'proj-1',
			initialReports: baseResponse,
			showWorkspaceBanner: false
		});

		await fireEvent.input(getByPlaceholderText('Report ID, notes, assignee'), {
			target: { value: 'audit' }
		});
		await fireEvent.click(getByText('Apply filters'));

		await waitFor(() =>
			expect(mockListReports).toHaveBeenCalledWith(
				expect.any(Function),
				'token',
				expect.objectContaining({
					project_id: 'proj-1',
					project_slug: 'proj-1'
				})
			)
		);
		expect(await findByRole('button', { name: 'rpt-2' })).toBeInTheDocument();
	});

	it('fetches reports when only the project slug is available', async () => {
		mockListReports.mockResolvedValueOnce(baseResponse);

		const { getByText } = render(ProjectReportsPanel, {
			token: 'token',
			projectId: null,
			projectSlug: 'workspace-a',
			initialReports: baseResponse,
			showWorkspaceBanner: false
		});

		await fireEvent.click(getByText('Apply filters'));

		await waitFor(() =>
			expect(mockListReports).toHaveBeenCalledWith(
				expect.any(Function),
				'token',
				expect.objectContaining({
					project_id: undefined,
					project_slug: 'workspace-a'
				})
			)
		);
	});

	it('saves review metadata for a selected report', async () => {
		mockListReports.mockResolvedValue(baseResponse);
		mockUpdateReportReviewMetadata.mockResolvedValue({
			id: 'rpt-1',
			review_status: 'resolved',
			review_assignee: 'alice@example.com',
			review_due_at: '2024-02-01T00:00:00Z',
			review_notes: 'done',
			updated_at: '2024-02-01T00:00:00Z'
		});

		const { getByLabelText, getByText, findByText, getByRole } = render(ProjectReportsPanel, {
			token: 'token',
			projectId: 'proj-1',
			projectSlug: 'proj-1',
			initialReports: baseResponse,
			showWorkspaceBanner: false
		});

		await fireEvent.click(getByRole('button', { name: 'rpt-1' }));
		await waitFor(() =>
			expect(mockListReportComments).toHaveBeenCalledWith(
				expect.any(Function),
				'token',
				'rpt-1',
				expect.objectContaining({ projectId: 'proj-1', projectSlug: 'proj-1' })
			)
		);

		const statusSelect = getByLabelText('Status') as HTMLSelectElement;
		await fireEvent.change(statusSelect, { target: { value: 'resolved' } });
		await fireEvent.click(getByText('Save metadata'));

		await waitFor(() =>
			expect(mockUpdateReportReviewMetadata).toHaveBeenCalledWith(
				expect.any(Function),
				'token',
				'rpt-1',
				expect.objectContaining({ review_status: 'resolved' }),
				expect.objectContaining({ projectId: 'proj-1', projectSlug: 'proj-1' })
			)
		);
		expect(await findByText('Review metadata saved.')).toBeInTheDocument();
	});

	it('shows an error when attempting to delete without a token', async () => {
		const { findByText, getByText } = render(ProjectReportsPanel, {
			token: null,
			projectId: 'proj-1',
			projectSlug: 'proj-1',
			initialReports: baseResponse,
			showWorkspaceBanner: false
		});

		await fireEvent.click(getByText('Delete rpt-1'));

		expect(await findByText('Missing API token; cannot delete reports.')).toBeInTheDocument();
		expect(mockDeleteReport).not.toHaveBeenCalled();
	});

	it('surfaces API errors when deleting reports fails', async () => {
		mockDeleteReport.mockRejectedValueOnce(new Error('Delete failed'));
		const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);

		const { getByText, findByText } = render(ProjectReportsPanel, {
			token: 'token',
			projectId: 'proj-1',
			projectSlug: 'proj-1',
			initialReports: baseResponse,
			showWorkspaceBanner: false
		});

		await fireEvent.click(getByText('Delete rpt-1'));

		await waitFor(() => expect(mockDeleteReport).toHaveBeenCalledWith(expect.any(Function), 'token', 'rpt-1'));
		expect(await findByText('Delete failed')).toBeInTheDocument();
		confirmSpy.mockRestore();
	});
});
