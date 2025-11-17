import { derived, writable } from 'svelte/store';
import {
	type ArtifactEntry,
	type GeneratedAssetCreatePayload,
	type GeneratedAssetRegisterResponse,
	type GeneratedAssetSummary,
	type GeneratedAssetVersionCreatePayload,
	type GeneratedAssetUpdatePayload,
	type ProjectArtifactRecord,
	type ProjectArtifactUpdatePayload,
	type ProjectConfigCreatePayload,
	type ProjectConfigRecord,
	type ProjectConfigUpdatePayload,
	type ProjectCreatePayload,
	type ProjectDetail,
	type ProjectRunCreatePayload,
	type ProjectRunSummary,
	type ProjectSummary,
	type ProjectOverview,
	type ProjectUpdatePayload,
	addProjectLibraryAssetVersion as apiAddProjectLibraryAssetVersion,
	createProject as apiCreateProject,
	createProjectConfig as apiCreateProjectConfig,
	createProjectRun as apiCreateProjectRun,
	deleteProject as apiDeleteProject,
	deleteProjectConfig as apiDeleteProjectConfig,
	deleteProjectLibraryAsset as apiDeleteProjectLibraryAsset,
	deleteProjectLibraryAssetVersion as apiDeleteProjectLibraryAssetVersion,
	deleteRunArtifact as apiDeleteRunArtifact,
	getProjectConfig as apiGetProjectConfig,
	getProjectLibraryAsset as apiGetProjectLibraryAsset,
	getProjectOverview as apiGetProjectOverview,
	listProjectArtifacts as apiListProjectArtifacts,
	listProjectConfigs as apiListProjectConfigs,
	listProjectLibrary as apiListProjectLibrary,
	listProjectRuns as apiListProjectRuns,
	listProjects as apiListProjects,
	listRunArtifacts as apiListRunArtifacts,
	registerProjectLibraryAsset as apiRegisterProjectLibraryAsset,
	syncProjectRunArtifacts as apiSyncProjectRunArtifacts,
	updateProject as apiUpdateProject,
	updateProjectArtifact as apiUpdateProjectArtifact,
	updateProjectConfig as apiUpdateProjectConfig,
	updateProjectLibraryAsset as apiUpdateProjectLibraryAsset,
	uploadRunArtifact as apiUploadRunArtifact
} from '$lib/api/client';

type FetchFn = typeof fetch;

interface ArtifactCacheEntry {
	path: string;
	runId: string;
	entries: ArtifactEntry[];
	fetchedAt: string;
}

interface ProjectRunCacheEntry {
	items: ProjectRunSummary[];
	nextCursor: string | null;
	totalCount: number;
	fetchedAt: string;
}

interface ProjectLibraryCacheEntry {
	assets: GeneratedAssetSummary[];
	includeVersions: boolean;
	nextCursor: string | null;
	totalCount: number;
	fetchedAt: string;
}

interface ProjectOverviewCacheEntry {
	data: ProjectOverview;
	fetchedAt: string;
}

interface ProjectConfigCacheEntry {
	items: ProjectConfigRecord[];
	includePayload: boolean;
	fetchedAt: string;
}

interface ProjectArtifactIndexEntry {
	projectId: string;
	runId: string | null;
	items: ProjectArtifactRecord[];
	nextCursor: string | null;
	totalCount: number;
	fetchedAt: string;
}

interface ProjectState {
	projects: ProjectSummary[];
	activeProjectId: string | null;
	runs: Record<string, ProjectRunCacheEntry>;
	artifacts: Record<string, ArtifactCacheEntry>;
	library: Record<string, ProjectLibraryCacheEntry>;
	overview: Record<string, ProjectOverviewCacheEntry>;
	configs: Record<string, ProjectConfigCacheEntry>;
	artifactIndex: Record<string, ProjectArtifactIndexEntry>;
	loading: boolean;
	error: string | null;
}

const initialState: ProjectState = {
	projects: [],
	activeProjectId: null,
	runs: {},
	artifacts: {},
	library: {},
	overview: {},
	configs: {},
	artifactIndex: {},
	loading: false,
	error: null
};

const makeArtifactKey = (runId: string, path = ''): string => {
	const normalised = !path || path === '.' ? '.' : path.replace(/^(\.\/|\/)+/, '').trim() || '.';
	return `${runId}::${normalised}`;
};

const makeProjectArtifactIndexKey = (projectId: string, runId: string | null = null): string =>
	`${projectId}::${runId ?? 'all'}`;

const extractDirectory = (path: string): string => {
	const cleaned = path.replace(/\\/g, '/').replace(/^(\.\/|\/)+/, '');
	if (!cleaned || cleaned === '.') {
		return '.';
	}
	const segments = cleaned.split('/').filter(Boolean);
	if (segments.length <= 1) {
		return '.';
	}
	return segments.slice(0, -1).join('/') || '.';
};

const upsertLibraryAsset = (assets: GeneratedAssetSummary[], asset: GeneratedAssetSummary): GeneratedAssetSummary[] => {
	const others = assets.filter((item) => item.id !== asset.id);
	return [asset, ...others];
};

const normaliseError = (error: unknown): string =>
	error instanceof Error ? error.message : typeof error === 'string' ? error : 'Unknown error';

function createProjectStore() {
	const store = writable<ProjectState>({ ...initialState });
	let currentState = { ...initialState };
	store.subscribe((value) => {
		currentState = value;
	});
	const { subscribe, update, set } = store;

	return {
		subscribe,
		reset() {
			set({ ...initialState });
		},
		setActiveProject(projectId: string | null) {
			update((state) => {
				if (!projectId || !state.projects.some((project) => project.id === projectId)) {
					return { ...state, activeProjectId: null };
				}
				return { ...state, activeProjectId: projectId };
			});
		},
		upsertProject(project: ProjectSummary | ProjectDetail) {
			update((state) => {
				const exists = state.projects.some((item) => item.id === project.id);
				const projects = exists
					? state.projects.map((item) => (item.id === project.id ? { ...item, ...project } : item))
					: [...state.projects, project];
				return {
					...state,
					projects,
					activeProjectId: state.activeProjectId ?? project.id
				};
			});
		},
		removeProject(projectId: string) {
			update((state) => {
				const runIds = new Set((state.runs[projectId]?.items ?? []).map((run) => run.id));
				const projects = state.projects.filter((item) => item.id !== projectId);
				const runs = Object.fromEntries(
					Object.entries(state.runs).filter(([key]) => key !== projectId)
				);
				const artifacts = Object.fromEntries(
					Object.entries(state.artifacts).filter(([, entry]) => !runIds.has(entry.runId))
				);
				const library = Object.fromEntries(
					Object.entries(state.library).filter(([key]) => key !== projectId)
				);
				const overview = Object.fromEntries(
					Object.entries(state.overview).filter(([key]) => key !== projectId)
				);
				const configs = Object.fromEntries(Object.entries(state.configs).filter(([key]) => key !== projectId));
				const artifactIndex = Object.fromEntries(
					Object.entries(state.artifactIndex).filter(([, entry]) => entry.projectId !== projectId)
				);
				const activeProjectId =
					state.activeProjectId === projectId ? (projects[0]?.id ?? null) : state.activeProjectId;
				return { ...state, projects, runs, artifacts, library, overview, configs, artifactIndex, activeProjectId };
			});
		},
		setRuns(projectId: string, runs: ProjectRunSummary[]) {
			update((state) => ({
				...state,
				runs: {
					...state.runs,
					[projectId]: {
						items: runs,
						nextCursor: null,
						totalCount: runs.length,
						fetchedAt: new Date().toISOString()
					}
				}
			}));
		},
		upsertRun(projectId: string, run: ProjectRunSummary) {
			update((state) => {
				const cache = state.runs[projectId];
				const items = cache?.items ?? [];
				const exists = items.some((item) => item.id === run.id);
				const nextItems = exists
					? items.map((item) => (item.id === run.id ? { ...item, ...run } : item))
					: [run, ...items];
				return {
					...state,
					runs: {
						...state.runs,
						[projectId]: {
							items: nextItems,
							nextCursor: cache?.nextCursor ?? null,
							totalCount: exists ? cache?.totalCount ?? nextItems.length : (cache?.totalCount ?? 0) + 1,
							fetchedAt: new Date().toISOString()
						}
					}
				};
			});
		},
		setArtifactCache(runId: string, path: string, entries: ArtifactEntry[]) {
			update((state) => ({
				...state,
				artifacts: {
					...state.artifacts,
					[makeArtifactKey(runId, path)]: {
						runId,
						path: path || '.',
						entries,
						fetchedAt: new Date().toISOString()
					}
				}
			}));
		},
		clearArtifacts(runId?: string) {
			if (!runId) {
				update((state) => ({ ...state, artifacts: {} }));
				return;
			}
			update((state) => {
				const next = Object.fromEntries(
					Object.entries(state.artifacts).filter(([, value]) => value.runId !== runId)
				);
				return { ...state, artifacts: next };
			});
		},
		getCachedArtifacts(runId: string, path: string = '.') {
			const key = makeArtifactKey(runId, path);
			return currentState.artifacts[key] ?? null;
		},
	getCachedLibrary(projectId: string) {
		return currentState.library[projectId] ?? null;
	},
	getCachedRuns(projectId: string) {
		return currentState.runs[projectId] ?? null;
	},
	getCachedOverview(projectId: string) {
		return currentState.overview[projectId] ?? null;
	},
	getCachedConfigs(projectId: string) {
		return currentState.configs[projectId] ?? null;
	},
	getCachedArtifactIndex(projectId: string, runId: string | null = null) {
		return currentState.artifactIndex[makeProjectArtifactIndexKey(projectId, runId)] ?? null;
	},
		clearLibrary(projectId?: string) {
			if (!projectId) {
				update((state) => ({ ...state, library: {} }));
				return;
			}
			update((state) => {
				const next = Object.fromEntries(Object.entries(state.library).filter(([key]) => key !== projectId));
				return { ...state, library: next };
			});
		},
		async loadProjects(fetchFn: FetchFn, token: string) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const projects = await apiListProjects(fetchFn, token);
				update((state) => {
					const active =
						state.activeProjectId && projects.some((project) => project.id === state.activeProjectId)
							? state.activeProjectId
							: projects[0]?.id ?? null;
					return {
						...state,
						projects,
						activeProjectId: active,
						loading: false
					};
				});
				return projects;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
	async loadLibrary(fetchFn: FetchFn, token: string, projectId: string, includeVersions = false) {
		update((state) => ({ ...state, loading: true, error: null }));
		try {
			const response = await apiListProjectLibrary(fetchFn, token, projectId, { includeVersions });
			update((state) => ({
					...state,
					library: {
						...state.library,
						[projectId]: {
							assets: response.items,
							includeVersions,
							nextCursor: response.nextCursor ?? null,
							totalCount: response.totalCount,
							fetchedAt: new Date().toISOString()
						}
					},
					loading: false
				}));
				return response.items;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		clearOverview(projectId?: string) {
			if (!projectId) {
				update((state) => ({ ...state, overview: {} }));
				return;
			}
			update((state) => {
				const next = Object.fromEntries(
					Object.entries(state.overview).filter(([key]) => key !== projectId)
				);
				return { ...state, overview: next };
			});
		},
		async loadOverview(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			options: { recentAssets?: number; includeMetadata?: boolean } = {}
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const overview = await apiGetProjectOverview(fetchFn, token, projectId, options);
				update((state) => ({
					...state,
					overview: {
						...state.overview,
						[projectId]: {
							data: overview,
							fetchedAt: new Date().toISOString()
						}
					},
					projects: state.projects.map((project) =>
						project.id === projectId
							? {
									...project,
									...overview.project,
									run_count: overview.run_count,
									library_asset_count: overview.library_asset_count,
									latest_run: overview.latest_run ?? project.latest_run,
									last_activity_at: overview.last_activity_at ?? project.last_activity_at
								}
							: project
					),
					loading: false
				}));
				return overview;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async loadConfigs(fetchFn: FetchFn, token: string, projectId: string, includePayload = true) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const configs = await apiListProjectConfigs(fetchFn, token, projectId, { includePayload });
				update((state) => ({
					...state,
					configs: {
						...state.configs,
						[projectId]: {
							items: configs,
							includePayload,
							fetchedAt: new Date().toISOString()
						}
					},
					loading: false
				}));
				return configs;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async createProjectConfig(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			payload: ProjectConfigCreatePayload
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const created = await apiCreateProjectConfig(fetchFn, token, projectId, payload);
				update((state) => {
					const cache = state.configs[projectId];
					const items = cache?.items ?? [];
					return {
						...state,
						configs: {
							...state.configs,
							[projectId]: {
								items: [created, ...items.filter((item) => item.id !== created.id)],
								includePayload: cache?.includePayload ?? true,
								fetchedAt: new Date().toISOString()
							}
						},
						loading: false
					};
				});
				return created;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async updateProjectConfig(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			configId: string,
			payload: ProjectConfigUpdatePayload
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				let record: ProjectConfigRecord | null = null;
				if (!currentState.configs[projectId]?.includePayload && payload.payload === undefined) {
					record = await apiGetProjectConfig(fetchFn, token, projectId, configId, { includePayload: true });
				}
				const updated =
					record ??
					(await apiUpdateProjectConfig(fetchFn, token, projectId, configId, payload));
				update((state) => {
					const cache = state.configs[projectId];
					const items = cache?.items ?? [];
					const nextItems = items.some((item) => item.id === updated.id)
						? items.map((item) => (item.id === updated.id ? updated : item))
						: [updated, ...items];
					return {
						...state,
						configs: {
							...state.configs,
							[projectId]: {
								items: nextItems,
								includePayload: cache?.includePayload ?? true,
								fetchedAt: new Date().toISOString()
							}
						},
						loading: false
					};
				});
				return updated;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async deleteProjectConfig(fetchFn: FetchFn, token: string, projectId: string, configId: string) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				await apiDeleteProjectConfig(fetchFn, token, projectId, configId);
				update((state) => {
					const cache = state.configs[projectId];
					if (!cache) {
						return { ...state, loading: false };
					}
					const items = cache.items.filter((item) => item.id !== configId);
					const nextConfigs = { ...state.configs };
					if (items.length) {
						nextConfigs[projectId] = {
							items,
							includePayload: cache.includePayload,
							fetchedAt: new Date().toISOString()
						};
					} else {
						delete nextConfigs[projectId];
					}
					return {
						...state,
						configs: nextConfigs,
						loading: false
					};
				});
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async registerLibraryAsset(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			payload: GeneratedAssetCreatePayload
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const result: GeneratedAssetRegisterResponse = await apiRegisterProjectLibraryAsset(
					fetchFn,
					token,
					projectId,
					payload
				);
				const updated = result.asset;
				update((state) => {
					const cache = state.library[projectId];
					const assets = upsertLibraryAsset(cache?.assets ?? [], updated);
					const existed = cache?.assets?.some((item) => item.id === updated.id) ?? false;
					return {
						...state,
						library: {
							...state.library,
							[projectId]: {
								assets,
								includeVersions: cache?.includeVersions ?? Boolean(updated.versions?.length),
								nextCursor: cache?.nextCursor ?? null,
								totalCount: cache ? (existed ? cache.totalCount : cache.totalCount + 1) : assets.length,
								fetchedAt: new Date().toISOString()
							}
						},
						loading: false
					};
				});
				return result;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async addLibraryAssetVersion(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			assetId: string,
			payload: GeneratedAssetVersionCreatePayload
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const result: GeneratedAssetRegisterResponse = await apiAddProjectLibraryAssetVersion(
					fetchFn,
					token,
					projectId,
					assetId,
					payload
				);
				const updated = result.asset;
				update((state) => {
					const cache = state.library[projectId];
					const assets = upsertLibraryAsset(cache?.assets ?? [], updated);
					return {
						...state,
						library: {
							...state.library,
							[projectId]: {
								assets,
								includeVersions: true,
								nextCursor: cache?.nextCursor ?? null,
								totalCount: cache?.totalCount ?? assets.length,
								fetchedAt: new Date().toISOString()
							}
						},
						loading: false
					};
				});
				return result;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async deleteLibraryAssetVersion(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			assetId: string,
			versionId: string,
			removeFiles = true
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				await apiDeleteProjectLibraryAssetVersion(fetchFn, token, projectId, assetId, versionId, removeFiles);
				const refreshed = await apiGetProjectLibraryAsset(fetchFn, token, projectId, assetId, true);
				update((state) => {
					const cache = state.library[projectId];
					const assets = upsertLibraryAsset(cache?.assets ?? [], refreshed);
					return {
						...state,
						library: {
							...state.library,
							[projectId]: {
								assets,
								includeVersions: true,
								nextCursor: cache?.nextCursor ?? null,
								totalCount: cache?.totalCount ?? assets.length,
								fetchedAt: new Date().toISOString()
							}
						},
						loading: false
					};
				});
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async deleteLibraryAsset(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			assetId: string,
			removeFiles = false
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				await apiDeleteProjectLibraryAsset(fetchFn, token, projectId, assetId, removeFiles);
				update((state) => {
					const cache = state.library[projectId];
					if (!cache) {
						return { ...state, loading: false };
					}
					const existed = cache.assets.some((item) => item.id === assetId);
					const assets = cache.assets.filter((item) => item.id !== assetId);
					const nextLibrary = {
						...state.library,
						[projectId]: {
							assets,
							includeVersions: cache.includeVersions,
							nextCursor: cache.nextCursor,
							totalCount: existed ? Math.max(0, cache.totalCount - 1) : cache.totalCount,
							fetchedAt: new Date().toISOString()
						}
					};
					return {
						...state,
						library: nextLibrary,
						loading: false
					};
				});
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async updateLibraryAsset(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			assetId: string,
			payload: GeneratedAssetUpdatePayload
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const updated = await apiUpdateProjectLibraryAsset(fetchFn, token, projectId, assetId, payload);
				update((state) => {
					const cache = state.library[projectId];
					const assets = upsertLibraryAsset(cache?.assets ?? [], updated);
					return {
						...state,
						library: {
							...state.library,
							[projectId]: {
								assets,
								includeVersions: cache?.includeVersions ?? true,
								nextCursor: cache?.nextCursor ?? null,
								totalCount: cache?.totalCount ?? assets.length,
								fetchedAt: new Date().toISOString()
							}
						},
						loading: false
					};
				});
				return updated;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
	async createProject(fetchFn: FetchFn, token: string, payload: ProjectCreatePayload) {
		update((state) => ({ ...state, loading: true, error: null }));
		try {
			const created = await apiCreateProject(fetchFn, token, payload);
			update((state) => ({
				...state,
					projects: [...state.projects, created],
					activeProjectId: created.id,
					loading: false
				}));
				return created;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
		}
	},
	async loadMoreLibrary(fetchFn: FetchFn, token: string, projectId: string, limit = 100) {
		const cache = currentState.library[projectId];
		if (!cache?.nextCursor) {
			return [] as GeneratedAssetSummary[];
		}
		update((state) => ({ ...state, error: null }));
		try {
			const response = await apiListProjectLibrary(fetchFn, token, projectId, {
				includeVersions: cache.includeVersions,
				cursor: cache.nextCursor ?? undefined,
				limit
			});
			update((state) => {
				const existingCache = state.library[projectId];
				const existingAssets = existingCache?.assets ?? [];
				const existingIds = new Set(existingAssets.map((item) => item.id));
				const merged = [...existingAssets, ...response.items.filter((item) => !existingIds.has(item.id))];
				return {
					...state,
					library: {
						...state.library,
						[projectId]: {
							assets: merged,
							includeVersions: cache.includeVersions,
							nextCursor: response.nextCursor ?? null,
							totalCount: response.totalCount,
							fetchedAt: new Date().toISOString()
						}
					}
				};
			});
			return response.items;
		} catch (error) {
			const message = normaliseError(error);
			update((state) => ({ ...state, error: message }));
			throw error;
		}
	},
	async loadProjectArtifactIndex(
		fetchFn: FetchFn,
		token: string,
		projectId: string,
		options: { runId?: string | null; limit?: number } = {}
	) {
		update((state) => ({ ...state, loading: true, error: null }));
		try {
			const runFilter = options.runId ?? null;
			const response = await apiListProjectArtifacts(fetchFn, token, projectId, {
				runId: runFilter ?? undefined,
				limit: options.limit
			});
			const key = makeProjectArtifactIndexKey(projectId, runFilter);
			update((state) => ({
				...state,
				artifactIndex: {
					...state.artifactIndex,
					[key]: {
						projectId,
						runId: runFilter,
						items: response.items,
						nextCursor: response.nextCursor ?? null,
						totalCount: response.totalCount,
						fetchedAt: new Date().toISOString()
					}
				},
				loading: false
			}));
			return response.items;
		} catch (error) {
			const message = normaliseError(error);
			update((state) => ({ ...state, loading: false, error: message }));
			throw error;
		}
	},
	async loadMoreProjectArtifactIndex(
		fetchFn: FetchFn,
		token: string,
		projectId: string,
		options: { runId?: string | null; limit?: number } = {}
	) {
		const runFilter = options.runId ?? null;
		const key = makeProjectArtifactIndexKey(projectId, runFilter);
		const cache = currentState.artifactIndex[key];
		if (!cache?.nextCursor) {
			return [] as ProjectArtifactRecord[];
		}
		update((state) => ({ ...state, error: null }));
		try {
			const response = await apiListProjectArtifacts(fetchFn, token, projectId, {
				runId: runFilter ?? undefined,
				limit: options.limit,
				cursor: cache.nextCursor ?? undefined
			});
			update((state) => {
				const existing = state.artifactIndex[key];
				const existingItems = existing?.items ?? [];
				const existingIds = new Set(existingItems.map((item) => item.id));
				const merged = [...existingItems, ...response.items.filter((item) => !existingIds.has(item.id))];
				return {
					...state,
					artifactIndex: {
						...state.artifactIndex,
						[key]: {
							projectId,
							runId: runFilter,
							items: merged,
							nextCursor: response.nextCursor ?? null,
							totalCount: response.totalCount,
							fetchedAt: new Date().toISOString()
						}
					}
				};
			});
			return response.items;
		} catch (error) {
			const message = normaliseError(error);
			update((state) => ({ ...state, error: message }));
			throw error;
		}
	},
	async updateProjectArtifactMetadata(
		fetchFn: FetchFn,
		token: string,
		projectId: string,
		artifactId: string,
		payload: ProjectArtifactUpdatePayload
	) {
		update((state) => ({ ...state, loading: true, error: null }));
		try {
			const updated = await apiUpdateProjectArtifact(fetchFn, token, projectId, artifactId, payload);
			update((state) => {
				const nextIndex = { ...state.artifactIndex };
				for (const [key, entry] of Object.entries(nextIndex)) {
					if (entry.projectId !== projectId) {
						continue;
					}
					if (entry.runId && entry.runId !== (updated.run_id ?? null)) {
						continue;
					}
					const idx = entry.items.findIndex((item) => item.id === updated.id);
					if (idx >= 0) {
						const items = [...entry.items];
						items[idx] = updated;
						nextIndex[key] = { ...entry, items, fetchedAt: new Date().toISOString() };
					}
				}
				return {
					...state,
					artifactIndex: nextIndex,
					loading: false
				};
			});
			return updated;
		} catch (error) {
			const message = normaliseError(error);
			update((state) => ({ ...state, loading: false, error: message }));
			throw error;
		}
	},
	async syncRunArtifacts(
		fetchFn: FetchFn,
		token: string,
		projectId: string,
		runId: string,
		options: { pruneMissing?: boolean } = {}
	) {
		update((state) => ({ ...state, loading: true, error: null }));
		try {
			const result = await apiSyncProjectRunArtifacts(fetchFn, token, projectId, runId, options);
			update((state) => ({ ...state, loading: false }));
			return result;
		} catch (error) {
			const message = normaliseError(error);
			update((state) => ({ ...state, loading: false, error: message }));
			throw error;
		}
	},
	async updateProject(fetchFn: FetchFn, token: string, projectId: string, payload: ProjectUpdatePayload) {
		update((state) => ({ ...state, loading: true, error: null }));
		try {
			const updatedProject = await apiUpdateProject(fetchFn, token, projectId, payload);
			update((state) => {
				const projects = state.projects.map((project) =>
					project.id === projectId ? { ...project, ...updatedProject } : project
				);
				return {
					...state,
					projects,
					loading: false
				};
			});
			return updatedProject;
		} catch (error) {
			const message = normaliseError(error);
			update((state) => ({ ...state, loading: false, error: message }));
			throw error;
		}
	},
	async deleteProject(fetchFn: FetchFn, token: string, projectId: string, removeFiles = false) {
		update((state) => ({ ...state, loading: true, error: null }));
		try {
			await apiDeleteProject(fetchFn, token, projectId, removeFiles);
			update((state) => {
				const projectRunIds = new Set((state.runs[projectId]?.items ?? []).map((run) => run.id));
				const updatedProjects = state.projects.filter((project) => project.id !== projectId);
				const runs = Object.fromEntries(
					Object.entries(state.runs).filter(([key]) => key !== projectId)
				);
				const artifacts = Object.fromEntries(
					Object.entries(state.artifacts).filter(([, value]) => !projectRunIds.has(value.runId))
				);
				const library = Object.fromEntries(
					Object.entries(state.library).filter(([key]) => key !== projectId)
				);
				const overview = Object.fromEntries(
					Object.entries(state.overview).filter(([key]) => key !== projectId)
				);
				const configs = Object.fromEntries(Object.entries(state.configs).filter(([key]) => key !== projectId));
				const artifactIndex = Object.fromEntries(
					Object.entries(state.artifactIndex).filter(([, entry]) => entry.projectId !== projectId)
				);
				const activeProjectId =
					state.activeProjectId === projectId ? (updatedProjects[0]?.id ?? null) : state.activeProjectId;
				return {
					...state,
					projects: updatedProjects,
					runs,
					artifacts,
					library,
					overview,
					configs,
					artifactIndex,
					activeProjectId,
					loading: false
				};
			});
		} catch (error) {
			const message = normaliseError(error);
			update((state) => ({ ...state, loading: false, error: message }));
			throw error;
		}
	},
	async refreshRuns(fetchFn: FetchFn, token: string, projectId: string, limit = 50) {
		update((state) => ({ ...state, loading: true, error: null }));
		try {
			const response = await apiListProjectRuns(fetchFn, token, projectId, { limit });
			update((state) => ({
				...state,
				runs: {
					...state.runs,
					[projectId]: {
						items: response.items,
						nextCursor: response.nextCursor ?? null,
						totalCount: response.totalCount,
						fetchedAt: new Date().toISOString()
					}
				},
				loading: false
			}));
			return response.items;
		} catch (error) {
			const message = normaliseError(error);
			update((state) => ({ ...state, loading: false, error: message }));
			throw error;
		}
	},
		async loadMoreRuns(fetchFn: FetchFn, token: string, projectId: string, limit = 50) {
			const cache = currentState.runs[projectId];
			if (!cache?.nextCursor) {
				return [] as ProjectRunSummary[];
			}
			update((state) => ({ ...state, error: null }));
			try {
				const response = await apiListProjectRuns(fetchFn, token, projectId, {
					limit,
					cursor: cache.nextCursor ?? undefined
				});
				update((state) => {
					const existingCache = state.runs[projectId];
					const existingItems = existingCache?.items ?? [];
					const existingIds = new Set(existingItems.map((item) => item.id));
					const merged = [...existingItems, ...response.items.filter((item) => !existingIds.has(item.id))];
					return {
						...state,
						runs: {
							...state.runs,
							[projectId]: {
								items: merged,
								nextCursor: response.nextCursor ?? null,
								totalCount: response.totalCount,
								fetchedAt: new Date().toISOString()
							}
						}
					};
				});
				return response.items;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, error: message }));
				throw error;
			}
		},
		async createRun(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			payload: ProjectRunCreatePayload
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const run = await apiCreateProjectRun(fetchFn, token, projectId, payload);
				update((state) => {
					const cache = state.runs[projectId];
					const items = cache?.items ?? [];
					const exists = items.some((item) => item.id === run.id);
					return {
						...state,
						runs: {
							...state.runs,
							[projectId]: {
								items: exists ? items : [run, ...items],
								nextCursor: cache?.nextCursor ?? null,
								totalCount: exists ? cache?.totalCount ?? items.length : (cache?.totalCount ?? 0) + 1,
								fetchedAt: new Date().toISOString()
							}
						},
						loading: false
					};
				});
				return run;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async loadArtifacts(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			runId: string,
			path: string = '.'
		) {
			const targetPath = !path || path === '.' ? '.' : path;
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const entries = await apiListRunArtifacts(
					fetchFn,
					token,
					projectId,
					runId,
					targetPath === '.' ? undefined : targetPath
				);
				update((state) => ({
					...state,
					artifacts: {
						...state.artifacts,
						[makeArtifactKey(runId, targetPath)]: {
							runId,
							path: targetPath,
							entries,
							fetchedAt: new Date().toISOString()
						}
					},
					loading: false
				}));
				return entries;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async uploadArtifact(
			fetchFn: FetchFn,
			token: string,
			projectId: string,
			runId: string,
			options: { path: string; file: File | Blob; filename?: string; overwrite?: boolean }
		) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const entry = await apiUploadRunArtifact(fetchFn, token, projectId, runId, options);
				update((state) => {
					const directory = extractDirectory(entry.path);
					const key = makeArtifactKey(runId, directory);
					const existing = state.artifacts[key];
					const existingEntries = existing?.entries ?? [];
					const nextEntries = (() => {
						const index = existingEntries.findIndex((item) => item.path === entry.path);
						if (index >= 0) {
							const copy = [...existingEntries];
							copy[index] = entry;
							return copy;
						}
						return [...existingEntries, entry];
					})();
					const nextArtifacts = {
						...state.artifacts,
						[key]: {
							runId,
							path: directory,
							entries: nextEntries,
							fetchedAt: new Date().toISOString()
						}
					};
					return {
						...state,
						artifacts: nextArtifacts,
						loading: false
					};
				});
				return entry;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		},
		async deleteArtifact(fetchFn: FetchFn, token: string, projectId: string, runId: string, path: string) {
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				await apiDeleteRunArtifact(fetchFn, token, projectId, runId, path);
				update((state) => {
					const directory = extractDirectory(path);
					const key = makeArtifactKey(runId, directory);
					const existing = state.artifacts[key];
					const entries = existing?.entries ?? [];
					const nextEntries = entries.filter((item) => item.path !== path);
					const nextArtifacts = { ...state.artifacts };
					if (nextEntries.length) {
						nextArtifacts[key] = {
							runId,
							path: directory,
							entries: nextEntries,
							fetchedAt: new Date().toISOString()
						};
					} else {
						delete nextArtifacts[key];
					}
					return {
						...state,
						artifacts: nextArtifacts,
						loading: false
					};
				});
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
				throw error;
			}
		}
	};
}

export const projectState = createProjectStore();

export const activeProject = derived(projectState, ($state) =>
	$state.projects.find((project) => project.id === $state.activeProjectId) ?? null
);

export const activeProjectRuns = derived([projectState, activeProject], ([$state, $active]) =>
	$active ? $state.runs[$active.id]?.items ?? [] : []
);

export const activeProjectLibrary = derived([projectState, activeProject], ([$state, $active]) =>
	$active ? $state.library[$active.id]?.assets ?? [] : []
);

export const activeProjectOverview = derived([projectState, activeProject], ([$state, $active]) =>
	$active ? $state.overview[$active.id]?.data ?? null : null
);
