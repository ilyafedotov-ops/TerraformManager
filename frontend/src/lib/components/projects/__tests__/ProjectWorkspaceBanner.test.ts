import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, beforeEach, vi } from 'vitest';
import type { Writable } from 'svelte/store';
import type { ProjectSummary } from '$lib/api/client';

const { setActiveProjectMock, gotoMock } = vi.hoisted(() => ({
	setActiveProjectMock: vi.fn(),
	gotoMock: vi.fn()
}));

vi.mock('$lib/stores/project', async () => {
	const { writable } = await import('svelte/store');
	const projectStore = writable({ projects: [] as ProjectSummary[], activeProjectId: null as string | null });
	return {
		projectState: {
			subscribe: projectStore.subscribe,
			set: projectStore.set,
			update: projectStore.update,
			setActiveProject: setActiveProjectMock
		},
		activeProject: writable<ProjectSummary | null>(null)
	};
});

vi.mock('$app/navigation', () => ({
	goto: gotoMock
}));

import ProjectWorkspaceBanner from '../ProjectWorkspaceBanner.svelte';
import { activeProject, projectState } from '$lib/stores/project';

type ProjectStoreState = { projects: ProjectSummary[]; activeProjectId: string | null };

const projectStore = projectState as unknown as Writable<ProjectStoreState>;
const activeStore = activeProject as Writable<ProjectSummary | null>;

const setProjects = (projects: ProjectSummary[], activeProjectId: string | null) => {
	projectStore.set({ projects, activeProjectId });
	const active = projects.find((project) => project.id === activeProjectId) ?? null;
	activeStore.set(active);
};

describe('ProjectWorkspaceBanner', () => {
	beforeEach(() => {
		setActiveProjectMock.mockReset();
		gotoMock.mockReset();
		setProjects([], null);
	});

	it('renders the active project selector when projects exist', () => {
		setProjects(
			[
				{ id: 'proj-1', name: 'Main', slug: 'main', root_path: '/workspace/main' },
				{ id: 'proj-2', name: 'Backup', slug: 'backup', root_path: '/workspace/backup' }
			],
			'proj-1'
		);

		const { getByLabelText } = render(ProjectWorkspaceBanner, {
			context: 'Testing context'
		});

		const select = getByLabelText('Active project') as HTMLSelectElement;
		expect(select.value).toBe('proj-1');

		fireEvent.change(select, { target: { value: 'proj-2' } });
		expect(setActiveProjectMock).toHaveBeenCalledWith('proj-2');
	});

	it('hides the manage link when disabled and shows empty state', () => {
		const { queryByText, getByText } = render(ProjectWorkspaceBanner, {
			showManageLink: false
		});

		expect(queryByText('Manage projects')).not.toBeInTheDocument();
		expect(getByText('No projects found yet.')).toBeInTheDocument();
	});

	it('navigates to the projects page when manage link is clicked', async () => {
		setProjects([{ id: 'proj-1', name: 'Main', slug: 'main', root_path: '/workspace/main' }], 'proj-1');

		const { getByText } = render(ProjectWorkspaceBanner);
		const link = getByText('Manage projects');
		await fireEvent.click(link);

		expect(gotoMock).toHaveBeenCalledWith('/projects');
	});
});
