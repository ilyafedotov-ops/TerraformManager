import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import ReportTable from '../ReportTable.svelte';
import type { ReportSummary } from '$lib/api/client';

const buildReport = (overrides: Partial<ReportSummary> = {}): ReportSummary => ({
	id: 'rpt-1',
	created_at: '2024-01-01T12:00:00Z',
	summary: {
		issues_found: 5,
		severity_counts: {
			critical: 2,
			high: 3
		}
	},
	...overrides
});

describe('ReportTable', () => {
	const apiBase = 'https://api.example.dev';

	it('renders report rows with formatted details', () => {
		const reports = [buildReport(), buildReport({ id: 'rpt-2', created_at: '2024-01-02T14:00:00Z' })];
		const { getByText, getAllByText } = render(ReportTable, {
			props: { reports, apiBase, token: 'token-123', deletingId: null }
		});

		expect(getByText('rpt-1')).toBeInTheDocument();
		expect(getAllByText(/high/i)[0]).toBeInTheDocument();
		expect(getAllByText('5')[0]).toBeInTheDocument();
		expect(getByText('rpt-2')).toBeInTheDocument();
	});

	it('emits delete event when a row delete action is triggered', async () => {
		const reports = [buildReport()];
		const handler = vi.fn();
		const { getByText } = render(ReportTable, {
			props: { reports, apiBase, token: 'token-123', deletingId: null },
			events: { delete: (event: CustomEvent<{ id: string }>) => handler(event.detail.id) }
		});

		await fireEvent.click(getByText('Delete'));

		expect(handler).toHaveBeenCalledWith('rpt-1');
	});

	it('disables delete action when no token is provided', async () => {
		const reports = [buildReport()];
		const { getByText } = render(ReportTable, {
			props: { reports, apiBase, token: null, deletingId: null }
		});

		expect(getByText('Delete')).toBeDisabled();
	});

	it('renders project-scoped view links when a projectId is provided', () => {
		const reports = [buildReport()];
		const { getByText } = render(ReportTable, {
			props: { reports, apiBase, token: 'token-123', deletingId: null, projectId: 'proj-123' }
		});

		expect(getByText('View')).toHaveAttribute(
			'href',
			'/projects?project=proj-123&tab=reports&report=rpt-1'
		);
	});
});
