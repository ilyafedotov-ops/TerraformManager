<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
import RunArtifactsPanel from '$lib/components/projects/RunArtifactsPanel.svelte';
import {
	type GeneratedAssetSummary,
	type GeneratedAssetVersionSummary,
	type GeneratedAssetVersionFile,
	type GeneratedAssetDiffFileEntry,
	type ProjectDetail,
	type ProjectRunSummary,
	type ProjectSummary,
	type ProjectOverview,
	type ProjectConfigRecord,
	type ProjectArtifactRecord,
	downloadProjectLibraryAssetVersion,
	diffProjectLibraryAssetVersions,
	listProjectLibraryVersionFiles
} from '$lib/api/client';
import { projectState, activeProject, activeProjectRuns, activeProjectOverview } from '$lib/stores/project';
	import { notifyError, notifySuccess } from '$lib/stores/notifications';

	const { data } = $props();
	const token = data.token as string | null;
	const initialProjects = (data.projects ?? []) as ProjectSummary[];
	const loadError = data.error as string | undefined;

	if (initialProjects.length) {
		const snapshot = get(projectState);
		if (!snapshot.projects.length) {
			projectState.reset();
			for (const project of initialProjects) {
				projectState.upsertProject(project);
			}
			projectState.setActiveProject(initialProjects[0].id);
		}
	}

	onMount(() => {
		if (token) {
			void projectState.loadProjects(fetch, token).catch((error) => {
				console.error('Failed to load projects', error);
			});
		}
	});

type RunsCacheEntry = ReturnType<typeof projectState.getCachedRuns> | null;
type LibraryCacheEntry = ReturnType<typeof projectState.getCachedLibrary> | null;
type ConfigCacheEntry = ReturnType<typeof projectState.getCachedConfigs> | null;
type ArtifactIndexCacheEntry = ReturnType<typeof projectState.getCachedArtifactIndex> | null;

const projects = $derived($projectState.projects as ProjectSummary[]);
const activeProjectValue = $derived($activeProject as ProjectDetail | null);
const projectRuns = $derived($activeProjectRuns as ProjectRunSummary[]);
const libraryCache = $derived<LibraryCacheEntry>(
	(() => {
		const project = activeProjectValue;
		if (!project) {
			return null;
		}
		return $projectState.library[project.id] ?? null;
	})()
);
const libraryAssets = $derived<GeneratedAssetSummary[]>(libraryCache?.assets ?? []);
const libraryAssetTypes = $derived<string[]>(
	(() => {
		const values = Array.from(new Set(libraryAssets.map((asset) => asset.asset_type))).filter(
			(value): value is string => Boolean(value)
		);
		return values.sort((a, b) => a.localeCompare(b));
	})()
);
const libraryGeneratorTags = $derived<string[]>(
	(() => {
		const tags = new Set<string>();
		for (const asset of libraryAssets) {
			for (const tag of asset.tags ?? []) {
				if (typeof tag === 'string' && tag.startsWith('generator:')) {
					tags.add(tag.replace(/^generator:/, ''));
				}
			}
		}
		return Array.from(tags).sort((a, b) => a.localeCompare(b));
	})()
);
const overview = $derived($activeProjectOverview as ProjectOverview | null);

let runCache = $state<RunsCacheEntry>(null);
let configCache = $state<ConfigCacheEntry>(null);
let artifactIndexCache = $state<ArtifactIndexCacheEntry>(null);

const projectConfigs = $derived(configCache?.items ?? []);
const projectArtifacts = $derived(artifactIndexCache?.items ?? []);

	let searchQuery = $state('');
let activeTab = $state<'overview' | 'runs' | 'files' | 'configs' | 'artifacts' | 'library' | 'settings'>('overview');
	let createModalOpen = $state(false);

	let createName = $state('');
	let createDescription = $state('');
let createMetadata = $state('{\n\t"owner": "platform"\n}');
let createError = $state<string | null>(null);
let createBusy = $state(false);
let libraryTypeFilter = $state('all');
let libraryGeneratorFilter = $state('all');
const libraryTypeOptions = $derived<string[]>(['all', ...libraryAssetTypes]);
const filteredLibraryAssets = $derived<GeneratedAssetSummary[]>(
	(() => {
		const generatorFilter = libraryGeneratorFilter;
		return libraryAssets.filter((asset) => {
			const matchesType = libraryTypeFilter === 'all' || asset.asset_type === libraryTypeFilter;
			if (!matchesType) {
				return false;
			}
			if (generatorFilter === 'all') {
				return true;
			}
			const slugs =
				asset.tags
					?.filter((tag) => typeof tag === 'string' && tag.startsWith('generator:'))
					.map((tag) => tag.replace(/^generator:/, '')) ?? [];
			return slugs.includes(generatorFilter);
		});
	})()
);

	let editName = $state('');
	let editDescription = $state('');
	let editMetadata = $state('{\n\n}');
	let editError = $state<string | null>(null);
	let updateBusy = $state(false);
	let deleteBusy = $state(false);
	let removeFiles = $state(false);

	let runsRefreshing = $state(false);
	let runsLoadingMore = $state(false);
	let libraryLoading = $state(false);
	let libraryLoadingMore = $state(false);
	let libraryError = $state<string | null>(null);
	let overviewLoading = $state(false);
	let overviewError = $state<string | null>(null);
	let configsLoading = $state(false);
	let configsError = $state<string | null>(null);
	let configFormBusy = $state(false);
	let configFormError = $state<string | null>(null);
	let editingConfigId = $state<string | null>(null);
	let configNameInput = $state('');
	let configDescriptionInput = $state('');
	let configKindInput = $state('tfreview');
	let configRefInput = $state('');
	let configPayloadInput = $state('');
	let configTagsInput = $state('');
	let configMetadataInput = $state('{\n\n}');
	let configIsDefault = $state(false);
let artifactRunFilter = $state('');
	let artifactTableLoading = $state(false);
	let artifactTableError = $state<string | null>(null);
	let artifactEditTarget = $state<ProjectArtifactRecord | null>(null);
	let artifactTagsInput = $state('');
	let artifactMetadataInput = $state('{\n\n}');
	let artifactMediaTypeInput = $state('');
let artifactEditBusy = $state(false);
let artifactEditError = $state<string | null>(null);
let artifactSyncBusy = $state(false);

const formatAssetTypeLabel = (value: string) => {
	if (value === 'all') return 'All types';
	const mapping: Record<string, string> = {
		terraform_config: 'Terraform configs',
		scan_report: 'Scan reports',
	};
	return mapping[value] ?? value.replace(/_/g, ' ');
};

const formatGeneratorLabel = (value: string) => {
	if (value === 'all') return 'All generators';
	return value;
};

const setLibraryTypeFilterValue = (value: string) => {
	libraryTypeFilter = value;
};

const toggleLibraryGeneratorFilter = (value: string) => {
	libraryGeneratorFilter = libraryGeneratorFilter === value ? 'all' : value;
};

$effect(() => {
	if (libraryTypeFilter !== 'all' && !libraryAssetTypes.includes(libraryTypeFilter)) {
		libraryTypeFilter = 'all';
	}
	if (libraryGeneratorFilter !== 'all' && !libraryGeneratorTags.includes(libraryGeneratorFilter)) {
		libraryGeneratorFilter = 'all';
	}
});

type DiffState = {
	assetId: string;
	versionId: string;
	againstVersionId: string;
	diff: string | null;
	files: GeneratedAssetDiffFileEntry[];
	selectedPath: string | null;
	error: string | null;
	loading: boolean;
	ignoreWhitespace: boolean;
};

let diffState = $state<DiffState | null>(null);
let diffLayout = $state<'unified' | 'split'>('unified');

type VersionFileState = {
	expanded: boolean;
	loading: boolean;
	error: string | null;
	items: GeneratedAssetVersionFile[];
};

let versionFileState = $state<Record<string, VersionFileState>>({});

	let editAssetTarget = $state<GeneratedAssetSummary | null>(null);
	let editAssetName = $state('');
	let editAssetType = $state('');
	let editAssetTags = $state('');
	let editAssetDescription = $state('');
	let editAssetMetadata = $state('{\n\n}');
	let editAssetError = $state<string | null>(null);
	let editAssetSubmitting = $state(false);

	let metadataExpanded = $state(false);

	const pendingRunLoads = new Set<string>();
	const pendingLibraryLoads = new Set<string>();
	const pendingOverviewLoads = new Set<string>();
	const pendingConfigLoads = new Set<string>();
	const pendingArtifactIndexLoads = new Set<string>();

	const tabs: { id: typeof activeTab; label: string }[] = [
		{ id: 'overview', label: 'Overview' },
		{ id: 'runs', label: 'Runs' },
		{ id: 'files', label: 'Run files' },
		{ id: 'configs', label: 'Configs' },
		{ id: 'artifacts', label: 'Artifacts' },
		{ id: 'library', label: 'Library' },
		{ id: 'settings', label: 'Settings' }
	];

	const parseMetadata = (value: string) => {
		const trimmed = value.trim();
		if (!trimmed) {
			return {} as Record<string, unknown>;
		}
		return JSON.parse(trimmed) as Record<string, unknown>;
	};

	$effect(() => {
		const project = $activeProject as ProjectDetail | null;
		if (project) {
			editName = project.name;
			editDescription = project.description ?? '';
			try {
				editMetadata = JSON.stringify(project.metadata ?? {}, null, 2);
			} catch {
				editMetadata = '{\n\n}';
			}
			editError = null;
		} else {
			editName = '';
			editDescription = '';
			editMetadata = '{\n\n}';
			editError = null;
		}
	});

	let lastProjectId: string | null = null;
	$effect(() => {
		const project = $activeProject as ProjectDetail | null;
		if (project && project.id !== lastProjectId) {
			activeTab = 'overview';
			lastProjectId = project.id;
		}
	});

	$effect(() => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			return;
		}

		if (!projectState.getCachedRuns(project.id) && !pendingRunLoads.has(project.id)) {
			runsRefreshing = true;
			pendingRunLoads.add(project.id);
			void projectState
				.refreshRuns(fetch, token, project.id)
				.catch((error) => {
					console.error('Failed to load runs', error);
					notifyError('Unable to load project runs.');
				})
				.finally(() => {
					runsRefreshing = false;
					pendingRunLoads.delete(project.id);
				});
		}

		if (!projectState.getCachedLibrary(project.id) && !pendingLibraryLoads.has(project.id)) {
			libraryLoading = true;
			libraryError = null;
			pendingLibraryLoads.add(project.id);
			void projectState
				.loadLibrary(fetch, token, project.id, true)
				.catch((error) => {
					const message = error instanceof Error ? error.message : 'Unable to load project library.';
					libraryError = message;
					notifyError(message);
				})
				.finally(() => {
					libraryLoading = false;
					pendingLibraryLoads.delete(project.id);
				});
		}

		if (!projectState.getCachedOverview(project.id) && !pendingOverviewLoads.has(project.id)) {
			overviewLoading = true;
			overviewError = null;
			pendingOverviewLoads.add(project.id);
			void projectState
				.loadOverview(fetch, token, project.id)
				.catch((error) => {
					const message = error instanceof Error ? error.message : 'Unable to load overview.';
					overviewError = message;
					console.error('Failed to load overview', error);
				})
				.finally(() => {
					overviewLoading = false;
					pendingOverviewLoads.delete(project.id);
				});
		}
	});

	const handleSelectProject = (projectId: string) => {
		projectState.setActiveProject(projectId);
		activeTab = 'overview';
	};

	const handleCreate = async (event: SubmitEvent) => {
		event.preventDefault();
		if (!token) {
			notifyError('Sign in to create a project.');
			return;
		}
		createError = null;
		let metadata: Record<string, unknown> = {};
		try {
			metadata = parseMetadata(createMetadata);
		} catch (error) {
			createError = 'Metadata must be valid JSON.';
			console.warn('Invalid metadata payload', error);
			return;
		}
		if (!createName.trim()) {
			createError = 'Project name is required.';
			return;
		}

		createBusy = true;
		try {
			await projectState.createProject(fetch, token, {
				name: createName.trim(),
				description: createDescription.trim() || undefined,
				metadata
			});
			notifySuccess('Project created.');
			createName = '';
			createDescription = '';
			createMetadata = '{\n\t"owner": "platform"\n}';
			createModalOpen = false;
		} catch (error) {
			createError = error instanceof Error ? error.message : 'Failed to create project.';
		} finally {
			createBusy = false;
		}
	};

	const handleUpdate = async () => {
		const project = $activeProject;
		if (!project || !token) {
			notifyError('Select a project to update.');
			return;
		}
		editError = null;
		let metadata: Record<string, unknown> | null = null;
		try {
			metadata = parseMetadata(editMetadata);
		} catch (error) {
			editError = 'Metadata must be valid JSON.';
			console.warn('Invalid metadata payload', error);
			return;
		}
		if (!editName.trim()) {
			editError = 'Project name is required.';
			return;
		}

		updateBusy = true;
		try {
			await projectState.updateProject(fetch, token, project.id, {
				name: editName.trim(),
				description: editDescription.trim() || undefined,
				metadata
			});
			notifySuccess('Project updated.');
		} catch (error) {
			editError = error instanceof Error ? error.message : 'Failed to update project.';
		} finally {
			updateBusy = false;
		}
	};

	const handleDelete = async () => {
		const project = $activeProject;
		if (!project || !token) {
			notifyError('Select a project to delete.');
			return;
		}
		if (browser) {
			const confirmed = window.confirm(`Delete project "${project.name}"? This cannot be undone.`);
			if (!confirmed) {
				return;
			}
		}
		deleteBusy = true;
		try {
			await projectState.deleteProject(fetch, token, project.id, removeFiles);
			notifySuccess('Project deleted.');
			removeFiles = false;
		} catch (error) {
			notifyError(error instanceof Error ? error.message : 'Failed to delete project.');
		} finally {
			deleteBusy = false;
		}
	};

	const resetConfigForm = () => {
		editingConfigId = null;
		configNameInput = '';
		configDescriptionInput = '';
		configKindInput = 'tfreview';
		configRefInput = '';
		configPayloadInput = '';
		configTagsInput = '';
		configMetadataInput = '{\n\n}';
		configIsDefault = false;
		configFormError = null;
	};

	const handleEditConfig = (record: ProjectConfigRecord) => {
		editingConfigId = record.id;
		configNameInput = record.name;
		configDescriptionInput = record.description ?? '';
		configKindInput = record.kind ?? 'tfreview';
		configRefInput = record.config_name ?? '';
		configPayloadInput = record.payload ?? '';
		configTagsInput = record.tags.join(', ');
		configMetadataInput = JSON.stringify(record.metadata ?? {}, null, 2);
		configIsDefault = record.is_default;
		configFormError = null;
	};

	const handleConfigSubmit = async (event: SubmitEvent) => {
		event.preventDefault();
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			notifyError('Select a project to manage configs.');
			return;
		}
		configFormError = null;
		const name = configNameInput.trim();
		const kind = configKindInput.trim() || 'tfreview';
		const configName = configRefInput.trim();
		const payload = configPayloadInput.trim();
		if (!name) {
			configFormError = 'Config name is required.';
			return;
		}
		if (!configName && !payload) {
			configFormError = 'Provide either a saved config reference or inline payload.';
			return;
		}
		let metadata: Record<string, unknown>;
		try {
			metadata = parseMetadata(configMetadataInput);
		} catch (error) {
			console.warn('Invalid config metadata', error);
			configFormError = 'Metadata must be valid JSON.';
			return;
		}
		const tags = configTagsInput
			.split(',')
			.map((tag) => tag.trim())
			.filter(Boolean);

		configFormBusy = true;
		try {
			if (editingConfigId) {
				await projectState.updateProjectConfig(fetch, token, project.id, editingConfigId, {
					name,
					description: configDescriptionInput.trim() || undefined,
					config_name: configName || undefined,
					payload: payload || undefined,
					kind,
					tags,
					metadata,
					is_default: configIsDefault
				});
				notifySuccess('Config updated.');
			} else {
				await projectState.createProjectConfig(fetch, token, project.id, {
					name,
					description: configDescriptionInput.trim() || undefined,
					config_name: configName || undefined,
					payload: payload || undefined,
					kind,
					tags,
					metadata,
					is_default: configIsDefault
				});
				notifySuccess('Config created.');
			}
			resetConfigForm();
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to save config.';
			configFormError = message;
			notifyError(message);
		} finally {
			configFormBusy = false;
		}
	};

	const handleDeleteConfig = async (configId: string) => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			notifyError('Select a project to manage configs.');
			return;
		}
		if (browser) {
			const confirmed = window.confirm('Delete this project config?');
			if (!confirmed) return;
		}
		configsLoading = true;
		try {
			await projectState.deleteProjectConfig(fetch, token, project.id, configId);
			notifySuccess('Config deleted.');
			if (editingConfigId === configId) {
				resetConfigForm();
			}
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to delete config.';
			configsError = message;
			notifyError(message);
		} finally {
			configsLoading = false;
		}
	};

	const handleReloadConfigs = async () => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			return;
		}
		configsLoading = true;
		configsError = null;
		try {
			await projectState.loadConfigs(fetch, token, project.id);
			notifySuccess('Configs reloaded.');
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to reload configs.';
			configsError = message;
			notifyError(message);
		} finally {
			configsLoading = false;
		}
	};

	const handleSetDefaultConfig = async (configId: string) => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) return;
		try {
			await projectState.updateProjectConfig(fetch, token, project.id, configId, { is_default: true });
			notifySuccess('Default config updated.');
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to update default config.';
			notifyError(message);
		}
	};

	const handleReloadArtifactsIndex = async () => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) return;
		artifactTableLoading = true;
		artifactTableError = null;
		try {
		await projectState.loadProjectArtifactIndex(fetch, token, project.id, { runId: artifactRunFilter || null });
			notifySuccess('Artifacts reloaded.');
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to reload artifacts.';
			artifactTableError = message;
			notifyError(message);
		} finally {
			artifactTableLoading = false;
		}
	};

	const handleEditArtifactMetadata = (record: ProjectArtifactRecord) => {
		artifactEditTarget = record;
		artifactTagsInput = record.tags.join(', ');
		artifactMetadataInput = JSON.stringify(record.metadata ?? {}, null, 2);
		artifactMediaTypeInput = record.media_type ?? '';
		artifactEditError = null;
	};

	const resetArtifactEdit = () => {
		if (artifactEditBusy) return;
		artifactEditTarget = null;
		artifactTagsInput = '';
		artifactMetadataInput = '{\n\n}';
		artifactMediaTypeInput = '';
		artifactEditError = null;
	};

	const handleArtifactMetadataSubmit = async (event: SubmitEvent) => {
		event.preventDefault();
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token || !artifactEditTarget) {
			notifyError('Select a project and artifact to edit.');
			return;
		}
		let metadata: Record<string, unknown>;
		try {
			metadata = parseMetadata(artifactMetadataInput);
		} catch (error) {
			artifactEditError = 'Metadata must be valid JSON.';
			console.warn('Invalid artifact metadata', error);
			return;
		}
		const tags = artifactTagsInput
			.split(',')
			.map((tag) => tag.trim())
			.filter(Boolean);
		artifactEditBusy = true;
		try {
			await projectState.updateProjectArtifactMetadata(fetch, token, project.id, artifactEditTarget.id, {
				tags,
				metadata,
				media_type: artifactMediaTypeInput.trim() || undefined
			});
			notifySuccess('Artifact metadata updated.');
			resetArtifactEdit();
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to update artifact.';
			artifactEditError = message;
			notifyError(message);
		} finally {
			artifactEditBusy = false;
		}
	};

	const handleLoadMoreProjectArtifacts = async () => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) return;
		if (!artifactIndexCache?.nextCursor) return;
		artifactTableLoading = true;
		try {
			await projectState.loadMoreProjectArtifactIndex(fetch, token, project.id, { runId: artifactRunFilter || null });
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to load more artifacts.';
			artifactTableError = message;
			notifyError(message);
		} finally {
			artifactTableLoading = false;
		}
	};

	const handleSyncArtifacts = async () => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token || !artifactRunFilter) {
			notifyError('Select a run filter to sync artifacts.');
			return;
		}
		artifactSyncBusy = true;
		try {
			await projectState.syncRunArtifacts(fetch, token, project.id, artifactRunFilter);
			await projectState.loadProjectArtifactIndex(fetch, token, project.id, { runId: artifactRunFilter });
			await projectState.loadProjectArtifactIndex(fetch, token, project.id, { runId: null });
			notifySuccess('Artifacts synced.');
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to sync artifacts.';
			artifactTableError = message;
			notifyError(message);
		} finally {
			artifactSyncBusy = false;
		}
	};
	const handleRefreshRuns = async () => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			notifyError('Select a project to refresh runs.');
			return;
		}
		runsRefreshing = true;
		try {
			await projectState.refreshRuns(fetch, token, project.id);
			notifySuccess('Runs refreshed.');
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to refresh runs.';
			notifyError(message);
		} finally {
			runsRefreshing = false;
		}
	};

	const handleLoadMoreRuns = async () => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			return;
		}
		if (!runCache?.nextCursor) {
			return;
		}
		runsLoadingMore = true;
		try {
			await projectState.loadMoreRuns(fetch, token, project.id);
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to load additional runs.';
			notifyError(message);
		} finally {
			runsLoadingMore = false;
		}
	};

	const handleRefreshLibrary = async () => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			notifyError('Select a project to refresh.');
			return;
		}
		libraryLoading = true;
		libraryError = null;
		try {
			await projectState.loadLibrary(fetch, token, project.id, true);
			notifySuccess('Library refreshed.');
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to refresh library.';
			libraryError = message;
			notifyError(message);
		} finally {
			libraryLoading = false;
		}
	};

	const handleLoadMoreLibrary = async () => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			return;
		}
		if (!libraryCache?.nextCursor) {
			return;
		}
		libraryLoadingMore = true;
		try {
			await projectState.loadMoreLibrary(fetch, token, project.id);
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to load additional assets.';
			notifyError(message);
		} finally {
			libraryLoadingMore = false;
		}
	};

	const handleDeleteAsset = async (assetId: string) => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			notifyError('Select a project to delete assets.');
			return;
		}
		if (browser) {
			const confirmed = window.confirm('Delete this library asset? This cannot be undone.');
			if (!confirmed) {
				return;
			}
		}
		libraryLoading = true;
		try {
			await projectState.deleteLibraryAsset(fetch, token, project.id, assetId);
			notifySuccess('Library asset deleted.');
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to delete asset.';
			libraryError = message;
			notifyError(message);
		} finally {
			libraryLoading = false;
		}
	};

	const handleDownloadVersion = async (assetId: string, version: GeneratedAssetVersionSummary) => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			notifyError('Select a project to download assets.');
			return;
		}
		try {
			const response = await downloadProjectLibraryAssetVersion(
				fetch,
				token,
				project.id,
				assetId,
				version.id
			);
			const blob = await response.blob();
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement('a');
			anchor.href = url;
			anchor.download = version.display_path || `asset-${version.id}`;
			document.body.appendChild(anchor);
			anchor.click();
			document.body.removeChild(anchor);
			if (browser) {
				setTimeout(() => URL.revokeObjectURL(url), 500);
			}
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to download version.';
			notifyError(message);
		}
	};

	const handleDiffVersion = async (
		asset: GeneratedAssetSummary,
		version: GeneratedAssetVersionSummary,
		againstVersionId: string | null,
		options: { ignoreWhitespace?: boolean } = {}
	) => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			notifyError('Select a project to diff assets.');
			return;
		}
		if (!againstVersionId) {
			notifyError('Select another version to diff against.');
			return;
		}
	diffState = {
		assetId: asset.id,
		versionId: version.id,
		againstVersionId,
		ignoreWhitespace: options.ignoreWhitespace ?? false,
		diff: null,
		files: [],
		selectedPath: null,
		error: null,
		loading: true
	};
		try {
			const payload = await diffProjectLibraryAssetVersions(
				fetch,
				token,
				project.id,
				asset.id,
				version.id,
				againstVersionId,
				options
			);
			diffState = {
				assetId: asset.id,
				versionId: version.id,
				againstVersionId,
				ignoreWhitespace: payload.ignore_whitespace ?? options.ignoreWhitespace ?? false,
				diff: payload.diff,
				files: payload.files ?? [],
				selectedPath: (() => {
					const files = payload.files ?? [];
					if (!files.length) {
						return null;
					}
					const withDiff = files.find((item) => item.diff && item.diff.length);
					return (withDiff ?? files[0]).path;
				})(),
				error: null,
				loading: false
			};
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to generate diff.';
			const ignoreWhitespace = options.ignoreWhitespace ?? diffState?.ignoreWhitespace ?? false;
			diffState = {
				assetId: asset.id,
				versionId: version.id,
				againstVersionId,
				ignoreWhitespace,
				diff: null,
				files: [],
				selectedPath: null,
				error: message,
				loading: false
			};
		}
	};

	const handleCloseDiff = () => {
		diffState = null;
	};

	const handleCopyDiff = async () => {
		const diffText = getCurrentDiffText();
		if (!diffText) {
			notifyError('No diff available to copy.');
			return;
		}
		if (!browser || !navigator.clipboard) {
			notifyError('Clipboard access is not available.');
			return;
		}
		try {
			await navigator.clipboard.writeText(diffText);
			notifySuccess('Diff copied to clipboard.');
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to copy diff.';
			notifyError(message);
		}
	};

	const handleDownloadDiffText = () => {
		if (!diffState) {
			notifyError('No diff available to download.');
			return;
		}
		const diffText = getCurrentDiffText();
		if (!diffText) {
			notifyError('No diff available to download.');
			return;
		}
		const blob = new Blob([diffText], { type: 'text/plain;charset=utf-8' });
		const url = URL.createObjectURL(blob);
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = `diff-${diffState.versionId}-vs-${diffState.againstVersionId}.patch`;
		document.body.appendChild(anchor);
		anchor.click();
		document.body.removeChild(anchor);
		if (browser) {
			setTimeout(() => URL.revokeObjectURL(url), 500);
		}
	};

	const toggleIgnoreWhitespace = () => {
		const currentDiff = diffState;
		if (!currentDiff) return;
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			notifyError('Select a project to diff assets.');
			return;
		}
		const asset = libraryAssets.find((item) => item.id === currentDiff.assetId);
		if (!asset) {
			notifyError('Asset not found in current library.');
			return;
		}
		const version = asset.versions?.find((item) => item.id === currentDiff.versionId);
		if (!version) {
			notifyError('Version not found.');
			return;
		}
		const baseVersionId = currentDiff.againstVersionId;
		if (!baseVersionId) {
			notifyError('No base version selected for diff.');
			return;
		}
		void handleDiffVersion(asset, version, baseVersionId, {
			ignoreWhitespace: !currentDiff.ignoreWhitespace
		});
	};

	const setDiffLayout = (layout: 'unified' | 'split') => {
		diffLayout = layout;
	};

	type SplitRow = {
		left: string;
		right: string;
		type: 'context' | 'added' | 'removed';
	};

const buildSplitRows = (diffText: string): SplitRow[] => {
	const rows: SplitRow[] = [];
	for (const rawLine of diffText.split('\n')) {
			if (!rawLine || rawLine.startsWith('@@') || rawLine.startsWith('---') || rawLine.startsWith('+++')) {
				continue;
			}
			if (rawLine.startsWith('+')) {
				rows.push({ left: '', right: rawLine.slice(1), type: 'added' });
				continue;
			}
			if (rawLine.startsWith('-')) {
				rows.push({ left: rawLine.slice(1), right: '', type: 'removed' });
				continue;
			}
			if (rawLine.startsWith('\\')) {
				continue;
			}
			const value = rawLine.startsWith(' ') ? rawLine.slice(1) : rawLine;
			rows.push({ left: value, right: value, type: 'context' });
	}
	return rows;
};

const getSelectedDiffEntry = (): GeneratedAssetDiffFileEntry | null => {
	const current = diffState;
	if (!current || !current.selectedPath) {
		return null;
	}
	return current.files.find((file) => file.path === current.selectedPath) ?? null;
};

const getCurrentDiffText = (): string | null => {
	const entry = getSelectedDiffEntry();
	if (entry?.diff) {
		return entry.diff;
	}
	return diffState?.diff ?? null;
};

const selectDiffFile = (path: string) => {
	if (!diffState) return;
	diffState = { ...diffState, selectedPath: path };
};

const diffFileStatusClass = (status: string): string => {
	switch (status) {
		case 'added':
			return 'border-emerald-200 bg-emerald-50 text-emerald-600';
		case 'removed':
			return 'border-rose-200 bg-rose-50 text-rose-600';
		case 'modified':
			return 'border-amber-200 bg-amber-50 text-amber-600';
		default:
			return 'border-slate-200 bg-slate-50 text-slate-500';
	}
};

const validationStatusLabel = (summary?: Record<string, unknown> | null): string => {
	if (!summary) return 'skipped';
	const raw = summary['status'];
	return typeof raw === 'string' ? raw : 'unknown';
};

const validationStatusClass = (status: string): string => {
	switch (status) {
		case 'passed':
			return 'border-emerald-200 bg-emerald-50 text-emerald-600';
		case 'failed':
			return 'border-rose-200 bg-rose-50 text-rose-600';
		default:
			return 'border-slate-200 bg-slate-50 text-slate-500';
	}
};

const formatBytes = (value?: number | null): string => {
	if (value === null || value === undefined) {
		return '—';
	}
	const units = ['B', 'KB', 'MB', 'GB'];
	let size = value;
	let idx = 0;
	while (size >= 1024 && idx < units.length - 1) {
		size /= 1024;
		idx += 1;
	}
	const decimals = size >= 10 || idx === 0 ? 0 : 1;
	return `${size.toFixed(decimals)} ${units[idx]}`;
};

const getVersionFileKey = (assetId: string, versionId: string) => `${assetId}::${versionId}`;

const getVersionFileEntry = (assetId: string, versionId: string): VersionFileState => {
	const key = getVersionFileKey(assetId, versionId);
	return (
		versionFileState[key] ?? {
			expanded: false,
			loading: false,
			error: null,
			items: []
		}
	);
};

const toggleVersionFiles = async (asset: GeneratedAssetSummary, version: GeneratedAssetVersionSummary) => {
	const project = $activeProject as ProjectDetail | null;
	if (!project || !token) {
		notifyError('Select a project to load version files.');
		return;
	}
	const key = getVersionFileKey(asset.id, version.id);
	const entry = getVersionFileEntry(asset.id, version.id);
	const nextExpanded = !entry.expanded;
	versionFileState = {
		...versionFileState,
		[key]: {
			...entry,
			expanded: nextExpanded
		}
	};
	if (!nextExpanded || entry.items.length) {
		return;
	}
	versionFileState = {
		...versionFileState,
		[key]: {
			...entry,
			expanded: true,
			loading: true,
			error: null
		}
	};
	try {
		const items = await listProjectLibraryVersionFiles(fetch, token, project.id, asset.id, version.id);
		versionFileState = {
			...versionFileState,
			[key]: {
				expanded: true,
				loading: false,
				error: null,
				items
			}
		};
	} catch (error) {
		const message = error instanceof Error ? error.message : 'Failed to load version files.';
		notifyError(message);
		versionFileState = {
			...versionFileState,
			[key]: {
				expanded: true,
				loading: false,
				error: message,
				items: []
			}
		};
	}
};

	const openEditAsset = (asset: GeneratedAssetSummary) => {
		editAssetTarget = asset;
		editAssetName = asset.name;
		editAssetType = asset.asset_type;
		editAssetDescription = asset.description ?? '';
		editAssetTags = asset.tags.join(', ');
		editAssetMetadata = JSON.stringify(asset.metadata ?? {}, null, 2);
		editAssetError = null;
	};

	const closeEditAsset = () => {
		if (editAssetSubmitting) return;
		editAssetTarget = null;
		editAssetError = null;
	};

	const handleEditAssetSubmit = async (event: SubmitEvent) => {
		event.preventDefault();
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token || !editAssetTarget) {
			notifyError('Select a project to update assets.');
			return;
		}
		const trimmedName = editAssetName.trim();
		if (!trimmedName) {
			editAssetError = 'Asset name is required.';
			return;
		}
		const trimmedType = editAssetType.trim();
		if (!trimmedType) {
			editAssetError = 'Asset type is required.';
			return;
		}
		const tagList = editAssetTags
			.split(',')
			.map((tag) => tag.trim())
			.filter((tag) => tag.length > 0);
		let metadata: Record<string, unknown> | undefined;
		const metadataPayload = editAssetMetadata.trim();
		if (metadataPayload) {
			try {
				const parsed = JSON.parse(metadataPayload);
				if (!parsed || typeof parsed !== 'object') {
					throw new Error('Metadata must be a JSON object.');
				}
				metadata = parsed as Record<string, unknown>;
			} catch (error) {
				editAssetError = error instanceof Error ? error.message : 'Metadata must be valid JSON.';
				return;
			}
		}

		editAssetSubmitting = true;
		editAssetError = null;
		try {
			await projectState.updateLibraryAsset(fetch, token, project.id, editAssetTarget.id, {
				name: trimmedName,
				asset_type: trimmedType,
				description: editAssetDescription.trim() || undefined,
				tags: tagList,
				metadata
			});
			notifySuccess('Asset updated.');
			closeEditAsset();
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to update asset.';
			editAssetError = message;
			notifyError(message);
		} finally {
			editAssetSubmitting = false;
		}
	};

	const matchesSearch = (project: ProjectSummary) => {
		const term = searchQuery.trim().toLowerCase();
		if (!term) return true;
		return (
			project.name.toLowerCase().includes(term) ||
			project.slug.toLowerCase().includes(term) ||
			(project.description ?? '').toLowerCase().includes(term)
		);
	};

let sortedProjects = $state<ProjectSummary[]>([]);

$effect(() => {
	runCache = activeProjectValue ? projectState.getCachedRuns(activeProjectValue.id) : null;
});

$effect(() => {
	configCache = activeProjectValue ? projectState.getCachedConfigs(activeProjectValue.id) : null;
});

$effect(() => {
	artifactIndexCache = activeProjectValue
		? projectState.getCachedArtifactIndex(activeProjectValue.id, artifactRunFilter || null)
		: null;
});

$effect(() => {
	const items = projects ?? [];
	const sorted = [...items]
		.sort((a, b) => (b.last_activity_at ?? '').localeCompare(a.last_activity_at ?? ''))
		.filter(matchesSearch);
	sortedProjects = sorted;
});

	$effect(() => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			return;
		}
		const projectId = project.id;
		if (
			activeTab === 'configs' &&
			!projectState.getCachedConfigs(projectId) &&
			!pendingConfigLoads.has(projectId)
		) {
			pendingConfigLoads.add(projectId);
			configsLoading = true;
			configsError = null;
			void projectState
				.loadConfigs(fetch, token, projectId)
				.catch((error) => {
					const message = error instanceof Error ? error.message : 'Unable to load configs.';
					configsError = message;
					notifyError(message);
				})
				.finally(() => {
					configsLoading = false;
					pendingConfigLoads.delete(projectId);
				});
		}
	});

	$effect(() => {
		const project = $activeProject as ProjectDetail | null;
		if (!project || !token) {
			return;
		}
		const projectId = project.id;
		const artifactKey = `${projectId}::${artifactRunFilter || 'all'}`;
		if (
			activeTab === 'artifacts' &&
			!projectState.getCachedArtifactIndex(projectId, artifactRunFilter || null) &&
			!pendingArtifactIndexLoads.has(artifactKey)
		) {
			pendingArtifactIndexLoads.add(artifactKey);
			artifactTableLoading = true;
			artifactTableError = null;
			void projectState
				.loadProjectArtifactIndex(fetch, token, projectId, { runId: artifactRunFilter || null })
				.catch((error) => {
					const message = error instanceof Error ? error.message : 'Unable to load artifacts.';
					artifactTableError = message;
					notifyError(message);
				})
				.finally(() => {
					artifactTableLoading = false;
					pendingArtifactIndexLoads.delete(artifactKey);
				});
		}
	});
</script>

<section class="space-y-8">
	<header class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
		<div class="space-y-2">
			<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Projects</p>
			<h1 class="text-3xl font-semibold text-slate-700">Manage workspaces</h1>
			<p class="text-sm text-slate-500">
				Create TerraformManager workspaces, inspect run history, manage artifacts, and curate the shared library without
				leaving the dashboard.
			</p>
		</div>
		<div class="flex items-center gap-2 sm:justify-end">
			<button
				type="button"
				class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-50"
				onclick={() => {
					if (token) {
						void projectState.loadProjects(fetch, token).catch((error) => {
							console.error('Failed to reload projects', error);
							notifyError('Failed to reload projects');
						});
					}
				}}
			>
				Refresh list
			</button>
			<button
				type="button"
				class="inline-flex items-center gap-2 rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-sky-200 transition hover:bg-sky-600"
				onclick={() => {
					createModalOpen = true;
					createError = null;
				}}
			>
				New project
			</button>
		</div>
	</header>

	{#if loadError}
		<div class="rounded-3xl border border-amber-300 bg-amber-50 px-6 py-3 text-sm text-amber-700">
			{loadError}
</div>
{/if}

	<div class="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
		<aside class="space-y-4 lg:sticky lg:top-24">
			<div class="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200">
				<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="project-search">
					Search
				</label>
				<input
					id="project-search"
					type="search"
					class="mt-2 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
					bind:value={searchQuery}
					placeholder="Filter by name or slug"
				/>
			</div>
			<div class="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200">
				<div class="flex items-center justify-between">
					<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Projects</h3>
					<span class="text-xs font-semibold text-slate-400">{projects.length}</span>
				</div>
				{#if !sortedProjects.length}
					<p class="mt-4 text-sm text-slate-500">No projects match your filters.</p>
				{:else}
					<ul class="mt-3 space-y-2">
						{#each sortedProjects as project (project.id)}
							<li>
								<button
									type="button"
									class={`w-full rounded-2xl border px-4 py-3 text-left transition ${
										activeProjectValue && project.id === activeProjectValue.id
											? 'border-sky-300 bg-sky-50 text-sky-600'
											: 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
									}`}
									onclick={() => handleSelectProject(project.id)}
								>
									<div class="flex items-start justify-between gap-3">
										<div>
											<p class="text-sm font-semibold">{project.name}</p>
											<p class="text-xs uppercase tracking-[0.2em] text-slate-400">{project.slug}</p>
										</div>
										<div class="flex flex-col items-end gap-1">
											<span class="rounded-full border border-slate-200 px-2 py-[2px] text-[0.65rem] text-slate-500">
												{project.run_count ?? 0} run(s)
											</span>
											<span class="rounded-full border border-slate-200 px-2 py-[2px] text-[0.65rem] text-slate-500">
												{project.library_asset_count ?? 0} asset(s)
											</span>
											<span class="rounded-full border border-slate-200 px-2 py-[2px] text-[0.65rem] text-slate-500">
												{project.config_count ?? 0} config(s)
											</span>
											<span class="rounded-full border border-slate-200 px-2 py-[2px] text-[0.65rem] text-slate-500">
												{project.artifact_count ?? 0} artifact(s)
											</span>
										</div>
									</div>
									{#if project.latest_run}
										<div class="mt-2 flex items-center justify-between text-xs text-slate-400">
											<span class="uppercase tracking-[0.25em]">{project.latest_run.status}</span>
											<span>{project.latest_run.created_at}</span>
										</div>
									{/if}
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		</aside>

		<main class="space-y-6">
			{#if activeProjectValue}
				<section class="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm shadow-slate-200">
					<div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
						<div>
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Selected project</p>
							<h2 class="text-2xl font-semibold text-slate-700">{activeProjectValue.name}</h2>
							<p class="text-sm text-slate-500">
								{activeProjectValue.description || 'No description yet. Use the settings tab to add one.'}
							</p>
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<button
								type="button"
								class={`inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-50 ${
									runsRefreshing ? 'cursor-wait opacity-60' : ''
								}`}
								onclick={handleRefreshRuns}
								disabled={runsRefreshing}
							>
								{runsRefreshing ? 'Refreshing runs…' : 'Refresh runs'}
							</button>
							<button
								type="button"
								class={`inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-50 ${
									libraryLoading ? 'cursor-wait opacity-60' : ''
								}`}
								onclick={handleRefreshLibrary}
								disabled={libraryLoading}
							>
								{libraryLoading ? 'Refreshing library…' : 'Refresh library'}
							</button>
						</div>
					</div>

					<nav class="mt-6 flex flex-wrap gap-2 border-b border-slate-200 pb-2">
						{#each tabs as tab}
							<button
								type="button"
								class={`rounded-full px-4 py-1 text-sm font-semibold transition ${
									activeTab === tab.id
										? 'bg-sky-500 text-white shadow-sm shadow-sky-200'
										: 'bg-slate-100 text-slate-500 hover:bg-slate-200'
								}`}
								onclick={() => (activeTab = tab.id)}
							>
								{tab.label}
							</button>
						{/each}
					</nav>

					<div class="mt-6 space-y-6">
						{#if activeTab === 'overview'}
							{#if overviewLoading}
								<p class="text-sm text-slate-500">Loading overview…</p>
							{:else if overviewError}
								<p class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">{overviewError}</p>
							{:else if overview}
								<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
									<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
										<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Total runs</p>
										<p class="mt-2 text-2xl font-semibold text-slate-700">{overview.run_count}</p>
										<p class="mt-1 text-xs text-slate-400">Includes generator and review executions.</p>
									</div>
									<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
										<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Library assets</p>
										<p class="mt-2 text-2xl font-semibold text-slate-700">{overview.library_asset_count}</p>
										<p class="mt-1 text-xs text-slate-400">Versioned artifacts promoted from runs.</p>
									</div>
									<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
										<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Last activity</p>
										<p class="mt-2 text-lg font-semibold text-slate-700">{overview.last_activity_at ?? '—'}</p>
										<p class="mt-1 text-xs text-slate-400">Most recent run, asset update, or edit.</p>
									</div>
									<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
										<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Latest status</p>
										<p class="mt-2 text-lg font-semibold text-slate-700">
											{overview.latest_run ? overview.latest_run.status : 'No runs yet'}
										</p>
										<p class="mt-1 text-xs text-slate-400">
											{overview.latest_run ? overview.latest_run.created_at : 'Run the generator to populate summary data.'}
										</p>
									</div>
									<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
										<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Project configs</p>
										<p class="mt-2 text-2xl font-semibold text-slate-700">{overview.config_count}</p>
										<p class="mt-1 text-xs text-slate-400">
											Default: {overview.default_config ? overview.default_config.name : 'Unset'}
										</p>
									</div>
									<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
										<p class="text-xs uppercase tracking-[0.3em] text-slate-400">Tracked artifacts</p>
										<p class="mt-2 text-2xl font-semibold text-slate-700">{overview.artifact_count}</p>
										<p class="mt-1 text-xs text-slate-400">Artifacts promoted from run outputs.</p>
									</div>
								</div>

								<div class="grid gap-4 lg:grid-cols-2">
									<section class="rounded-2xl border border-slate-200 bg-white px-4 py-4">
										<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Latest run</h3>
										{#if overview.latest_run}
											<div class="mt-3 space-y-2 text-sm text-slate-600">
												<p class="text-base font-semibold text-slate-700">{overview.latest_run.label}</p>
												<div class="flex flex-wrap items-center gap-2 text-xs">
													<span class="rounded-full border border-slate-200 px-2 py-[1px] uppercase tracking-[0.25em] text-slate-400">
														{overview.latest_run.kind}
													</span>
													<span class="rounded-full border border-slate-200 px-2 py-[1px] text-slate-500">
														{overview.latest_run.status}
													</span>
													{#if overview.latest_run.created_at}
														<span class="text-slate-400">{overview.latest_run.created_at}</span>
													{/if}
												</div>
												{#if overview.latest_run.summary}
													<details class="text-xs text-slate-500">
														<summary class="cursor-pointer font-semibold">Summary</summary>
														<pre class="mt-2 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[0.75rem] text-slate-600">
{JSON.stringify(overview.latest_run.summary, null, 2)}</pre>
													</details>
												{/if}
											</div>
										{:else}
											<p class="mt-3 text-sm text-slate-500">
												No runs recorded for this project yet. Trigger a generator or review run to populate the overview.
											</p>
										{/if}
									</section>
								</div>

								<div class="grid gap-4 lg:grid-cols-2">
									<section class="rounded-2xl border border-slate-200 bg-white px-4 py-4">
										<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Default config</h3>
										{#if overview.default_config}
											<div class="mt-3 space-y-2 text-sm text-slate-600">
												<div class="flex items-center justify-between text-xs text-slate-400">
													<span class="font-semibold text-slate-700">{overview.default_config.name}</span>
													<span class="rounded-full border border-slate-200 px-2 py-[2px] text-[0.65rem]">
														{overview.default_config.kind}
													</span>
												</div>
												{#if overview.default_config.description}
													<p class="text-xs text-slate-500">{overview.default_config.description}</p>
												{/if}
												<p class="text-xs text-slate-400">
													{overview.default_config.config_name
														? `References saved config "${overview.default_config.config_name}".`
														: 'Inline payload stored with this project.'}
												</p>
												{#if overview.default_config.tags.length}
													<div class="flex flex-wrap gap-1 text-[0.65rem] text-slate-500">
														{#each overview.default_config.tags as tag}
															<span class="rounded-full border border-slate-200 px-2 py-[2px]">{tag}</span>
														{/each}
													</div>
												{/if}
											</div>
										{:else}
											<p class="mt-3 text-sm text-slate-500">
												No project config assigned. Use the Configs tab to create one.
											</p>
										{/if}
									</section>
									<section class="rounded-2xl border border-slate-200 bg-white px-4 py-4">
										<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Recent artifacts</h3>
										{#if overview.recent_artifacts?.length}
											<ul class="mt-3 space-y-2 text-sm text-slate-600">
												{#each overview.recent_artifacts as artifact (artifact.id)}
													<li class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
														<div class="flex items-center justify-between">
															<div>
																<p class="font-semibold text-slate-700">{artifact.name}</p>
																<p class="text-xs text-slate-400">
																	Run: {artifact.run_id ?? 'manual'} · {artifact.relative_path}
																</p>
															</div>
															<div class="flex flex-wrap gap-1 text-[0.65rem] text-slate-500">
																{#if artifact.tags.length}
																	{#each artifact.tags.slice(0, 3) as tag}
																		<span class="rounded-full border border-slate-200 px-2 py-[2px]">{tag}</span>
																	{/each}
																	{#if artifact.tags.length > 3}
																		<span class="rounded-full border border-slate-200 px-2 py-[2px]">
																			+{artifact.tags.length - 3}
																		</span>
																	{/if}
																{:else}
																	<span class="rounded-full border border-slate-200 px-2 py-[2px]">untagged</span>
																{/if}
															</div>
														</div>
													</li>
												{/each}
											</ul>
										{:else}
											<p class="mt-3 text-sm text-slate-500">
												No artifacts promoted yet. Upload run outputs or promote library assets to populate this list.
											</p>
										{/if}
									</section>
								</div>

								{#if overview.metrics}
									<section class="rounded-2xl border border-slate-200 bg-white px-4 py-4">
										<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Key metrics</h3>
										<div class="mt-3 grid gap-4 md:grid-cols-3">
											<div class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
												<p class="font-semibold uppercase tracking-[0.25em] text-slate-400">Cost</p>
												<pre class="mt-2 overflow-auto font-mono text-[0.7rem]">
{JSON.stringify(overview.metrics.cost ?? {}, null, 2)}</pre>
											</div>
											<div class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
												<p class="font-semibold uppercase tracking-[0.25em] text-slate-400">Drift</p>
												<pre class="mt-2 overflow-auto font-mono text-[0.7rem]">
{JSON.stringify(overview.metrics.drift ?? {}, null, 2)}</pre>
											</div>
											<div class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
												<p class="font-semibold uppercase tracking-[0.25em] text-slate-400">Policy</p>
												<pre class="mt-2 overflow-auto font-mono text-[0.7rem]">
{JSON.stringify(overview.metrics.policy ?? {}, null, 2)}</pre>
											</div>
										</div>
									</section>
								{/if}
							{:else}
								<p class="text-sm text-slate-500">
									Run the generator or curate assets to populate the overview summary for this workspace.
								</p>
							{/if}
						{:else if activeTab === 'runs'}
							<div class="space-y-4">
								{#if !projectRuns.length}
									<p class="text-sm text-slate-500">No runs recorded yet.</p>
								{:else}
									<ul class="space-y-2">
										{#each projectRuns as run (run.id)}
											<li class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
												<div class="flex flex-wrap items-center justify-between gap-2">
													<div>
														<p class="font-semibold text-slate-700">{run.label}</p>
														<p class="text-xs uppercase tracking-[0.2em] text-slate-400">{run.kind}</p>
													</div>
													<div class="flex items-center gap-2 text-xs text-slate-500">
														<span class="rounded-full border border-slate-200 px-3 py-[2px] font-semibold text-slate-600">
															{run.status}
														</span>
														{#if run.created_at}
															<span>{run.created_at}</span>
														{/if}
													</div>
												</div>
												{#if run.parameters}
													<details class="mt-2 text-xs text-slate-500">
														<summary class="cursor-pointer font-semibold">Parameters</summary>
														<pre class="mt-2 overflow-auto rounded-xl border border-slate-200 bg-white p-3 font-mono text-[0.7rem]">
{JSON.stringify(run.parameters, null, 2)}</pre>
													</details>
												{/if}
												{#if run.summary}
													<details class="mt-2 text-xs text-slate-500">
														<summary class="cursor-pointer font-semibold">Summary</summary>
														<pre class="mt-2 overflow-auto rounded-xl border border-slate-200 bg-white p-3 font-mono text-[0.7rem]">
{JSON.stringify(run.summary, null, 2)}</pre>
													</details>
												{/if}
												{#if run.report_id && activeProjectValue}
													<div class="mt-3">
														<a
															class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-600 transition hover:bg-sky-50 hover:text-sky-600"
															href={`/projects/${activeProjectValue.id}/reports/${run.report_id}`}
														>
															View linked report
														</a>
													</div>
												{/if}
											</li>
										{/each}
									</ul>
									<div class="flex items-center justify-between">
										<span class="text-xs text-slate-400">
											Showing {projectRuns.length} of {runCache?.totalCount ?? projectRuns.length} run(s)
										</span>
										{#if runCache?.nextCursor}
											<button
												type="button"
												class={`inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-500 transition hover:bg-slate-50 ${
													runsLoadingMore ? 'cursor-wait opacity-60' : ''
												}`}
												onclick={handleLoadMoreRuns}
												disabled={runsLoadingMore}
											>
												{runsLoadingMore ? 'Loading…' : 'Load more'}
											</button>
										{/if}
									</div>
								{/if}
							</div>
						{:else if activeTab === 'files'}
							<RunArtifactsPanel
								token={token}
								title="Run artifacts"
								emptyMessage="Generate a run to browse its output artifacts."
							/>
						{:else if activeTab === 'configs'}
							<section class="space-y-4">
								<div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
									<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Project configs</h3>
									<div class="flex items-center gap-2 text-xs text-slate-400">
										<span>{projectConfigs.length} config(s)</span>
										<button
											type="button"
											class="rounded-xl border border-slate-200 px-3 py-1 font-semibold text-slate-500 transition hover:bg-slate-50"
											onclick={handleReloadConfigs}
											disabled={configsLoading}
										>
											{configsLoading ? 'Reloading…' : 'Reload'}
										</button>
										<button
											type="button"
											class="rounded-xl border border-slate-200 px-3 py-1 font-semibold text-slate-500 transition hover:bg-slate-50"
											onclick={resetConfigForm}
										>
											New config
										</button>
									</div>
								</div>
								{#if configsError}
									<p class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-700">{configsError}</p>
								{/if}
								<div class="grid gap-6 lg:grid-cols-[minmax(0,0.55fr)_minmax(0,1fr)]">
									<section class="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
										{#if configsLoading && !projectConfigs.length}
											<p class="text-sm text-slate-500">Loading configs…</p>
										{:else if !projectConfigs.length}
											<p class="text-sm text-slate-500">No configs yet. Use the form to create one.</p>
										{:else}
											<ul class="space-y-3 text-sm text-slate-600">
												{#each projectConfigs as config (config.id)}
													<li class="rounded-2xl border border-slate-200 px-4 py-3">
														<div class="flex items-start justify-between gap-3">
															<div>
																<p class="text-base font-semibold text-slate-700">{config.name}</p>
																<p class="text-xs text-slate-400">
																	{config.kind} ·
																	{config.config_name ? `references ${config.config_name}` : 'inline payload'}
																</p>
																{#if config.description}
																	<p class="mt-1 text-xs text-slate-500">{config.description}</p>
																{/if}
																{#if config.tags.length}
																	<div class="mt-2 flex flex-wrap gap-1 text-[0.65rem] text-slate-500">
																		{#each config.tags as tag}
																			<span class="rounded-full border border-slate-200 px-2 py-[2px]">{tag}</span>
																		{/each}
																	</div>
																{/if}
															</div>
															<div class="flex flex-col items-end gap-1 text-xs text-slate-400">
																{#if config.is_default}
																	<span class="rounded-full border border-emerald-300 bg-emerald-50 px-2 py-[2px] text-emerald-600">
																		Default
																	</span>
																{/if}
																{#if config.updated_at}<span>{config.updated_at}</span>{/if}
															</div>
														</div>
														<div class="mt-3 flex flex-wrap gap-2 text-xs">
															<button
																type="button"
																class="rounded-xl border border-slate-200 px-3 py-1 font-semibold text-slate-500 transition hover:bg-slate-50"
																onclick={() => handleEditConfig(config)}
															>
																Edit
															</button>
															<button
																type="button"
																class="rounded-xl border border-slate-200 px-3 py-1 font-semibold text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
																onclick={() => handleSetDefaultConfig(config.id)}
																disabled={config.is_default}
															>
																Set default
															</button>
															<button
																type="button"
																class="rounded-xl border border-rose-200 px-3 py-1 font-semibold text-rose-600 transition hover:bg-rose-50"
																onclick={() => handleDeleteConfig(config.id)}
															>
																Delete
															</button>
														</div>
													</li>
												{/each}
											</ul>
										{/if}
									</section>
									<section class="rounded-2xl border border-slate-200 bg-white p-4">
										<h4 class="text-base font-semibold text-slate-700">
											{editingConfigId ? 'Edit config' : 'Create config'}
										</h4>
										<form class="mt-4 space-y-3 text-sm text-slate-600" onsubmit={handleConfigSubmit}>
											<label class="block space-y-1">
												<span class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Name</span>
												<input
													class="w-full rounded-2xl border border-slate-200 px-3 py-2"
													type="text"
													bind:value={configNameInput}
													placeholder="production-baseline"
												/>
											</label>
											<label class="block space-y-1">
												<span class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Description</span>
												<textarea
													class="w-full rounded-2xl border border-slate-200 px-3 py-2"
													rows={2}
													bind:value={configDescriptionInput}
												></textarea>
											</label>
											<label class="block space-y-1">
												<span class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Kind</span>
												<input
													class="w-full rounded-2xl border border-slate-200 px-3 py-2"
													type="text"
													bind:value={configKindInput}
													placeholder="tfreview"
												/>
											</label>
											<label class="block space-y-1">
												<span class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Reference config</span>
												<input
													class="w-full rounded-2xl border border-slate-200 px-3 py-2"
													type="text"
													bind:value={configRefInput}
													placeholder="baseline"
												/>
											</label>
											<label class="block space-y-1">
												<span class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Inline payload</span>
												<textarea
													class="w-full rounded-2xl border border-slate-200 px-3 py-2 font-mono text-xs"
													rows={6}
													bind:value={configPayloadInput}
													placeholder="# thresholds:\n#   high: fail"
												></textarea>
											</label>
											<label class="block space-y-1">
												<span class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Tags</span>
												<input
													class="w-full rounded-2xl border border-slate-200 px-3 py-2"
													type="text"
													bind:value={configTagsInput}
													placeholder="prod, baseline"
												/>
											</label>
											<label class="block space-y-1">
												<span class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Metadata (JSON)</span>
												<textarea
													class="w-full rounded-2xl border border-slate-200 px-3 py-2 font-mono text-xs"
													rows={4}
													bind:value={configMetadataInput}
												></textarea>
											</label>
											<label class="flex items-center gap-2 text-xs text-slate-500">
												<input type="checkbox" bind:checked={configIsDefault} />
												Set as default config
											</label>
											{#if configFormError}
												<p class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-600">
													{configFormError}
												</p>
											{/if}
											<div class="flex items-center gap-2">
												<button
													type="submit"
													class="rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-sky-200 transition hover:bg-sky-600 disabled:opacity-60"
													disabled={configFormBusy}
												>
													{configFormBusy ? 'Saving…' : editingConfigId ? 'Update config' : 'Create config'}
												</button>
												{#if editingConfigId}
													<button
														type="button"
														class="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-50"
														onclick={resetConfigForm}
														disabled={configFormBusy}
													>
														Cancel
													</button>
												{/if}
											</div>
										</form>
									</section>
								</div>
							</section>
						{:else if activeTab === 'artifacts'}
							<section class="space-y-4">
								<div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
									<div>
										<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Project artifacts</h3>
										<p class="text-xs text-slate-500">Metadata for run outputs promoted into the workspace.</p>
									</div>
									<div class="flex flex-wrap items-center gap-2 text-xs text-slate-500">
										<select
											class="rounded-xl border border-slate-200 px-3 py-1 text-sm text-slate-600"
											bind:value={artifactRunFilter}
										>
											<option value="">All runs</option>
											{#each projectRuns as run (run.id)}
												<option value={run.id}>{run.label}</option>
											{/each}
										</select>
										<button
											type="button"
											class="rounded-xl border border-slate-200 px-3 py-1 font-semibold text-slate-500 transition hover:bg-slate-50"
											onclick={handleReloadArtifactsIndex}
											disabled={artifactTableLoading}
										>
											{artifactTableLoading ? 'Reloading…' : 'Reload'}
										</button>
										<button
											type="button"
											class="rounded-xl border border-slate-200 px-3 py-1 font-semibold text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
											onclick={handleSyncArtifacts}
											disabled={!artifactRunFilter || artifactSyncBusy}
										>
											{artifactSyncBusy ? 'Syncing…' : 'Sync run'}
										</button>
									</div>
								</div>
								{#if artifactTableError}
									<p class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-600">
										{artifactTableError}
									</p>
								{:else}
									<div class="grid gap-4 lg:grid-cols-[3fr,2fr]">
										<div class="space-y-4">
											{#if artifactTableLoading && !projectArtifacts.length}
												<p class="text-sm text-slate-500">Loading artifacts…</p>
											{:else if !projectArtifacts.length}
												<p class="text-sm text-slate-500">No artifacts indexed yet. Promote a run to populate this table.</p>
											{:else}
												<div class="overflow-hidden rounded-2xl border border-slate-200 bg-white">
													<table class="w-full text-sm text-slate-600">
														<thead class="bg-slate-50 text-xs uppercase tracking-[0.3em] text-slate-400">
															<tr>
																<th class="px-4 py-3 text-left">Artifact</th>
																<th class="px-4 py-3 text-left">Details</th>
																<th class="px-4 py-3 text-left">Actions</th>
															</tr>
														</thead>
														<tbody>
															{#each projectArtifacts as artifact (artifact.id)}
																<tr class="border-t border-slate-100">
																	<td class="px-4 py-3 align-top">
																		<p class="font-semibold text-slate-700">{artifact.name}</p>
																		<p class="text-xs uppercase tracking-[0.2em] text-slate-400">
																			Run: {artifact.run_id ?? 'manual'}
																		</p>
																	</td>
																	<td class="px-4 py-3 align-top">
																		<div class="space-y-1 text-xs text-slate-500">
																			<p class="font-mono text-[0.7rem] text-slate-600">{artifact.relative_path}</p>
																			{#if artifact.media_type}
																				<p>{artifact.media_type}</p>
																			{/if}
																			{#if artifact.tags.length}
																				<div class="flex flex-wrap gap-1">
																					{#each artifact.tags as tag}
																						<span class="rounded-full border border-slate-200 px-2 py-[1px] text-[0.65rem] uppercase tracking-[0.3em] text-slate-400">
																							{tag}
																						</span>
																					{/each}
																				</div>
																			{/if}
																			{#if artifact.created_at}
																				<p>Uploaded {artifact.created_at}</p>
																			{/if}
																		</div>
																	</td>
																	<td class="px-4 py-3 align-top">
																		<div class="flex flex-col gap-2 text-xs">
																			<button
																				type="button"
																				class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-3 py-1 font-semibold text-slate-500 transition hover:bg-slate-50"
																				onclick={() => handleEditArtifactMetadata(artifact)}
																			>
																				Edit metadata
																			</button>
																		</div>
																	</td>
																</tr>
															{/each}
														</tbody>
													</table>
												</div>
												<div class="flex flex-col gap-2 text-xs text-slate-400 md:flex-row md:items-center md:justify-between">
													<span>
														Showing {projectArtifacts.length} of {artifactIndexCache?.totalCount ?? projectArtifacts.length} artifact(s)
													</span>
													{#if artifactIndexCache?.nextCursor}
														<button
															type="button"
															class={`inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 font-semibold text-slate-500 transition hover:bg-slate-50 ${
																artifactTableLoading ? 'cursor-wait opacity-60' : ''
															}`}
															onclick={handleLoadMoreProjectArtifacts}
															disabled={artifactTableLoading}
														>
															{artifactTableLoading ? 'Loading…' : 'Load more'}
														</button>
													{/if}
												</div>
											{/if}
										</div>
										<div class="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
											<div>
												<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Edit artifact metadata</h4>
												{#if artifactEditTarget}
													<p class="text-sm text-slate-500">
														Updating <span class="font-semibold text-slate-700">{artifactEditTarget.name}</span>
													</p>
												{:else}
													<p class="text-sm text-slate-500">Select an artifact to edit its tags and metadata.</p>
												{/if}
											</div>
											<form class="space-y-3" onsubmit={handleArtifactMetadataSubmit}>
												<label class="block space-y-1 text-xs text-slate-500">
													<span class="font-semibold uppercase tracking-[0.3em] text-slate-400">Tags (comma separated)</span>
													<input
														class="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm text-slate-700"
														type="text"
														bind:value={artifactTagsInput}
														placeholder="prod,release"
														disabled={!artifactEditTarget || artifactEditBusy}
													/>
												</label>
												<label class="block space-y-1 text-xs text-slate-500">
													<span class="font-semibold uppercase tracking-[0.3em] text-slate-400">Media type</span>
													<input
														class="w-full rounded-2xl border border-slate-200 px-3 py-2 text-sm text-slate-700"
														type="text"
														bind:value={artifactMediaTypeInput}
														placeholder="application/json"
														disabled={!artifactEditTarget || artifactEditBusy}
													/>
												</label>
												<label class="block space-y-1 text-xs text-slate-500">
													<span class="font-semibold uppercase tracking-[0.3em] text-slate-400">Metadata (JSON)</span>
													<textarea
														class="w-full rounded-2xl border border-slate-200 px-3 py-2 font-mono text-xs text-slate-700"
														rows={6}
														bind:value={artifactMetadataInput}
														disabled={!artifactEditTarget || artifactEditBusy}
													></textarea>
												</label>
												{#if artifactEditError}
													<p class="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600">
														{artifactEditError}
													</p>
												{/if}
												<div class="flex flex-wrap items-center gap-2 text-sm">
													<button
														type="submit"
														class="rounded-xl bg-sky-500 px-4 py-2 font-semibold text-white shadow-sm shadow-sky-200 transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
														disabled={!artifactEditTarget || artifactEditBusy}
													>
														{artifactEditBusy ? 'Saving…' : 'Save metadata'}
													</button>
													<button
														type="button"
														class="rounded-xl border border-slate-200 px-4 py-2 font-semibold text-slate-500 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
														onclick={resetArtifactEdit}
														disabled={artifactEditBusy || !artifactEditTarget}
													>
														Clear selection
													</button>
												</div>
											</form>
										</div>
									</div>
								{/if}
							</section>
						{:else if activeTab === 'library'}
							<section class="space-y-4">
								<div class="flex items-center justify-between">
					<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Library assets</h3>
					<div class="flex flex-col gap-2 text-xs text-slate-400 lg:flex-row lg:items-center">
						<span>
							Showing {filteredLibraryAssets.length} of {libraryCache?.totalCount ?? libraryAssets.length} asset(s)
						</span>
						<div class="flex flex-col gap-1 text-[0.65rem] uppercase tracking-[0.3em] text-slate-400">
							<span>Types</span>
							<div class="flex flex-wrap gap-2">
								{#each libraryTypeOptions as type (type)}
									<button
										type="button"
										class={`rounded-full border px-3 py-1 text-[0.65rem] font-semibold transition ${
											libraryTypeFilter === type
												? 'border-sky-400 bg-sky-50 text-sky-600 shadow-sky-100'
												: 'border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-600'
										}`}
										onclick={() => setLibraryTypeFilterValue(type)}
									>
										{formatAssetTypeLabel(type)}
									</button>
								{/each}
							</div>
						</div>
						{#if libraryGeneratorTags.length}
							<div class="flex flex-col gap-1 text-[0.65rem] uppercase tracking-[0.3em] text-slate-400">
								<span>Generators</span>
								<div class="flex flex-wrap gap-2">
									{#each ['all', ...libraryGeneratorTags] as slug (slug)}
										<button
											type="button"
											class={`rounded-full border px-3 py-1 text-[0.65rem] font-semibold transition ${
												libraryGeneratorFilter === slug
													? 'border-violet-400 bg-violet-50 text-violet-600 shadow-violet-100'
													: 'border-slate-200 text-slate-500 hover:border-slate-300 hover:text-slate-600'
											}`}
											onclick={() =>
												slug === 'all' ? (libraryGeneratorFilter = 'all') : toggleLibraryGeneratorFilter(slug)}
										>
											{formatGeneratorLabel(slug)}
										</button>
									{/each}
								</div>
							</div>
						{/if}
						{#if libraryCache?.nextCursor}
							<button
								type="button"
												class={`inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-[6px] font-semibold text-slate-500 transition hover:bg-slate-50 ${
													libraryLoadingMore ? 'cursor-wait opacity-60' : ''
												}`}
												onclick={handleLoadMoreLibrary}
												disabled={libraryLoadingMore}
											>
												{libraryLoadingMore ? 'Loading…' : 'Load more'}
											</button>
										{/if}
									</div>
								</div>

					{#if libraryError}
						<div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-600">
							{libraryError}
						</div>
					{:else if libraryLoading && !libraryAssets.length}
						<p class="text-sm text-slate-500">Loading project library…</p>
					{:else if libraryAssets.length}
						{#if filteredLibraryAssets.length}
							<ul class="space-y-3">
								{#each filteredLibraryAssets as asset (asset.id)}
											<li class="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
												<div class="flex flex-wrap items-start justify-between gap-3">
													<div>
														<p class="text-base font-semibold text-slate-700">{asset.name}</p>
														<p class="text-xs uppercase tracking-[0.25em] text-slate-400">{asset.asset_type}</p>
													</div>
													<div class="flex flex-wrap items-center gap-2 text-xs text-slate-500">
														<button
															type="button"
															class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100"
															onclick={() => openEditAsset(asset)}
														>
															Edit
														</button>
														<button
															type="button"
															class="inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-white px-3 py-1 text-[0.65rem] font-semibold text-rose-500 transition hover:bg-rose-500 hover:text-white"
															onclick={() => handleDeleteAsset(asset.id)}
															disabled={libraryLoading}
														>
															Delete
														</button>
													</div>
												</div>
												{#if asset.description}
													<p class="text-xs text-slate-500">{asset.description}</p>
												{/if}
												{#if asset.metadata && Object.keys(asset.metadata).length}
													<details class="text-xs text-slate-500">
														<summary class="cursor-pointer font-semibold">Metadata</summary>
														<pre class="mt-2 overflow-auto rounded-xl border border-slate-200 bg-white p-3 font-mono text-[0.7rem] text-slate-600">
{JSON.stringify(asset.metadata, null, 2)}</pre>
													</details>
												{/if}
												<div class="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
													<p class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
														Versions ({asset.versions?.length ?? 0})
													</p>
												{#if asset.versions && asset.versions.length}
													<ul class="space-y-2 text-xs text-slate-600">
														{#each asset.versions as version, versionIndex (version.id)}
															{@const previousVersion = asset.versions ? asset.versions[versionIndex + 1] ?? null : null}
															{@const manifestEntry = getVersionFileEntry(asset.id, version.id)}
															<li class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
																<div class="space-y-1">
																	<span class="font-mono text-[0.7rem] text-slate-600">{version.display_path}</span>
																	<div class="flex items-center gap-2">
																		{#if version.created_at}
																				<span class="rounded-full border border-slate-200 bg-white px-2 py-[1px] text-[0.6rem] uppercase tracking-[0.3em] text-slate-400">
																					{version.created_at}
																				</span>
																			{/if}
																		{#if asset.latest_version_id === version.id}
																			<span class="rounded-full border border-sky-200 bg-sky-50 px-2 py-[1px] text-[0.6rem] font-semibold uppercase tracking-[0.3em] text-sky-500">
																				Latest
																			</span>
																		{/if}
																		{#if version.validation_summary}
																			{@const validationStatus = validationStatusLabel(version.validation_summary)}
																			<span class={`rounded-full border px-2 py-[1px] text-[0.6rem] font-semibold uppercase tracking-[0.3em] ${validationStatusClass(validationStatus)}`}>
																				Validation {validationStatus}
																			</span>
																		{/if}
																	</div>
																	{#if version.metadata && Object.keys(version.metadata).length}
																		<details class="text-[0.65rem] text-slate-500">
																			<summary class="cursor-pointer font-semibold">Version metadata</summary>
																			<pre class="mt-2 overflow-auto rounded-xl border border-slate-200 bg-white p-2 font-mono">
{JSON.stringify(version.metadata, null, 2)}</pre>
																		</details>
																	{/if}
																</div>
																<div class="flex flex-wrap items-center gap-2">
																	<button
																		type="button"
																		class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100"
																		onclick={() => void handleDownloadVersion(asset.id, version)}
																	>
																		Download
																	</button>
																	<button
																		type="button"
																		class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100"
																		onclick={() => void toggleVersionFiles(asset, version)}
																		disabled={manifestEntry.loading}
																	>
																		{manifestEntry.expanded ? 'Hide files' : manifestEntry.items.length ? `Files (${manifestEntry.items.length})` : 'View files'}
																	</button>
																	<button
																		type="button"
																		class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
																		onclick={() => {
																			void handleDiffVersion(asset, version, previousVersion?.id ?? null, {
																					ignoreWhitespace: diffState?.ignoreWhitespace ?? false
																				});
																				activeTab = 'library';
																			}}
																			disabled={!previousVersion || (diffState?.loading && diffState.assetId === asset.id && diffState.versionId === version.id)}
																		>
																			Diff prev
																		</button>
																	</div>
																</li>
															{#if manifestEntry.expanded}
																<li class="rounded-lg border border-slate-200 bg-white px-3 py-2">
																	{#if manifestEntry.loading}
																		<p class="text-[0.65rem] text-slate-500">Loading files…</p>
																	{:else if manifestEntry.error}
																		<p class="text-[0.65rem] text-rose-500">{manifestEntry.error}</p>
																	{:else if manifestEntry.items.length}
																		<div class="overflow-auto rounded-xl border border-slate-100">
																			<table class="min-w-full text-[0.65rem] text-left text-slate-600">
																				<thead class="bg-slate-50 text-[0.6rem] uppercase tracking-[0.25em] text-slate-400">
																					<tr>
																						<th class="px-3 py-2">Path</th>
																						<th class="px-3 py-2">Size</th>
																						<th class="px-3 py-2">Media</th>
																						<th class="px-3 py-2">Checksum</th>
																					</tr>
																				</thead>
																				<tbody>
																					{#each manifestEntry.items as file}
																						<tr class="odd:bg-white even:bg-slate-50">
																							<td class="px-3 py-2 font-mono">{file.path}</td>
																							<td class="px-3 py-2">{formatBytes(file.size_bytes ?? null)}</td>
																							<td class="px-3 py-2">{file.media_type ?? '—'}</td>
																							<td class="px-3 py-2 font-mono">{file.checksum ?? '—'}</td>
																						</tr>
																					{/each}
																				</tbody>
																			</table>
																		</div>
																	{:else}
																		<p class="text-[0.65rem] text-slate-500">No files were recorded for this version.</p>
																	{/if}
																</li>
															{/if}
														{#if diffState && diffState.assetId === asset.id && diffState.versionId === version.id}
															{@const currentDiff = getCurrentDiffText()}
															{@const selectedEntry = getSelectedDiffEntry()}
															<li class="space-y-2 rounded-lg border border-slate-200 bg-white px-3 py-3 text-xs text-slate-600">
																<div class="flex flex-wrap items-center justify-between gap-2">
																			<p class="font-semibold uppercase tracking-[0.25em] text-slate-400">
																				Diff vs {diffState.againstVersionId}
																			</p>
																			<div class="flex flex-wrap items-center gap-2">
																				<button
																					type="button"
																					class="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-2 py-1 text-[0.65rem] font-semibold transition hover:bg-slate-100"
																					class:bg-sky-500={diffLayout === 'unified'}
																					class:text-white={diffLayout === 'unified'}
																					class:border-sky-500={diffLayout === 'unified'}
																					onclick={() => setDiffLayout('unified')}
																					disabled={diffState.loading}
																				>
																					Unified
																				</button>
																				<button
																					type="button"
																					class="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-2 py-1 text-[0.65rem] font-semibold transition hover:bg-slate-100"
																					class:bg-sky-500={diffLayout === 'split'}
																					class:text-white={diffLayout === 'split'}
																					class:border-sky-500={diffLayout === 'split'}
																					onclick={() => setDiffLayout('split')}
																					disabled={diffState.loading}
																				>
																					Split view
																				</button>
																				<button
																					type="button"
																					class="inline-flex items-center gap-1 rounded-xl border px-2 py-1 text-[0.65rem] font-semibold transition"
																					class:border-emerald-500={diffState.ignoreWhitespace}
																					class:bg-emerald-500={diffState.ignoreWhitespace}
																					class:text-white={diffState.ignoreWhitespace}
																					class:border-slate-200={!diffState.ignoreWhitespace}
																					class:bg-slate-50={!diffState.ignoreWhitespace}
																					class:text-slate-500={!diffState.ignoreWhitespace}
																					onclick={toggleIgnoreWhitespace}
																					disabled={diffState.loading}
																				>
																					Ignore whitespace
																				</button>
																				<button
																					type="button"
																					class="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-2 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100"
																					onclick={handleCopyDiff}
																					disabled={!currentDiff}
																				>
																					Copy
																				</button>
																				<button
																					type="button"
																					class="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-2 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100"
																					onclick={handleDownloadDiffText}
																					disabled={!currentDiff}
																				>
																					Download
																				</button>
																				<button
																					type="button"
																					class="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-2 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100"
																					onclick={handleCloseDiff}
																				>
																					Close
																				</button>
																			</div>
																		</div>
																		{#if diffState.files.length}
																			<div class="space-y-2 rounded-xl border border-slate-100 bg-slate-50 p-2">
																				<p class="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-slate-400">
																					Files ({diffState.files.length})
																				</p>
																				<div class="flex flex-wrap gap-2">
																					{#each diffState.files as file}
																						<button
																							type="button"
																							class={`rounded-xl border px-2 py-1 text-[0.65rem] font-semibold transition ${diffFileStatusClass(file.status)}`}
																							class:border-sky-500={diffState.selectedPath === file.path}
																							class:bg-sky-50={diffState.selectedPath === file.path}
																							onclick={() => selectDiffFile(file.path)}
																							disabled={diffState.loading}
																						>
																							<span class="font-mono">{file.path}</span>
																							<span class="ml-2 uppercase tracking-[0.15em]">{file.status}</span>
																						</button>
																					{/each}
																				</div>
																				{#if selectedEntry}
																					<p class="text-[0.6rem] text-slate-500">
																						Base: {formatBytes(selectedEntry.base?.size_bytes ?? null)} · Compare:
																						{formatBytes(selectedEntry.compare?.size_bytes ?? null)}
																					</p>
																				{/if}
																			</div>
																		{/if}
																		{#if diffState.loading}
																			<p class="text-slate-500">Computing diff…</p>
																		{:else if diffState.error}
																			<p class="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-rose-500">
																				{diffState.error}
																			</p>
																		{:else if currentDiff}
																			{#if diffLayout === 'unified'}
																				<pre class="overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[0.7rem] text-slate-600">
{currentDiff}</pre>
																			{:else}
																				<div class="grid grid-cols-2 gap-1 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[0.7rem] text-slate-600">
																					{#each buildSplitRows(currentDiff) as row, idx (idx)}
																						<div class={`whitespace-pre-wrap ${row.type === 'added' ? 'bg-emerald-100' : row.type === 'removed' ? 'bg-rose-100' : ''}`}>
																							{row.left}
																						</div>
																						<div class={`whitespace-pre-wrap ${row.type === 'added' ? 'bg-emerald-100' : row.type === 'removed' ? 'bg-rose-100' : ''}`}>
																							{row.right}
																						</div>
																					{/each}
																				</div>
																			{/if}
																		{:else}
																			<p class="text-xs text-slate-500">Diff returned no content.</p>
																		{/if}
																	</li>
																{/if}
															{/each}
														</ul>
													{:else}
														<p class="text-xs text-slate-500">No versions recorded.</p>
													{/if}
												</div>
											</li>
								{/each}
							</ul>
						{:else}
							<p class="text-sm text-slate-500">No assets match the current filter.</p>
						{/if}
					{:else}
						<p class="text-sm text-slate-500">
							No library assets yet. Promote artifacts from recent runs to build a reusable library.
						</p>
					{/if}
							</section>
						{:else if activeTab === 'settings'}
							<section class="space-y-4">
								<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
									<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Project details</h3>
									<div class="mt-4 grid gap-4 md:grid-cols-2">
										<div class="space-y-3">
											<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="project-name">
												Name
											</label>
											<input
												id="project-name"
												type="text"
												class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
												bind:value={editName}
											/>
										</div>
										<div class="space-y-3">
											<label
												class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400"
												for="project-description"
											>
												Description
											</label>
											<textarea
												id="project-description"
												class="h-24 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
												bind:value={editDescription}
											></textarea>
										</div>
									</div>
									<div class="mt-4 space-y-3">
										<div class="flex items-center justify-between">
											<label
												class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400"
												for="project-metadata"
											>
												Metadata (JSON)
											</label>
											<button
												type="button"
												class="text-xs font-semibold text-slate-500"
												onclick={() => {
													metadataExpanded = !metadataExpanded;
												}}
											>
												{metadataExpanded ? 'Collapse' : 'Expand'}
											</button>
										</div>
										<textarea
											id="project-metadata"
											class={`w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200 ${
												metadataExpanded ? 'h-64' : 'h-32'
											}`}
											bind:value={editMetadata}
										></textarea>
										{#if editError}
											<p class="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-600">{editError}</p>
										{/if}
										<div class="flex flex-wrap items-center gap-3">
											<button
												type="button"
												class="inline-flex items-center justify-center rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-sky-200 transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
												onclick={handleUpdate}
												disabled={updateBusy}
											>
												{#if updateBusy}
													<span class="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
												{/if}
												Save changes
											</button>
											<button
												type="button"
												class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-50"
												onclick={() => {
													const project = $activeProject as ProjectDetail | null;
													if (!project) return;
													editName = project.name;
													editDescription = project.description ?? '';
													try {
														editMetadata = JSON.stringify(project.metadata ?? {}, null, 2);
													} catch {
														editMetadata = '{\n\n}';
													}
												}}
											>
												Revert
											</button>
										</div>
									</div>
								</div>

								<div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-600">
									<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-rose-500">Danger zone</h3>
									<p class="mt-2 text-sm text-rose-600">
										Deleting a project removes its runs and library metadata. Optionally remove files from disk as well.
									</p>
									<label class="mt-3 inline-flex items-center gap-2 text-xs text-rose-500">
										<input
											type="checkbox"
											class="h-4 w-4 rounded border-rose-300 text-rose-500 focus:ring-rose-200"
											bind:checked={removeFiles}
										/>
										<span>Remove project files from disk</span>
									</label>
									<button
										type="button"
										class="mt-3 inline-flex items-center justify-center rounded-xl border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
										onclick={handleDelete}
										disabled={deleteBusy}
									>
										{#if deleteBusy}
											<span class="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
										{/if}
										Delete project
									</button>
								</div>
							</section>
						{/if}
					</div>
				</section>
			{:else}
				<div class="rounded-3xl border border-slate-200 bg-white px-6 py-6 text-sm text-slate-500 shadow-sm shadow-slate-200">
					Select a project from the list to inspect runs, artifacts, and library assets.
				</div>
			{/if}
		</main>
	</div>
</section>

{#if createModalOpen}
	<div class="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
		<button
			type="button"
			class="absolute inset-0 bg-slate-900/60"
			onclick={() => {
				if (!createBusy) {
					createModalOpen = false;
				}
			}}
			aria-label="Close create project modal"
		></button>
		<form
			class="relative w-full max-w-lg space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-900/20"
			onsubmit={handleCreate}
		>
			<div class="flex items-start justify-between gap-4">
				<div>
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Create project</p>
					<p class="mt-1 text-sm text-slate-600">Provision a new workspace for TerraformManager runs.</p>
				</div>
				<button
					type="button"
					class="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-500"
					onclick={() => {
						if (!createBusy) {
							createModalOpen = false;
						}
					}}
					aria-label="Close create project dialog"
				>
					Close
				</button>
			</div>
			<div class="grid gap-4">
				<div>
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="create-name">Name</label>
					<input
						id="create-name"
						type="text"
						class="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						bind:value={createName}
						placeholder="Platform workspace"
					/>
				</div>
				<div>
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="create-description">
						Description
					</label>
					<textarea
						id="create-description"
						class="mt-1 h-20 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						bind:value={createDescription}
						placeholder="Optional context"
					></textarea>
				</div>
				<div>
					<div class="flex items-center justify-between">
						<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="create-metadata">
							Metadata (JSON)
						</label>
						<button
							type="button"
							class="text-xs font-semibold text-sky-600"
							onclick={() => {
								createMetadata = '{\n\t"owner": "platform"\n}';
							}}
						>
							Reset
						</button>
					</div>
					<textarea
						id="create-metadata"
						class="mt-1 h-32 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						bind:value={createMetadata}
					></textarea>
				</div>
				{#if createError}
					<p class="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-600">{createError}</p>
				{/if}
			</div>
			<div class="flex justify-end">
				<button
					type="submit"
					class="inline-flex items-center justify-center rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-sky-200 transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
					disabled={createBusy}
				>
					{#if createBusy}
						<span class="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
					{/if}
					Create project
				</button>
			</div>
		</form>
	</div>
{/if}

{#if editAssetTarget}
	<div class="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
		<button
			type="button"
			class="absolute inset-0 bg-slate-900/60"
			onclick={closeEditAsset}
			aria-label="Close edit asset modal"
		></button>
		<div class="relative w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-900/20" role="dialog" aria-modal="true">
			<div class="flex items-start justify-between gap-4">
				<div>
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Edit asset</p>
					<p class="mt-1 text-sm text-slate-600">{editAssetTarget.name}</p>
				</div>
				<button
					type="button"
					class="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-500"
					onclick={closeEditAsset}
					aria-label="Close edit asset dialog"
				>
					Close
				</button>
			</div>
			<form class="mt-4 space-y-4 text-sm" onsubmit={handleEditAssetSubmit}>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="edit-asset-name">
						Asset name
					</label>
					<input
						id="edit-asset-name"
						class="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						type="text"
						bind:value={editAssetName}
						required
					/>
				</div>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="edit-asset-type">
						Asset type
					</label>
					<input
						id="edit-asset-type"
						class="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						type="text"
						bind:value={editAssetType}
						required
					/>
				</div>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="edit-asset-tags">
						Tags
					</label>
					<input
						id="edit-asset-tags"
						class="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						type="text"
						placeholder="baseline, production"
						bind:value={editAssetTags}
					/>
					<p class="text-xs text-slate-400">Separate with commas.</p>
				</div>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="edit-asset-description">
						Description
					</label>
					<textarea
						id="edit-asset-description"
						class="h-20 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						bind:value={editAssetDescription}
					></textarea>
				</div>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="edit-asset-metadata">
						Metadata (JSON)
					</label>
					<textarea
						id="edit-asset-metadata"
						class="h-24 rounded-xl border border-slate-200 px-3 py-2 font-mono text-[0.75rem] text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						bind:value={editAssetMetadata}
					></textarea>
				</div>
				{#if editAssetError}
					<p class="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600">{editAssetError}</p>
				{/if}
				<div class="flex flex-wrap items-center justify-end gap-2 pt-2">
					<button
						type="button"
						class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
						onclick={closeEditAsset}
						disabled={editAssetSubmitting}
					>
						Cancel
					</button>
					<button
						type="submit"
						class="inline-flex items-center gap-2 rounded-xl border border-sky-500 bg-sky-500 px-4 py-2 text-xs font-semibold text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
						disabled={editAssetSubmitting}
					>
						{#if editAssetSubmitting}
							<span class="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
						{/if}
						Save changes
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
