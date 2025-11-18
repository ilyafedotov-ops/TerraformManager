import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import type { Writable } from 'svelte/store';
import type { ProjectRunSummary, ProjectSummary } from '$lib/api/client';

const { mockCreateRun, mockUpsertRun, mockUpdateProjectRun } = vi.hoisted(() => ({
	mockCreateRun: vi.fn(),
	mockUpsertRun: vi.fn(),
	mockUpdateProjectRun: vi.fn()
}));

vi.mock('$lib/stores/project', async () => {
	const { writable } = await import('svelte/store');
	const store = writable(null);
	return {
		activeProject: store,
		projectState: {
			createRun: mockCreateRun,
			upsertRun: mockUpsertRun
		}
	};
});

vi.mock('$lib/api/client', async (importOriginal) => {
	const actual = (await importOriginal()) as typeof import('$lib/api/client');
	return {
		...actual,
		updateProjectRun: mockUpdateProjectRun
	};
});

import ProjectReviewPanel from '../ProjectReviewPanel.svelte';
import { activeProject } from '$lib/stores/project';
import { API_BASE } from '$lib/api/client';

describe('ProjectReviewPanel', () => {
	let fetchMock: ReturnType<typeof vi.fn>;

	beforeEach(() => {
		mockCreateRun.mockReset();
		mockUpsertRun.mockReset();
		mockUpdateProjectRun.mockReset();
		fetchMock = vi.fn();
		globalThis.fetch = fetchMock as typeof fetch;
	});

	afterEach(() => {
		delete (globalThis as { fetch?: typeof fetch }).fetch;
	});

	it('shows an error when submitting without a token', async () => {
		const { getByLabelText, getByText, findByText } = render(ProjectReviewPanel, {
			token: null,
			projectId: 'proj-123',
			projectSlug: 'proj-123',
			showWorkspaceBanner: false
		});

		const fileInput = getByLabelText('Terraform files or zip archives') as HTMLInputElement;
		const mockFile = new File(['output'], 'main.tf', { type: 'text/plain' });
		await fireEvent.change(fileInput, { target: { files: [mockFile] } });

		await fireEvent.click(getByText('Run scan'));

		expect(await findByText(/API token missing/i)).toBeInTheDocument();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('submits a scan and renders the summary when the API succeeds', async () => {
		const responsePayload = {
			id: 'report-1',
			summary: {
				severity_counts: { high: 2 },
				issues_found: 2
			},
			report: { findings: [] }
		};
		fetchMock.mockResolvedValue({
			ok: true,
			json: async () => responsePayload,
			text: async () => ''
		} as Response);
		mockCreateRun.mockResolvedValue({ id: 'run-1' });
		mockUpdateProjectRun.mockResolvedValue({
			id: 'run-1',
			project_id: 'proj-1',
			label: 'Review',
			kind: 'review',
			status: 'completed'
		} satisfies ProjectRunSummary);
	const activeProjectStore = activeProject as unknown as Writable<ProjectSummary | null>;
	activeProjectStore.set({ id: 'proj-1', slug: 'proj-1', name: 'Demo project', root_path: '/workspace' });

		const { getByLabelText, getByText, findByText } = render(ProjectReviewPanel, {
			token: 'test-token',
			projectId: 'proj-1',
			projectSlug: 'proj-1',
			showWorkspaceBanner: false
		});

		const fileInput = getByLabelText('Terraform files or zip archives') as HTMLInputElement;
		const mockFile = new File(['module'], 'main.tf', { type: 'text/plain' });
		await fireEvent.change(fileInput, { target: { files: [mockFile] } });

		await fireEvent.click(getByText('Run scan'));

		await findByText('Scan summary');
		await waitFor(() => {
			expect(fetchMock).toHaveBeenCalledWith(`${API_BASE}/scan/upload`, expect.objectContaining({
				method: 'POST',
				headers: { Authorization: 'Bearer test-token' }
			}));
		});
		expect(mockCreateRun).toHaveBeenCalled();
		expect(mockUpdateProjectRun).toHaveBeenCalled();
	});
});
