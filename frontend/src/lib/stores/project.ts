import { derived, writable } from 'svelte/store';
import {
	type ArtifactEntry,
	type GeneratedAssetCreatePayload,
	type GeneratedAssetRegisterResponse,
	type GeneratedAssetSummary,
	type GeneratedAssetVersionCreatePayload,
	type ProjectCreatePayload,
	type ProjectDetail,
	type ProjectRunCreatePayload,
	type ProjectRunSummary,
	type ProjectSummary,
	type ProjectUpdatePayload,
	createProject as apiCreateProject,
	createProjectRun as apiCreateProjectRun,
	listProjectRuns as apiListProjectRuns,
	listProjects as apiListProjects,
	listRunArtifacts as apiListRunArtifacts,
	uploadRunArtifact as apiUploadRunArtifact,
	deleteRunArtifact as apiDeleteRunArtifact,
	updateProject as apiUpdateProject,
	deleteProject as apiDeleteProject,
	listProjectLibrary as apiListProjectLibrary,
	registerProjectLibraryAsset as apiRegisterProjectLibraryAsset,
	addProjectLibraryAssetVersion as apiAddProjectLibraryAssetVersion,
	deleteProjectLibraryAssetVersion as apiDeleteProjectLibraryAssetVersion,
	deleteProjectLibraryAsset as apiDeleteProjectLibraryAsset,
	getProjectLibraryAsset as apiGetProjectLibraryAsset
} from '$lib/api/client';

type FetchFn = typeof fetch;

interface ArtifactCacheEntry {
	path: string;
	runId: string;
	entries: ArtifactEntry[];
	fetchedAt: string;
}

interface ProjectLibraryCacheEntry {
	assets: GeneratedAssetSummary[];
	includeVersions: boolean;
	fetchedAt: string;
}

interface ProjectState {
	projects: ProjectSummary[];
	activeProjectId: string | null;
	runs: Record<string, ProjectRunSummary[]>;
	artifacts: Record<string, ArtifactCacheEntry>;
	library: Record<string, ProjectLibraryCacheEntry>;
	loading: boolean;
	error: string | null;
}

const initialState: ProjectState = {
	projects: [],
	activeProjectId: null,
	runs: {},
	artifacts: {},
	library: {},
	loading: false,
	error: null
};

const makeArtifactKey = (runId: string, path = ''): string => {
	const normalised = !path || path === '.' ? '.' : path.replace(/^(\.\/|\/)+/, '').trim() || '.';
	return `${runId}::${normalised}`;
};

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
				const runIds = new Set((state.runs[projectId] ?? []).map((run) => run.id));
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
				const activeProjectId =
					state.activeProjectId === projectId ? (projects[0]?.id ?? null) : state.activeProjectId;
				return { ...state, projects, runs, artifacts, library, activeProjectId };
			});
		},
		setRuns(projectId: string, runs: ProjectRunSummary[]) {
			update((state) => ({
				...state,
				runs: { ...state.runs, [projectId]: runs }
			}));
		},
		upsertRun(projectId: string, run: ProjectRunSummary) {
			update((state) => {
				const current = state.runs[projectId] ?? [];
				const exists = current.some((item) => item.id === run.id);
				const nextRuns = exists
					? current.map((item) => (item.id === run.id ? { ...item, ...run } : item))
					: [run, ...current];
				return {
					...state,
					runs: {
						...state.runs,
						[projectId]: nextRuns
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
				const assets = await apiListProjectLibrary(fetchFn, token, projectId, includeVersions);
				update((state) => ({
					...state,
					library: {
						...state.library,
						[projectId]: {
							assets,
							includeVersions,
							fetchedAt: new Date().toISOString()
						}
					},
					loading: false
				}));
				return assets;
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
					return {
						...state,
						library: {
							...state.library,
							[projectId]: {
								assets,
								includeVersions: cache?.includeVersions ?? Boolean(updated.versions?.length),
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
					const assets = cache.assets.filter((item) => item.id !== assetId);
					const nextLibrary = {
						...state.library,
						[projectId]: {
							assets,
							includeVersions: cache.includeVersions,
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
				const projectRunIds = new Set((state.runs[projectId] ?? []).map((run) => run.id));
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
				const activeProjectId =
					state.activeProjectId === projectId ? (updatedProjects[0]?.id ?? null) : state.activeProjectId;
				return {
					...state,
					projects: updatedProjects,
					runs,
					artifacts,
					library,
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
				const runs = await apiListProjectRuns(fetchFn, token, projectId, limit);
				update((state) => ({
					...state,
					runs: { ...state.runs, [projectId]: runs },
					loading: false
				}));
				return runs;
			} catch (error) {
				const message = normaliseError(error);
				update((state) => ({ ...state, loading: false, error: message }));
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
					const current = state.runs[projectId] ?? [];
					return {
						...state,
						runs: {
							...state.runs,
							[projectId]: [run, ...current]
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
	$active ? $state.runs[$active.id] ?? [] : []
);

export const activeProjectLibrary = derived([projectState, activeProject], ([$state, $active]) =>
	$active ? $state.library[$active.id]?.assets ?? [] : []
);
