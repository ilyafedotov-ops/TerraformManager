import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { projectState, activeProject, activeProjectRuns, activeProjectLibrary } from '../project';

const mocks = vi.hoisted(() => ({
	listProjects: vi.fn(),
	createProject: vi.fn(),
	listProjectRuns: vi.fn(),
	createProjectRun: vi.fn(),
	listRunArtifacts: vi.fn(),
	uploadRunArtifact: vi.fn(),
	deleteRunArtifact: vi.fn(),
	updateProject: vi.fn(),
	deleteProject: vi.fn(),
	listProjectLibrary: vi.fn(),
	registerProjectLibraryAsset: vi.fn(),
	addProjectLibraryAssetVersion: vi.fn(),
	deleteProjectLibraryAssetVersion: vi.fn(),
	deleteProjectLibraryAsset: vi.fn(),
	getProjectLibraryAsset: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
	listProjects: mocks.listProjects,
	createProject: mocks.createProject,
	listProjectRuns: mocks.listProjectRuns,
	createProjectRun: mocks.createProjectRun,
	listRunArtifacts: mocks.listRunArtifacts,
	uploadRunArtifact: mocks.uploadRunArtifact,
	deleteRunArtifact: mocks.deleteRunArtifact,
	updateProject: mocks.updateProject,
	deleteProject: mocks.deleteProject,
	listProjectLibrary: mocks.listProjectLibrary,
	registerProjectLibraryAsset: mocks.registerProjectLibraryAsset,
	addProjectLibraryAssetVersion: mocks.addProjectLibraryAssetVersion,
	deleteProjectLibraryAssetVersion: mocks.deleteProjectLibraryAssetVersion,
	deleteProjectLibraryAsset: mocks.deleteProjectLibraryAsset,
	getProjectLibraryAsset: mocks.getProjectLibraryAsset
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

const mockAssetVersion = {
	id: 'version-1',
	asset_id: 'asset-1',
	project_id: mockProject.id,
	storage_path: '/tmp/project-1/library/asset-1/version-1/main.tf',
	display_path: 'main.tf',
	checksum: 'abc123',
	size_bytes: 42,
	created_at: '2024-01-01T00:00:00Z'
};

const mockAsset = {
	id: 'asset-1',
	project_id: mockProject.id,
	name: 'primary-config',
	description: 'Baseline configuration',
	asset_type: 'terraform',
	tags: ['baseline'],
	metadata: { env: 'prod' },
	latest_version_id: mockAssetVersion.id,
	created_at: '2024-01-01T00:00:00Z',
	updated_at: '2024-01-02T00:00:00Z',
	versions: [mockAssetVersion]
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
		mocks.listProjectLibrary.mockResolvedValueOnce([mockAsset]);
		await projectState.loadLibrary(vi.fn(), 'token', mockProject.id, true);
		mocks.deleteProject.mockResolvedValueOnce(undefined);
		await projectState.deleteProject(vi.fn(), 'token', mockProject.id);
		const state = snapshot();
		expect(state.projects).toHaveLength(0);
		expect(state.runs[mockProject.id]).toBeUndefined();
		expect(state.artifacts).toEqual({});
		expect(state.library[mockProject.id]).toBeUndefined();
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

	it('uploads artifacts and updates cache', async () => {
		projectState.upsertProject(mockProject);
		projectState.setRuns(mockProject.id, [mockRun]);
		mocks.uploadRunArtifact.mockResolvedValueOnce({
			name: 'module.tf',
			path: 'runs/run-1/module.tf',
			is_dir: false,
			size: 128,
			modified_at: '2024-01-01T00:00:00Z'
		});

		await projectState.uploadArtifact(vi.fn(), 'token', mockProject.id, mockRun.id, {
			path: 'runs/run-1/module.tf',
			file: new Blob(['resource "aws_s3_bucket" "example" {}']),
			filename: 'module.tf',
			overwrite: true
		});

		expect(mocks.uploadRunArtifact).toHaveBeenCalledTimes(1);
		const cached = projectState.getCachedArtifacts(mockRun.id, 'runs/run-1');
		expect(cached).not.toBeNull();
		expect(cached?.entries).toHaveLength(1);
		expect(cached?.entries[0].name).toBe('module.tf');
	});

	it('deletes artifacts and prunes cache entries', async () => {
		projectState.setArtifactCache(mockRun.id, 'runs/run-1', [
			{ name: 'module.tf', path: 'runs/run-1/module.tf', is_dir: false }
		]);
		mocks.deleteRunArtifact.mockResolvedValueOnce(undefined);

		await projectState.deleteArtifact(vi.fn(), 'token', mockProject.id, mockRun.id, 'runs/run-1/module.tf');

		expect(mocks.deleteRunArtifact).toHaveBeenCalledWith(
			expect.any(Function),
			'token',
			mockProject.id,
			mockRun.id,
			'runs/run-1/module.tf'
		);
		const cached = projectState.getCachedArtifacts(mockRun.id, 'runs/run-1');
		expect(cached).toBeNull();
	});

	it('loads library assets and caches them', async () => {
		projectState.upsertProject(mockProject);
		projectState.setActiveProject(mockProject.id);
		mocks.listProjectLibrary.mockResolvedValueOnce([mockAsset]);

		const assets = await projectState.loadLibrary(vi.fn(), 'token', mockProject.id, true);

		expect(assets).toHaveLength(1);
		const state = snapshot();
		expect(state.library[mockProject.id]?.assets[0].id).toBe(mockAsset.id);
		expect(get(activeProjectLibrary)[0]?.id).toBe(mockAsset.id);
	});

	it('registers library assets and updates cache', async () => {
		projectState.upsertProject(mockProject);
		projectState.setActiveProject(mockProject.id);
		projectState.clearLibrary();
		mocks.listProjectLibrary.mockResolvedValueOnce([]);
		await projectState.loadLibrary(vi.fn(), 'token', mockProject.id);

		mocks.registerProjectLibraryAsset.mockResolvedValueOnce({
			asset: mockAsset,
			version: mockAssetVersion
		});

		const result = await projectState.registerLibraryAsset(vi.fn(), 'token', mockProject.id, {
			name: mockAsset.name,
			asset_type: mockAsset.asset_type
		});

		expect(result.asset.id).toBe(mockAsset.id);
		const state = snapshot();
		expect(state.library[mockProject.id]?.assets).toHaveLength(1);
		expect(state.library[mockProject.id]?.assets[0].id).toBe(mockAsset.id);
	});

	it('adds library versions and refreshes the asset entry', async () => {
		projectState.upsertProject(mockProject);
		projectState.setActiveProject(mockProject.id);
		projectState.clearLibrary();
		mocks.listProjectLibrary.mockResolvedValueOnce([mockAsset]);
		await projectState.loadLibrary(vi.fn(), 'token', mockProject.id, true);

		const newVersion = {
			...mockAssetVersion,
			id: 'version-2',
			display_path: 'main_v2.tf',
			storage_path: '/tmp/project-1/library/asset-1/version-2/main.tf'
		};
		const updatedAsset = {
			...mockAsset,
			latest_version_id: newVersion.id,
			versions: [newVersion, ...(mockAsset.versions ?? [])]
		};

		mocks.addProjectLibraryAssetVersion.mockResolvedValueOnce({
			asset: updatedAsset,
			version: newVersion
		});

		const result = await projectState.addLibraryAssetVersion(
			vi.fn(),
			'token',
			mockProject.id,
			mockAsset.id,
			{}
		);

		expect(result.asset.latest_version_id).toBe(newVersion.id);
		const state = snapshot();
		expect(state.library[mockProject.id]?.assets[0].latest_version_id).toBe(newVersion.id);
	});

	it('deletes library versions and refetches the asset', async () => {
		projectState.upsertProject(mockProject);
		projectState.setActiveProject(mockProject.id);
		projectState.clearLibrary();
		const secondVersion = {
			...mockAssetVersion,
			id: 'version-2',
			display_path: 'main_v2.tf'
		};
		const assetWithTwoVersions = {
			...mockAsset,
			latest_version_id: secondVersion.id,
			versions: [secondVersion, mockAssetVersion]
		};
		mocks.listProjectLibrary.mockResolvedValueOnce([assetWithTwoVersions]);
		await projectState.loadLibrary(vi.fn(), 'token', mockProject.id, true);

		mocks.deleteProjectLibraryAssetVersion.mockResolvedValueOnce(undefined);
		const refreshedAsset = { ...mockAsset, versions: [mockAssetVersion], latest_version_id: mockAssetVersion.id };
		mocks.getProjectLibraryAsset.mockResolvedValueOnce(refreshedAsset);

		await projectState.deleteLibraryAssetVersion(
			vi.fn(),
			'token',
			mockProject.id,
			mockAsset.id,
			secondVersion.id
		);

		const state = snapshot();
		expect(state.library[mockProject.id]?.assets[0].versions).toHaveLength(1);
		expect(state.library[mockProject.id]?.assets[0].latest_version_id).toBe(mockAssetVersion.id);
	});

	it('deletes library assets and removes from cache', async () => {
		projectState.upsertProject(mockProject);
		projectState.setActiveProject(mockProject.id);
		projectState.clearLibrary();
		mocks.listProjectLibrary.mockResolvedValueOnce([mockAsset]);
		await projectState.loadLibrary(vi.fn(), 'token', mockProject.id, true);

		mocks.deleteProjectLibraryAsset.mockResolvedValueOnce(undefined);

		await projectState.deleteLibraryAsset(vi.fn(), 'token', mockProject.id, mockAsset.id);

		const state = snapshot();
		expect(state.library[mockProject.id]?.assets).toHaveLength(0);
	});
});
