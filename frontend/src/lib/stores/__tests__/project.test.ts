import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
	projectState,
	activeProject,
	activeProjectRuns
} from '../project';

const mocks = vi.hoisted(() => ({
	listProjects: vi.fn(),
	createProject: vi.fn(),
	listProjectRuns: vi.fn(),
	createProjectRun: vi.fn(),
	listRunArtifacts: vi.fn(),
	updateProject: vi.fn(),
	deleteProject: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	listProjects: mocks.listProjects,
	createProject: mocks.createProject,
	listProjectRuns: mocks.listProjectRuns,
	createProjectRun: mocks.createProjectRun,
	listRunArtifacts: mocks.listRunArtifacts,
	updateProject: mocks.updateProject,
	deleteProject: mocks.deleteProject
}));

const snapshot = () => {
	let value: any;
	const unsubscribe = projectState.subscribe((state) => {
		value = state;
	});
	unsubscribe();
	return value;
};

const mockProject = {
	id: 'project-1',
	name: 'Platform Workspace',
	slug: 'platform-workspace',
	root_path: '/tmp/project-1',
	description: 'Demo project'
};

const mockRun = {
	id: 'run-1',
	project_id: mockProject.id,
	label: 'Generator run',
	kind: 'generator',
	status: 'completed',
	triggered_by: 'user@example.com',
	parameters: { generator: 'aws_s3' },
	summary: { filename: 'main.tf' }
};

describe('projectState', () => {
	beforeEach(() => {
		projectState.reset();
		Object.values(mocks).forEach((fn) => fn.mockReset());
	});

	it('loads projects and sets active project', async () => {
		mocks.listProjects.mockResolvedValueOnce([mockProject]);
		await projectState.loadProjects(vi.fn(), 'token');
		const state = snapshot();
		expect(state.projects).toHaveLength(1);
		expect(state.projects[0]).toEqual(mockProject);
		expect(get(activeProject)?.id).toBe(mockProject.id);
	});

	it('creates a project and updates store', async () => {
	mocks.createProject.mockResolvedValueOnce(mockProject);
	await projectState.createProject(vi.fn(), 'token', {
		name: mockProject.name,
		description: mockProject.description ?? undefined
	});
	const state = snapshot();
	expect(state.projects).toHaveLength(1);
	expect(state.projects[0].id).toBe(mockProject.id);
	expect(get(activeProject)?.id).toBe(mockProject.id);
});

	it('updates project metadata', async () => {
		projectState.upsertProject(mockProject);
		mocks.updateProject.mockResolvedValueOnce({ ...mockProject, description: 'Updated', metadata: { owner: 'team' } });
		await projectState.updateProject(vi.fn(), 'token', mockProject.id, {
			description: 'Updated',
			metadata: { owner: 'team' }
		});
		const state = snapshot();
		const project = state.projects.find((item: any) => item.id === mockProject.id);
		expect(project?.description).toBe('Updated');
		expect(project?.metadata).toEqual({ owner: 'team' });
	});

	it('deletes projects and clears runs', async () => {
		projectState.upsertProject(mockProject);
		projectState.setRuns(mockProject.id, [mockRun]);
		projectState.setArtifactCache(mockRun.id, '.', []);
		mocks.deleteProject.mockResolvedValueOnce(undefined);
		await projectState.deleteProject(vi.fn(), 'token', mockProject.id);
		const state = snapshot();
		expect(state.projects).toHaveLength(0);
		expect(state.runs[mockProject.id]).toBeUndefined();
		expect(state.artifacts).toEqual({});
	});

	it('creates a run and stores it under the project', async () => {
		projectState.upsertProject(mockProject);
		mocks.createProjectRun.mockResolvedValueOnce(mockRun);
		const created = await projectState.createRun(vi.fn(), 'token', mockProject.id, {
			label: mockRun.label,
			kind: mockRun.kind
		});
		expect(created).toEqual(mockRun);
		const state = snapshot();
		expect(state.runs[mockProject.id]).toBeTruthy();
		expect(state.runs[mockProject.id][0].id).toBe(mockRun.id);
		expect(get(activeProjectRuns)[0]?.id).toBe(mockRun.id);
	});

	it('refreshes runs via API call', async () => {
		projectState.upsertProject(mockProject);
		mocks.listProjectRuns.mockResolvedValueOnce([mockRun]);
		await projectState.refreshRuns(vi.fn(), 'token', mockProject.id, 10);
		const state = snapshot();
		expect(state.runs[mockProject.id]).toHaveLength(1);
		expect(state.runs[mockProject.id][0].id).toBe(mockRun.id);
	});

	it('caches and clears artifacts', () => {
		projectState.setArtifactCache(mockRun.id, 'outputs/main.tf', [
			{ name: 'main.tf', path: 'outputs/main.tf', is_dir: false, size: 42 }
		]);
		const cached = projectState.getCachedArtifacts(mockRun.id, 'outputs/main.tf');
		expect(cached).not.toBeNull();
		expect(cached?.entries[0].name).toBe('main.tf');
		projectState.clearArtifacts(mockRun.id);
		expect(projectState.getCachedArtifacts(mockRun.id, 'outputs/main.tf')).toBeNull();
	});
});
