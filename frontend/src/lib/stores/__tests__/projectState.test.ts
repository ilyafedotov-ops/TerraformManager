import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const hoistedMocks = vi.hoisted(() => ({
    listProjectLibrary: vi.fn(),
    updateProjectLibraryAsset: vi.fn(),
    registerIdentifierResolver: vi.fn(),
}));

vi.mock('$lib/api/client', () => {
    return {
        registerProjectIdentifierResolver: hoistedMocks.registerIdentifierResolver,
        listProjectLibrary: hoistedMocks.listProjectLibrary,
        updateProjectLibraryAsset: hoistedMocks.updateProjectLibraryAsset,
        listProjects: vi.fn().mockResolvedValue([]),
        updateProject: vi.fn(),
        createProject: vi.fn(),
        deleteProject: vi.fn(),
        getProjectOverview: vi.fn(),
        listProjectRuns: vi.fn(),
        listRunArtifacts: vi.fn(),
        syncProjectRunArtifacts: vi.fn(),
        uploadRunArtifact: vi.fn(),
        deleteRunArtifact: vi.fn(),
        listProjectArtifacts: vi.fn(),
        updateProjectArtifact: vi.fn(),
        listProjectConfigs: vi.fn(),
        createProjectConfig: vi.fn(),
        updateProjectConfig: vi.fn(),
        deleteProjectConfig: vi.fn(),
        getProjectConfig: vi.fn(),
        registerProjectLibraryAsset: vi.fn(),
        addProjectLibraryAssetVersion: vi.fn(),
        deleteProjectLibraryAsset: vi.fn(),
        deleteProjectLibraryAssetVersion: vi.fn(),
        getProjectLibraryAsset: vi.fn(),
        createProjectRun: vi.fn(),
        listProjectLibraryVersionFiles: vi.fn(),
    };
});

const listProjectLibraryMock = hoistedMocks.listProjectLibrary;
const updateProjectLibraryAssetMock = hoistedMocks.updateProjectLibraryAsset;
const registerIdentifierResolverMock = hoistedMocks.registerIdentifierResolver;

// Import after mocking
import { projectState } from '$lib/stores/project';

const fetchStub = vi.fn();

const baseAsset = {
    id: 'asset-1',
    project_id: 'project-1',
    name: 'Scan Report',
    description: 'Baseline findings',
    asset_type: 'scan_report',
    tags: ['scan'],
    metadata: { source: 'api.scan' },
    latest_version_id: 'version-1',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    versions: [
        {
            id: 'version-1',
            asset_id: 'asset-1',
            project_id: 'project-1',
            storage_path: 'reports/asset-1.json',
            display_path: 'reports/report.json',
            media_type: 'application/json',
            notes: null,
            created_at: '2024-01-01T00:00:00Z',
            metadata: { report_id: 'r-1' },
        },
    ],
};

describe('projectState store', () => {
    beforeEach(() => {
        projectState.reset();
        listProjectLibraryMock.mockReset();
        updateProjectLibraryAssetMock.mockReset();
    });

    it('registers a project identifier resolver that prefers slugs', () => {
        expect(registerIdentifierResolverMock).toHaveBeenCalledTimes(1);
        const resolver = registerIdentifierResolverMock.mock.calls[0][0] as () => string | null;
        projectState.upsertProject({
            id: 'project-1',
            name: 'Demo',
            slug: 'demo-project',
            root_path: '/tmp/demo',
        } as any);
        projectState.setActiveProject('project-1');
        expect(resolver()).toBe('demo-project');
    });

    it('caches library responses with versions when loading assets', async () => {
        listProjectLibraryMock.mockResolvedValue({
            items: [baseAsset],
            nextCursor: null,
            totalCount: 1,
        });

        await projectState.loadLibrary(fetchStub, 'token', 'project-1', true);

        const state = get(projectState);
        expect(listProjectLibraryMock).toHaveBeenCalledWith(fetchStub, 'token', 'project-1', {
            includeVersions: true,
        });
        expect(state.library['project-1'].assets).toHaveLength(1);
        expect(state.library['project-1'].assets[0].versions?.[0].display_path).toBe('reports/report.json');
        expect(state.library['project-1'].includeVersions).toBe(true);
    });

    it('merges updated asset metadata into the cache', async () => {
        listProjectLibraryMock.mockResolvedValue({
            items: [baseAsset],
            nextCursor: null,
            totalCount: 1,
        });
        await projectState.loadLibrary(fetchStub, 'token', 'project-1', true);

        updateProjectLibraryAssetMock.mockResolvedValue({
            ...baseAsset,
            name: 'Updated Scan Report',
            tags: ['scan', 'weekly'],
        });

        await projectState.updateLibraryAsset(fetchStub, 'token', 'project-1', 'asset-1', {
            name: 'Updated Scan Report',
            tags: ['scan', 'weekly'],
        });

        const state = get(projectState);
        const updated = state.library['project-1'].assets.find((asset) => asset.id === 'asset-1');
        expect(updateProjectLibraryAssetMock).toHaveBeenCalledWith(
            fetchStub,
            'token',
            'project-1',
            'asset-1',
            {
                name: 'Updated Scan Report',
                tags: ['scan', 'weekly'],
            },
        );
        expect(updated?.name).toBe('Updated Scan Report');
        expect(updated?.tags).toEqual(['scan', 'weekly']);
    });
});
