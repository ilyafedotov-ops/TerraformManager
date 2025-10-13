<script lang="ts">
	import { browser } from '$app/environment';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
import { notifyError, notifySuccess } from '$lib/stores/notifications';
import { projectState, activeProject, activeProjectRuns, activeProjectLibrary } from '$lib/stores/project';
import RunArtifactsPanel from '$lib/components/projects/RunArtifactsPanel.svelte';
import {
	type GeneratedAssetSummary,
	type GeneratedAssetVersionSummary,
	type ProjectDetail,
	downloadProjectLibraryAssetVersion,
	diffProjectLibraryAssetVersions
} from '$lib/api/client';

	const { data } = $props();
	const token = data.token as string | null;
	const initialProjects = (data.projects ?? []) as ProjectDetail[];
	const loadError = data.error as string | undefined;

	if (initialProjects.length) {
		const stateSnapshot = get(projectState);
		if (!stateSnapshot.projects.length) {
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

let libraryLoading = $state(false);
let libraryError = $state<string | null>(null);
let diffState = $state<
	| {
		assetId: string;
		versionId: string;
		againstVersionId: string;
		diff: string | null;
		error: string | null;
		loading: boolean;
	}
	| null
>(null);

let metadataToggled = $state(false);

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

	const parseMetadata = (value: string) => {
		const trimmed = value.trim();
		if (!trimmed) {
			return {} as Record<string, unknown>;
		}
		return JSON.parse(trimmed) as Record<string, unknown>;
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

const runs = $derived($activeProjectRuns);
const projectList = $derived($projectState.projects);
const libraryAssets = $derived($activeProjectLibrary);

$effect(() => {
	const project = $activeProject as ProjectDetail | null;
	if (!token || !project) {
		libraryError = null;
		libraryLoading = false;
		return;
	}
	const cached = projectState.getCachedLibrary(project.id);
	if (cached && cached.includeVersions) {
		libraryError = null;
		libraryLoading = false;
		return;
	}
	libraryLoading = true;
	void projectState
		.loadLibrary(fetch, token, project.id, true)
		.then(() => {
			libraryError = null;
		})
		.catch((error) => {
			console.error('Failed to load library assets', error);
			libraryError = error instanceof Error ? error.message : 'Unable to load project library.';
		})
		.finally(() => {
			libraryLoading = false;
		});
});

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
	againstVersionId: string | null
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
			againstVersionId
		);
		diffState = {
			assetId: asset.id,
			versionId: version.id,
			againstVersionId,
			diff: payload.diff,
			error: null,
			loading: false
		};
	} catch (error) {
		const message = error instanceof Error ? error.message : 'Failed to generate diff.';
		diffState = {
			assetId: asset.id,
			versionId: version.id,
			againstVersionId,
			diff: null,
			error: message,
			loading: false
		};
	}
};

const handleCloseDiff = () => {
	diffState = null;
};
</script>

<section class="space-y-10">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Projects</p>
		<h2 class="text-3xl font-semibold text-slate-700">Manage workspaces</h2>
		<p class="max-w-3xl text-sm text-slate-500">
			Create, edit, and delete TerraformManager projects. Projects capture generator and review runs plus associated
			artifacts, enabling teams to collaborate without leaving the browser.
		</p>
		{#if loadError}
			<div class="rounded-3xl border border-amber-300 bg-amber-50 px-6 py-3 text-sm text-amber-700">
				{loadError}
			</div>
		{/if}
	</header>

	<section class="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm shadow-slate-200">
		<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Create project</h3>
		<form class="mt-4 grid gap-4 md:grid-cols-[minmax(0,360px)_1fr]" onsubmit={handleCreate}>
			<div class="space-y-3">
				<label class="block text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="create-name"
					>Name</label
				>
				<input
					id="create-name"
					type="text"
					class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
					bind:value={createName}
					placeholder="Platform workspace"
				/>
				<label
					class="block text-xs font-semibold uppercase tracking-[0.25em] text-slate-400"
					for="create-description">Description</label
				>
				<textarea
					id="create-description"
					class="h-24 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
					bind:value={createDescription}
					placeholder="Optional context"
				></textarea>
			</div>
			<div class="space-y-3">
				<div class="flex items-center justify-between">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="create-metadata"
						>Metadata (JSON)</label
					>
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
					class="h-40 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
					bind:value={createMetadata}
				></textarea>
				{#if createError}
					<p class="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-600">{createError}</p>
				{/if}
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
	</section>

	<section class="grid gap-6 lg:grid-cols-[320px_1fr]">
		<aside class="space-y-3">
			<div class="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200">
				<div class="flex items-center justify-between">
					<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Projects</h3>
					<button
						type="button"
						class="rounded-full border border-slate-200 px-2 py-[2px] text-[0.65rem] font-semibold uppercase tracking-[0.25em] text-slate-500 transition hover:bg-slate-100"
						onclick={() => {
							if (token) {
								void projectState.loadProjects(fetch, token).catch((error) => {
									console.error('Failed to reload projects', error);
									notifyError('Failed to reload projects');
								});
							}
						}}
					>
						Refresh
					</button>
				</div>
				{#if !projectList.length}
					<p class="mt-4 text-sm text-slate-500">
						No projects yet. Use the form above to create your first workspace.
					</p>
				{:else}
					<ul class="mt-3 space-y-2">
						{#each projectList as project (project.id)}
							<li>
								<button
									type="button"
									class={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left text-sm transition ${
										project.id === $activeProject?.id
											? 'border-sky-300 bg-sky-50 text-sky-600'
											: 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
									}`}
									onclick={() => projectState.setActiveProject(project.id)}
								>
									<span class="font-semibold">{project.name}</span>
									<span class="text-xs uppercase tracking-[0.2em] text-slate-400">{project.slug}</span>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
		</aside>

		<main class="space-y-6">
			{#if $activeProject}
				<section class="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm shadow-slate-200">
					<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Project details</h3>
					<div class="mt-4 space-y-4">
						<div class="grid gap-4 md:grid-cols-2">
							<div>
								<label
									class="block text-xs font-semibold uppercase tracking-[0.25em] text-slate-400"
									for="project-name">Name</label
								>
								<input
									id="project-name"
									type="text"
									class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
									bind:value={editName}
								/>
							</div>
							<div>
								<label
									class="block text-xs font-semibold uppercase tracking-[0.25em] text-slate-400"
									for="project-description">Description</label
								>
								<textarea
									id="project-description"
									class="h-24 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
									bind:value={editDescription}
								></textarea>
							</div>
						</div>
						<div>
							<div class="flex items-center justify-between">
								<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="project-metadata"
									>Metadata (JSON)</label
								>
								<button
									type="button"
									class="text-xs font-semibold text-slate-500"
									onclick={() => {
										metadataToggled = !metadataToggled;
									}}
								>
									{metadataToggled ? 'Hide' : 'Expand'}
								</button>
							</div>
							<textarea
								id="project-metadata"
								class={`w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200 ${metadataToggled ? 'h-64' : 'h-32'}`}
								bind:value={editMetadata}
							></textarea>
						</div>
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
							<div class="flex items-center gap-2 text-xs text-slate-500">
								<label class="inline-flex items-center gap-2">
									<input
										type="checkbox"
										class="h-4 w-4 rounded border-slate-300 text-rose-500 focus:ring-rose-200"
										bind:checked={removeFiles}
									/>
									<span>Remove files from disk</span>
								</label>
							</div>
							<button
								type="button"
								class="inline-flex items-center justify-center rounded-xl border border-rose-200 px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
								onclick={handleDelete}
								disabled={deleteBusy}
							>
								{#if deleteBusy}
									<span class="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
								{/if}
								Delete project
							</button>
						</div>
					</div>
				</section>

				<section class="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm shadow-slate-200">
					<div class="flex items-center justify-between">
						<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Run history</h3>
						<p class="text-xs text-slate-400">{runs.length} run(s)</p>
					</div>
					{#if runs.length}
						<ul class="mt-4 space-y-2">
							{#each runs as run (run.id)}
								<li class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
									<div class="flex flex-wrap items-center justify-between gap-2">
										<div>
											<p class="font-semibold text-slate-700">{run.label}</p>
											<p class="text-xs uppercase tracking-[0.2em] text-slate-400">{run.kind}</p>
										</div>
										<div class="flex items-center gap-2 text-xs text-slate-500">
											<span class="rounded-full border border-slate-200 px-3 py-[2px] font-semibold text-slate-600">{run.status}</span>
											{#if run.created_at}
												<span>{run.created_at}</span>
											{/if}
										</div>
									</div>
									{#if run.parameters}
										<details class="mt-2 text-xs text-slate-500">
											<summary class="cursor-pointer font-semibold">Parameters</summary>
											<pre class="mt-2 overflow-auto rounded-xl border border-slate-200 bg-white p-3 font-mono text-[0.7rem]">{JSON.stringify(run.parameters, null, 2)}</pre>
										</details>
									{/if}
									{#if run.summary}
										<details class="mt-2 text-xs text-slate-500">
											<summary class="cursor-pointer font-semibold">Summary</summary>
											<pre class="mt-2 overflow-auto rounded-xl border border-slate-200 bg-white p-3 font-mono text-[0.7rem]">{JSON.stringify(run.summary, null, 2)}</pre>
										</details>
									{/if}
								</li>
							{/each}
						</ul>
					{:else}
						<p class="mt-4 text-sm text-slate-500">No runs recorded for this project yet.</p>
					{/if}
				</section>

				<RunArtifactsPanel
					token={token}
					title="Project artifacts"
					emptyMessage="Select a project to manage artifacts for recent runs."
				/>

				<section class="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm shadow-slate-200">
					<div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
						<div>
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Library assets</p>
							<p class="text-sm text-slate-500">
								Persist promoted configs and generated files with full version history.
							</p>
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<button
								type="button"
								class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
								onclick={handleRefreshLibrary}
								disabled={libraryLoading || !token}
							>
								{#if libraryLoading}
									<span class="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
								{/if}
								Refresh
							</button>
						</div>
					</div>

					{#if libraryError}
						<div class="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-600">
							{libraryError}
						</div>
					{:else if libraryLoading && !libraryAssets.length}
						<p class="mt-4 text-sm text-slate-500">Loading project library…</p>
					{:else if libraryAssets.length}
						<ul class="mt-4 space-y-3">
							{#each libraryAssets as asset (asset.id)}
								<li class="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600">
									<div class="flex flex-wrap items-center justify-between gap-3">
										<div>
											<p class="text-base font-semibold text-slate-700">{asset.name}</p>
											<p class="text-xs uppercase tracking-[0.25em] text-slate-400">{asset.asset_type}</p>
										</div>
										<div class="flex items-center gap-2 text-xs text-slate-500">
											{#if asset.tags.length}
												<ul class="flex flex-wrap gap-1">
													{#each asset.tags as tag (tag)}
														<li class="rounded-full border border-slate-200 bg-white px-2 py-[1px] text-[0.6rem] font-semibold uppercase tracking-[0.3em] text-slate-400">
															{tag}
														</li>
													{/each}
												</ul>
											{/if}
											{#if asset.updated_at}
												<span class="rounded-full border border-slate-200 bg-white px-3 py-[1px] text-[0.65rem] text-slate-500">
													Updated {asset.updated_at}
												</span>
											{/if}
										</div>
									</div>
									{#if asset.description}
										<p class="text-xs text-slate-500">{asset.description}</p>
									{/if}
									{#if asset.metadata && Object.keys(asset.metadata).length}
										<details class="text-xs text-slate-500">
											<summary class="cursor-pointer font-semibold">Metadata</summary>
											<pre class="mt-2 overflow-auto rounded-xl border border-slate-200 bg-white p-3 font-mono text-[0.7rem] text-slate-600">{JSON.stringify(asset.metadata, null, 2)}</pre>
										</details>
									{/if}
									<div class="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
										<p class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">
											Versions ({asset.versions?.length ?? 0})
										</p>
										{#if asset.versions && asset.versions.length}
											<ul class="space-y-2 text-xs text-slate-600">
						{#each asset.versions as version, versionIndex (version.id)}
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
									{@const previousVersion = asset.versions ? asset.versions[versionIndex + 1] ?? null : null}
										<button
											type="button"
											class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-1 text-[0.65rem] font-semibold text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
											onclick={() => void handleDiffVersion(asset, version, previousVersion?.id ?? null)}
											disabled={!previousVersion || (diffState?.loading && diffState.assetId === asset.id && diffState.versionId === version.id)}
										>
											Diff prev
										</button>
									</div>
								</li>
								{#if diffState && diffState.assetId === asset.id && diffState.versionId === version.id}
									<li class="space-y-2 rounded-lg border border-slate-200 bg-white px-3 py-3 text-xs text-slate-600">
										<div class="flex items-center justify-between gap-2">
											<p class="font-semibold uppercase tracking-[0.25em] text-slate-400">Diff vs {diffState.againstVersionId}</p>
											<button
												type="button"
												class="rounded-xl border border-slate-200 bg-slate-50 px-2 py-1 text-[0.65rem] font-semibold text-slate-500"
												onclick={handleCloseDiff}
											>
												Close
											</button>
										</div>
										{#if diffState.loading}
											<p class="text-slate-400">Generating diff…</p>
										{:else if diffState.error}
											<p class="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-rose-600">{diffState.error}</p>
										{:else if diffState.diff}
											<pre class="max-h-64 overflow-auto rounded-xl border border-slate-200 bg-slate-900 p-3 font-mono text-[0.65rem] text-slate-100"><code>{diffState.diff}</code></pre>
										{:else}
											<p class="text-slate-400">No differences detected.</p>
										{/if}
									</li>
								{/if}
							{/each}
						</ul>
					{:else}
						<p class="text-xs text-slate-500">No versions recorded yet.</p>
					{/if}
									</div>
									<div class="flex flex-wrap gap-2">
										<button
											type="button"
											class="inline-flex items-center gap-2 rounded-xl border border-rose-200 px-3 py-1 text-xs font-semibold text-rose-600 transition hover:bg-rose-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
											onclick={() => void handleDeleteAsset(asset.id)}
											disabled={libraryLoading}
										>
											Delete asset
										</button>
									</div>
								</li>
							{/each}
						</ul>
					{:else}
						<p class="mt-4 text-sm text-slate-500">
							No library assets yet. Promote run artifacts to capture reusable configurations.
						</p>
					{/if}
				</section>
			{:else}
				<div class="rounded-3xl border border-slate-200 bg-white px-6 py-6 text-sm text-slate-500">
					Select a project to view configuration details.
				</div>
			{/if}
		</main>
	</section>
</section>
