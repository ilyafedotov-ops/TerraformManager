import { derived, writable } from 'svelte/store';
import {
	type ArtifactEntry,
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
	updateProject as apiUpdateProject,
	deleteProject as apiDeleteProject
} from '$lib/api/client';

type FetchFn = typeof fetch;

interface ArtifactCacheEntry {
	path: string;
	runId: string;
	entries: ArtifactEntry[];
	fetchedAt: string;
}

interface ProjectState {
	projects: ProjectSummary[];
	activeProjectId: string | null;
	runs: Record<string, ProjectRunSummary[]>;
	artifacts: Record<string, ArtifactCacheEntry>;
	loading: boolean;
	error: string | null;
}

const initialState: ProjectState = {
	projects: [],
	activeProjectId: null,
	runs: {},
	artifacts: {},
	loading: false,
	error: null
};

const makeArtifactKey = (runId: string, path = ''): string => `${runId}::${path || '.'}`;

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
				const activeProjectId =
					state.activeProjectId === projectId ? (projects[0]?.id ?? null) : state.activeProjectId;
				return { ...state, projects, runs, artifacts, activeProjectId };
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
				const activeProjectId =
					state.activeProjectId === projectId ? (updatedProjects[0]?.id ?? null) : state.activeProjectId;
				return {
					...state,
					projects: updatedProjects,
					runs,
					artifacts,
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
			update((state) => ({ ...state, loading: true, error: null }));
			try {
				const entries = await apiListRunArtifacts(fetchFn, token, projectId, runId, path === '.' ? undefined : path);
				update((state) => ({
					...state,
					artifacts: {
						...state.artifacts,
						[makeArtifactKey(runId, path)]: {
							runId,
							path,
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
