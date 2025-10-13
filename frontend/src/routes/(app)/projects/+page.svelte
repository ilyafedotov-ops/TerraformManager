<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import RunArtifactsPanel from '$lib/components/projects/RunArtifactsPanel.svelte';
	import {
		type GeneratedAssetSummary,
		type GeneratedAssetVersionSummary,
		type ProjectDetail,
		type ProjectRunSummary,
		type ProjectSummary,
		type ProjectOverview,
		downloadProjectLibraryAssetVersion,
		diffProjectLibraryAssetVersions
	} from '$lib/api/client';
	import {
		projectState,
		activeProject,
		activeProjectRuns,
		activeProjectLibrary,
		activeProjectOverview
	} from '$lib/stores/project';
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

	type RunsCacheEntry = ReturnType<typeof projectState.getCachedRuns>;
	type LibraryCacheEntry = ReturnType<typeof projectState.getCachedLibrary>;

	const projects = $derived($projectState.projects as ProjectSummary[]);
	const activeProjectValue = $derived($activeProject as ProjectDetail | null);
	const projectRuns = $derived($activeProjectRuns as ProjectRunSummary[]);
	const libraryAssets = $derived($activeProjectLibrary as GeneratedAssetSummary[]);
	const overview = $derived($activeProjectOverview as ProjectOverview | null);

	const runCache = $derived(
		(): RunsCacheEntry =>
			activeProjectValue ? projectState.getCachedRuns(activeProjectValue.id) : null
	);
	const libraryCache = $derived(
		(): LibraryCacheEntry =>
			activeProjectValue ? projectState.getCachedLibrary(activeProjectValue.id) : null
	);

	let searchQuery = $state('');
	let activeTab = $state<'overview' | 'runs' | 'artifacts' | 'library' | 'settings'>('overview');
	let createModalOpen = $state(false);

	let createName = $state('');
	let createDescription = $state('');
	let createMetadata = $state('{\n\t"owner": "platform"\n}');
	let createError = $state<string | null>(null);
	let createBusy = $state(false);

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

	type DiffState = {
		assetId: string;
		versionId: string;
		againstVersionId: string;
		diff: string | null;
		error: string | null;
		loading: boolean;
		ignoreWhitespace: boolean;
	};

	let diffState = $state<DiffState | null>(null);
	let diffLayout = $state<'unified' | 'split'>('unified');

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

	const tabs: { id: typeof activeTab; label: string }[] = [
		{ id: 'overview', label: 'Overview' },
		{ id: 'runs', label: 'Runs' },
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
				error: message,
				loading: false
			};
		}
	};

	const handleCloseDiff = () => {
		diffState = null;
	};

	const handleCopyDiff = async () => {
		if (!diffState || !diffState.diff) {
			notifyError('No diff available to copy.');
			return;
		}
		if (!browser || !navigator.clipboard) {
			notifyError('Clipboard access is not available.');
			return;
		}
		try {
			await navigator.clipboard.writeText(diffState.diff);
			notifySuccess('Diff copied to clipboard.');
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to copy diff.';
			notifyError(message);
		}
	};

	const handleDownloadDiffText = () => {
		if (!diffState || !diffState.diff) {
			notifyError('No diff available to download.');
			return;
		}
		const blob = new Blob([diffState.diff], { type: 'text/plain;charset=utf-8' });
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

	const sortedProjects = $derived((): ProjectSummary[] => {
		const items = projects ?? [];
		const sorted = [...items].sort((a, b) =>
			(b.last_activity_at ?? '').localeCompare(a.last_activity_at ?? '')
		);
		return sorted.filter(matchesSearch);
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
								<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
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
									<section class="rounded-2xl border border-slate-200 bg-white px-4 py-4">
										<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Recent assets</h3>
										{#if overview.recent_assets.length}
											<ul class="mt-3 space-y-2 text-sm text-slate-600">
												{#each overview.recent_assets as asset (asset.id)}
													<li class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
														<div class="flex items-center justify-between gap-3">
															<div>
																<p class="font-semibold text-slate-700">{asset.name}</p>
																<p class="text-xs uppercase tracking-[0.25em] text-slate-400">{asset.asset_type}</p>
															</div>
															<span class="text-xs text-slate-400">{asset.updated_at}</span>
														</div>
														{#if asset.description}
															<p class="mt-2 text-xs text-slate-500">{asset.description}</p>
														{/if}
													</li>
												{/each}
											</ul>
										{:else}
											<p class="mt-3 text-sm text-slate-500">No promoted assets yet. Use the library tab to curate generated outputs.</p>
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
						{:else if activeTab === 'artifacts'}
							<RunArtifactsPanel
								token={token}
								title="Run artifacts"
								emptyMessage="Generate a run to browse its output artifacts."
							/>
						{:else if activeTab === 'library'}
							<section class="space-y-4">
								<div class="flex items-center justify-between">
									<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Library assets</h3>
									<div class="flex items-center gap-2 text-xs text-slate-400">
										<span>
											Showing {libraryAssets.length} of {libraryCache?.totalCount ?? libraryAssets.length} asset(s)
										</span>
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
									<ul class="space-y-3">
										{#each libraryAssets as asset (asset.id)}
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
																		</div>
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
																			class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
																			onclick={() => {
																				diffLayout = diffLayout;
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
																{#if diffState && diffState.assetId === asset.id && diffState.versionId === version.id}
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
																					disabled={!diffState.diff}
																				>
																					Copy
																				</button>
																				<button
																					type="button"
																					class="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-2 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100"
																					onclick={handleDownloadDiffText}
																					disabled={!diffState.diff}
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
																		{#if diffState.loading}
																			<p class="text-slate-500">Computing diff…</p>
																		{:else if diffState.error}
																			<p class="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-rose-500">
																				{diffState.error}
																			</p>
																		{:else if diffState.diff}
																			{#if diffLayout === 'unified'}
																				<pre class="overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[0.7rem] text-slate-600">
{diffState.diff}</pre>
																			{:else}
																				<div class="grid grid-cols-2 gap-1 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[0.7rem] text-slate-600">
																					{#each buildSplitRows(diffState.diff) as row, idx (idx)}
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
