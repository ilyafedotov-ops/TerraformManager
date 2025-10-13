<script lang="ts">
import { browser } from '$app/environment';
import { onMount } from 'svelte';
import { downloadRunArtifact, type ArtifactEntry } from '$lib/api/client';
import { notifyError, notifySuccess } from '$lib/stores/notifications';
import { activeProject, activeProjectRuns, activeProjectLibrary, projectState } from '$lib/stores/project';

interface Props {
	token: string | null;
	title?: string;
	emptyMessage?: string;
	highlightReportId?: string | null;
}

	const {
		token,
		title = 'Project artifacts',
		emptyMessage = 'Select a project to browse run artifacts.',
		highlightReportId = null
	}: Props = $props();

	let selectedRunId = $state<string | null>(null);
	let artifactPath = $state('.');
let artifacts = $state<ArtifactEntry[]>([]);
let artifactsLoading = $state(false);
let artifactsError = $state<string | null>(null);
let breadcrumbStack = $state<string[]>([]);
let runsLoading = $state(false);
let uploadFiles = $state<FileList | null>(null);
let uploadTarget = $state('');
let uploadOverwrite = $state(true);
let uploadBusy = $state(false);
let uploadError = $state<string | null>(null);
let deleteBusyPath = $state<string | null>(null);
let previewPath = $state<string | null>(null);
let previewContent = $state<string | null>(null);
let previewError = $state<string | null>(null);
let previewLoading = $state(false);
let previousRunId = $state<string | null>(null);
let previousContent = $state<string | null>(null);
let previousError = $state<string | null>(null);
let previousLoading = $state(false);
let promoteBusyPath = $state<string | null>(null);
let promoteTarget = $state<ArtifactEntry | null>(null);
let promoteName = $state('');
let promoteType = $state('terraform');
let promoteTags = $state('');
let promoteDescription = $state('');
let promoteNotes = $state('');
let promoteMetadata = $state('{\n\n}');
let promoteError = $state<string | null>(null);
let promoteSubmitting = $state(false);
let promotionPrefsLoaded = $state(false);
let showTagSuggestions = $state(false);

	const activeProjectValue = $derived($activeProject);
	const projectRuns = $derived($activeProjectRuns);
	const selectedRun = $derived(projectRuns.find((run) => run.id === selectedRunId) ?? null);
	const libraryAssets = $derived($activeProjectLibrary);
	const tagSuggestions = $derived(
		(() => {
			const tags = new Set<string>();
			for (const asset of libraryAssets) {
				for (const tag of asset.tags ?? []) {
					if (tag) {
						tags.add(tag);
					}
				}
			}
			return Array.from(tags).sort((a, b) => a.localeCompare(b));
		})()
	);

	const normalisePath = (value: string) => (value && value !== '.' ? value : '.');

	const PREFERENCE_KEY = 'tfm_promotion_defaults';

	const loadPromotionDefaults = (): {
		assetType?: string;
		tags?: string;
		metadata?: string;
		description?: string;
		notes?: string;
	} => {
		if (!browser) return {};
		try {
			const raw = window.localStorage.getItem(PREFERENCE_KEY);
			if (!raw) return {};
			const parsed = JSON.parse(raw);
			if (!parsed || typeof parsed !== 'object') return {};
			return parsed;
		} catch {
			return {};
		}
	};

	const storePromotionDefaults = (prefs: {
		assetType?: string;
		tags?: string;
		metadata?: string;
		description?: string;
		notes?: string;
	}) => {
		if (!browser) return;
		try {
			window.localStorage.setItem(PREFERENCE_KEY, JSON.stringify(prefs));
		} catch {
			// ignore storage errors
		}
	};

	onMount(() => {
		if (!promotionPrefsLoaded) {
			const defaults = loadPromotionDefaults();
			if (defaults.assetType) {
				promoteType = defaults.assetType;
			}
			if (defaults.tags) {
				promoteTags = defaults.tags;
			}
			if (defaults.metadata) {
				promoteMetadata = defaults.metadata;
			}
			if (defaults.description) {
				promoteDescription = defaults.description;
			}
			if (defaults.notes) {
				promoteNotes = defaults.notes;
			}
			promotionPrefsLoaded = true;
		}
	});

	const applyTagSuggestion = (tag: string) => {
		const existing = promoteTags
			.split(',')
			.map((value) => value.trim())
			.filter((value) => value.length > 0);
		if (!existing.includes(tag)) {
			existing.push(tag);
			promoteTags = existing.join(', ');
		}
	};

	const updateBreadcrumbs = (path: string) => {
		const normalised = normalisePath(path);
		if (normalised === '.') {
			breadcrumbStack = [];
			return;
		}
		const parts = normalised.split('/').filter(Boolean);
		breadcrumbStack = parts.map((_, idx) => parts.slice(0, idx + 1).join('/'));
	};

const applyArtifacts = (path: string, entries: ArtifactEntry[]) => {
	artifactPath = normalisePath(path);
	artifacts = entries;
	artifactsError = null;
	updateBreadcrumbs(artifactPath);
	uploadTarget = '';
	uploadError = null;
	if (previewPath && previewPath.startsWith(`${artifactPath}/`)) {
		// keep preview if still within the current directory
	} else {
		resetPreview();
	}
};

	const pendingLoads = new Set<string>();

	const loadArtifacts = async (path: string, runId: string, projectId: string) => {
		const targetPath = normalisePath(path);
		const loadKey = `${runId}::${targetPath}`;
		if (pendingLoads.has(loadKey)) {
			return;
		}
		if (!token) {
			artifacts = [];
			artifactsLoading = false;
			artifactsError = 'Missing API token – unable to load artifacts.';
			updateBreadcrumbs('.');
			return;
		}
		const cached = projectState.getCachedArtifacts(runId, targetPath);
		if (cached) {
			applyArtifacts(targetPath, cached.entries);
			return;
		}

		pendingLoads.add(loadKey);
		artifactsLoading = true;
		artifactsError = null;
		try {
			const entries = await projectState.loadArtifacts(fetch, token, projectId, runId, targetPath);
			applyArtifacts(targetPath, entries);
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to load run artifacts.';
			artifactsError = message;
			artifacts = [];
			updateBreadcrumbs('.');
		} finally {
			pendingLoads.delete(loadKey);
			artifactsLoading = false;
		}
	};

	const ensureRunsLoaded = async (projectId: string) => {
		if (!token || runsLoading) return;
		runsLoading = true;
		try {
			await projectState.refreshRuns(fetch, token, projectId, 20);
		} catch (error) {
			console.warn('Unable to refresh project runs', error);
		} finally {
			runsLoading = false;
		}
	};

const resetArtifacts = () => {
	artifactPath = '.';
	artifacts = [];
	artifactsError = null;
	updateBreadcrumbs('.');
	uploadFiles = null;
	uploadTarget = '';
	uploadError = null;
	deleteBusyPath = null;
	resetPreview();
};

	const selectRun = async (runId: string | null, path = '.') => {
		if (!activeProjectValue || !runId) {
			selectedRunId = null;
			resetArtifacts();
			return;
		}
		selectedRunId = runId;
		resetPreview();
		await loadArtifacts(path, runId, activeProjectValue.id);
	};

	$effect(() => {
		const project = $activeProject;
		const runs = $activeProjectRuns;

		if (!project) {
			selectedRunId = null;
			resetArtifacts();
			return;
		}

		if (!runs.length) {
			selectedRunId = null;
			resetArtifacts();
			void ensureRunsLoaded(project.id);
			return;
		}

		let highlightedRunId: string | null = null;
		if (highlightReportId) {
			const match = runs.find((run) => {
				const summary = run.summary as Record<string, unknown> | null | undefined;
				const savedId =
					summary && typeof summary === 'object'
						? (summary as { saved_report_id?: string | null }).saved_report_id
						: null;
				return savedId === highlightReportId;
			});
			highlightedRunId = match?.id ?? null;
		}

		const preferredRunId = highlightedRunId ?? selectedRunId;

		if (!preferredRunId || !runs.some((run) => run.id === preferredRunId)) {
			const nextId = highlightedRunId && runs.some((run) => run.id === highlightedRunId) ? highlightedRunId : runs[0]?.id ?? null;
			if (nextId) {
				void selectRun(nextId, '.');
			}
		} else {
			if (selectedRunId !== preferredRunId) {
				selectedRunId = preferredRunId;
			}
			const cached = projectState.getCachedArtifacts(preferredRunId, artifactPath);
			if (cached) {
				applyArtifacts(artifactPath, cached.entries);
			} else {
				void loadArtifacts(artifactPath, preferredRunId, project.id);
			}
		}
	});

	const handleRunChange = async (event: Event) => {
		const selectElement = event.target as HTMLSelectElement;
		const runId = selectElement.value || null;
		await selectRun(runId, '.');
	};

	const navigateToPath = async (path: string) => {
		if (!selectedRunId || !activeProjectValue) return;
		resetPreview();
		await loadArtifacts(path, selectedRunId, activeProjectValue.id);
	};

	const handleBreadcrumbClick = async (index: number) => {
		if (!selectedRunId || !activeProjectValue) return;
		if (index < 0) {
			await navigateToPath('.');
			return;
		}
		const target = breadcrumbStack[index];
		if (target) {
			await navigateToPath(target);
		}
	};

	const downloadArtifact = async (entry: ArtifactEntry) => {
		if (!token || !activeProjectValue || !selectedRunId) {
			notifyError('Missing project selection or authentication token.');
			return;
		}
		if (entry.is_dir) {
			await navigateToPath(entry.path);
			return;
		}
		try {
			const response = await downloadRunArtifact(fetch, token, activeProjectValue.id, selectedRunId, entry.path);
			const blob = await response.blob();
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement('a');
			anchor.href = url;
			anchor.download = entry.name || 'artifact';
			document.body.appendChild(anchor);
			anchor.click();
			document.body.removeChild(anchor);
			if (browser) {
				setTimeout(() => URL.revokeObjectURL(url), 500);
			}
			notifySuccess(`Downloading ${entry.name || entry.path}`);
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to download artifact.';
			notifyError(message);
		}
	};

	const resetUploadForm = () => {
		uploadFiles = null;
		uploadTarget = '';
		uploadOverwrite = true;
		uploadError = null;
	};

	const resetPreview = () => {
		previewPath = null;
		previewContent = null;
		previewError = null;
		previewLoading = false;
		previousRunId = null;
		previousContent = null;
		previousError = null;
		previousLoading = false;
	};

	const resolveUploadPath = (fileName: string): string | null => {
		const desired = uploadTarget.trim().replace(/^(\.\/|\/)+/, '');
		if (desired) {
			return desired;
		}
		const name = fileName.trim();
		if (!name) {
			return null;
		}
		const base =
			artifactPath === '.'
				? ''
				: artifactPath
						.replace(/^(\.\/|\/)+/, '')
						.replace(/\/+$/, '');
		const combined = base ? `${base}/${name}` : name;
		const normalised = combined.replace(/^(\.\/|\/)+/, '').trim();
		return normalised || null;
	};

	const handleUploadSubmit = async (event: SubmitEvent) => {
		event.preventDefault();
		uploadError = null;

		if (!token) {
			const message = 'Sign in to upload artifacts.';
			uploadError = message;
			notifyError(message);
			return;
		}
		if (!activeProjectValue || !selectedRunId) {
			const message = 'Select a project and run to upload artifacts.';
			uploadError = message;
			notifyError(message);
			return;
		}
		const file = uploadFiles?.item(0) ?? null;
		if (!file) {
			uploadError = 'Choose a file to upload.';
			return;
		}
		const resolvedPath = resolveUploadPath(file.name);
		if (!resolvedPath) {
			uploadError = 'Provide a destination path for the artifact.';
			return;
		}

		const currentPath = artifactPath;
		uploadBusy = true;
		try {
			await projectState.uploadArtifact(fetch, token, activeProjectValue.id, selectedRunId, {
				path: resolvedPath,
				file,
				overwrite: uploadOverwrite
			});
			notifySuccess(`Uploaded ${file.name}`);
			resetUploadForm();
			await loadArtifacts(currentPath, selectedRunId, activeProjectValue.id);
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to upload artifact.';
			uploadError = message;
			notifyError(message);
		} finally {
			uploadBusy = false;
		}
	};

	const handleDeleteArtifact = async (entry: ArtifactEntry) => {
		if (entry.is_dir) {
			await navigateToPath(entry.path);
			return;
		}
		if (!token) {
			notifyError('Sign in to delete artifacts.');
			return;
		}
		if (!activeProjectValue || !selectedRunId) {
			notifyError('Select a project and run to delete artifacts.');
			return;
		}
		if (browser) {
			const confirmed = window.confirm(`Delete ${entry.name || entry.path}? This cannot be undone.`);
			if (!confirmed) {
				return;
			}
		}
		const currentPath = artifactPath;
		deleteBusyPath = entry.path;
		try {
			await projectState.deleteArtifact(fetch, token, activeProjectValue.id, selectedRunId, entry.path);
			notifySuccess(`Deleted ${entry.name || entry.path}`);
			await loadArtifacts(currentPath, selectedRunId, activeProjectValue.id);
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to delete artifact.';
			notifyError(message);
	} finally {
		deleteBusyPath = null;
	}
};

	const openPromoteModal = (entry: ArtifactEntry) => {
		if (entry.is_dir) {
			void navigateToPath(entry.path);
			return;
		}
		promoteTarget = entry;
		promoteName = entry.name || entry.path;
		const defaults = loadPromotionDefaults();
		if (!promotionPrefsLoaded) {
			promotionPrefsLoaded = true;
		}
		if (defaults.assetType) promoteType = defaults.assetType;
		else if (!promoteType.trim()) promoteType = 'terraform';
		if (defaults.tags !== undefined) promoteTags = defaults.tags;
		if (defaults.metadata) promoteMetadata = defaults.metadata;
		else if (!promoteMetadata.trim()) promoteMetadata = '{\n\n}';
		if (defaults.description !== undefined) promoteDescription = defaults.description;
		if (defaults.notes !== undefined) promoteNotes = defaults.notes;
		if (!promoteType.trim()) {
			promoteType = 'terraform';
		}
		if (!promoteMetadata.trim()) {
			promoteMetadata = '{\n\n}';
		}
		promoteError = null;
	};

	const closePromoteModal = () => {
		if (promoteSubmitting) return;
		promoteTarget = null;
		promoteError = null;
		showTagSuggestions = false;
	};

	const handlePromoteSubmit = async (event: SubmitEvent) => {
		event.preventDefault();
		if (!token) {
			notifyError('Sign in to promote artifacts.');
			return;
		}
		if (!activeProjectValue || !selectedRunId || !promoteTarget) {
			notifyError('Select a project and run to promote artifacts.');
			return;
		}
		const trimmedName = promoteName.trim();
		if (!trimmedName) {
			promoteError = 'Asset name is required.';
			return;
		}
		const trimmedType = promoteType.trim();
		if (!trimmedType) {
			promoteError = 'Asset type is required.';
			return;
		}
		const tagList = promoteTags
			.split(',')
			.map((tag) => tag.trim())
			.filter((tag) => tag.length > 0);
		let metadata: Record<string, unknown> | undefined;
		const metadataPayload = promoteMetadata.trim();
		if (metadataPayload) {
			try {
				const parsed = JSON.parse(metadataPayload);
				if (!parsed || typeof parsed !== 'object') {
					throw new Error('Metadata must be a JSON object.');
				}
				metadata = parsed as Record<string, unknown>;
			} catch (error) {
				promoteError = error instanceof Error ? error.message : 'Metadata must be valid JSON.';
				return;
			}
		}

		promoteBusyPath = promoteTarget.path;
		promoteSubmitting = true;
		promoteError = null;
		try {
			await projectState.registerLibraryAsset(fetch, token, activeProjectValue.id, {
				name: trimmedName,
				asset_type: trimmedType,
				description: promoteDescription.trim() || undefined,
				tags: tagList,
				metadata,
				run_id: selectedRunId,
				artifact_path: promoteTarget.path,
				notes: promoteNotes.trim() || undefined
			});
		notifySuccess(`Promoted ${trimmedName} to the library.`);
		closePromoteModal();
		storePromotionDefaults({
			assetType: trimmedType,
			tags: tagList.join(', '),
			metadata: metadataPayload || undefined,
			description: promoteDescription.trim() || undefined,
			notes: promoteNotes.trim() || undefined
		});
	} catch (error) {
		const message = error instanceof Error ? error.message : 'Failed to promote artifact.';
		promoteError = message;
		notifyError(message);
		} finally {
			promoteBusyPath = null;
			promoteSubmitting = false;
		}
	};

	const MAX_PREVIEW_BYTES = 512 * 1024; // 512 KB
	const textLikeContentTypes = ['text/', 'application/json', 'application/x-yaml', 'application/javascript'];

	const isLikelyText = (contentType: string | null, sample: Uint8Array) => {
		if (contentType && textLikeContentTypes.some((token) => contentType.includes(token))) {
			return true;
		}
		if (!sample.length) return true;
		const limit = Math.min(sample.length, 2048);
		let nonPrintable = 0;
		for (let i = 0; i < limit; i += 1) {
			const byte = sample[i];
			if (byte === 0) {
				return false;
			}
			if (byte < 9 || (byte > 13 && byte < 32)) {
				nonPrintable += 1;
			}
		}
		return nonPrintable / limit < 0.1;
	};

	const findPreviousRunId = () => {
		if (!selectedRunId) return null;
		const index = projectRuns.findIndex((run) => run.id === selectedRunId);
		if (index === -1) return null;
		const candidate = projectRuns[index + 1];
		return candidate?.id ?? null;
	};

	const fetchArtifactText = async (runId: string, path: string) => {
		if (!token || !activeProjectValue) {
			throw new Error('Missing authentication token or active project.');
		}
		const response = await downloadRunArtifact(fetch, token, activeProjectValue.id, runId, path);
		if (!response.ok) {
			throw new Error(`Failed to fetch artifact (${response.status})`);
		}
		const contentType = response.headers.get('content-type');
		const blob = await response.blob();
		if (blob.size > MAX_PREVIEW_BYTES) {
			throw new Error('File too large to preview. Please download instead.');
		}
		const buffer = await blob.arrayBuffer();
		const data = new Uint8Array(buffer);
		if (!isLikelyText(contentType, data)) {
			throw new Error('Binary file preview not supported. Use download instead.');
		}
		const decoder = new TextDecoder('utf-8', { fatal: false });
		return decoder.decode(data);
	};

	const handlePreviewArtifact = async (entry: ArtifactEntry) => {
		if (entry.is_dir) {
			await navigateToPath(entry.path);
			return;
		}
		if (!selectedRunId) return;
		previewPath = entry.path;
		previewContent = null;
		previewError = null;
		previewLoading = true;
		previousContent = null;
		previousError = null;
		previousRunId = null;
		try {
			previewContent = await fetchArtifactText(selectedRunId, entry.path);
		} catch (error) {
			previewError = error instanceof Error ? error.message : 'Unable to preview artifact.';
		} finally {
			previewLoading = false;
		}

		const candidateRunId = findPreviousRunId();
		if (!candidateRunId) {
			return;
		}
		previousRunId = candidateRunId;
		previousLoading = true;
		try {
			previousContent = await fetchArtifactText(candidateRunId, entry.path);
		} catch (error) {
			previousError = error instanceof Error ? error.message : 'Unable to load previous run artifact.';
		} finally {
			previousLoading = false;
		}
	};
</script>

<section class="rounded-3xl border border-slate-200 bg-white px-6 py-6 shadow-sm shadow-slate-200">
	<div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{title}</p>
			{#if activeProjectValue}
				<h3 class="mt-1 text-xl font-semibold text-slate-700">{activeProjectValue.name}</h3>
				<p class="text-sm text-slate-500">
					Slug
					<span class="ml-2 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-2 py-[2px] text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-slate-500">
						{activeProjectValue.slug}
					</span>
				</p>
			{:else}
				<p class="text-sm text-slate-500">{emptyMessage}</p>
			{/if}
		</div>
		{#if activeProjectValue && projectRuns.length}
			<div class="flex flex-col gap-2 text-sm text-slate-600">
				<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="run-select">
					Run history
				</label>
				<select
					id="run-select"
					class="w-64 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
					onchange={handleRunChange}
					value={selectedRunId ?? ''}
				>
					{#each projectRuns as run (run.id)}
						<option value={run.id}>
							{run.label} · {run.status}
							{#if highlightReportId && run.summary && (run.summary as { saved_report_id?: string | null }).saved_report_id === highlightReportId}
								★
							{/if}
						</option>
					{/each}
				</select>
				{#if highlightReportId}
					<p class="text-[0.65rem] text-slate-400">
						★ indicates runs linked to this report.
					</p>
				{/if}
			</div>
		{/if}
	</div>

	{#if selectedRun}
		<div class="mt-5 space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-500">
			<h4 class="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-slate-400">Run summary</h4>
			<div class="flex flex-wrap gap-3">
				<span class="rounded-full border border-slate-200 px-3 py-[2px] text-[0.65rem] font-semibold text-slate-600">
					Status: {selectedRun.status}
				</span>
				{#if highlightReportId && selectedRun.summary && (selectedRun.summary as { saved_report_id?: string | null }).saved_report_id === highlightReportId}
					<span class="rounded-full border border-sky-200 bg-sky-50 px-3 py-[2px] text-[0.65rem] font-semibold text-sky-600">
						Linked report
					</span>
				{/if}
				{#if selectedRun.triggered_by}
					<span class="rounded-full border border-slate-200 px-3 py-[2px] text-[0.65rem] font-semibold text-slate-600">
						Triggered by: {selectedRun.triggered_by}
					</span>
				{/if}
				{#if selectedRun.created_at}
					<span class="rounded-full border border-slate-200 px-3 py-[2px] text-[0.65rem] font-semibold text-slate-600">
						Created: {selectedRun.created_at}
					</span>
				{/if}
			</div>
			{#if selectedRun.parameters}
				<div class="space-y-1">
					<p class="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-slate-400">Parameters</p>
					<pre class="overflow-auto rounded-xl border border-slate-200 bg-white p-3 font-mono text-[0.7rem] text-slate-600">{JSON.stringify(selectedRun.parameters, null, 2)}</pre>
				</div>
			{/if}
			{#if selectedRun.summary}
				<div class="space-y-1">
					<p class="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-slate-400">Summary</p>
					<pre class="overflow-auto rounded-xl border border-slate-200 bg-white p-3 font-mono text-[0.7rem] text-slate-600">{JSON.stringify(selectedRun.summary, null, 2)}</pre>
				</div>
			{/if}
		</div>
	{/if}

	{#if activeProjectValue && selectedRunId}
		<div class="mt-6 space-y-4">
			<div class="flex items-center justify-between gap-3">
				<div class="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
					<span>Artifacts</span>
					{#if breadcrumbStack.length}
						<button
							type="button"
							class="rounded-full border border-slate-200 px-2 py-[2px] text-[0.6rem] font-semibold text-slate-500 transition hover:bg-slate-100"
							onclick={() => void handleBreadcrumbClick(-1)}
						>
							Root
						</button>
						{#each breadcrumbStack as path, index (path)}
							<span class="text-slate-300">/</span>
							<button
								type="button"
								class="rounded-full border border-slate-200 px-2 py-[2px] text-[0.6rem] font-semibold text-slate-500 transition hover:bg-slate-100"
								onclick={() => void handleBreadcrumbClick(index)}
							>
								{path.split('/').pop()}
							</button>
						{/each}
					{/if}
				</div>
				{#if artifactsLoading}
					<span class="text-xs text-slate-400">Loading artifacts…</span>
				{/if}
			</div>

			<div class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-100">
				<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Upload artifact</h4>
				<form class="mt-3 grid gap-3 md:grid-cols-[minmax(0,240px)_1fr]" onsubmit={handleUploadSubmit}>
					<div class="space-y-2">
						<label class="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400" for="artifact-file">
							File
							<input
								id="artifact-file"
								type="file"
								class="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
								bind:files={uploadFiles}
								disabled={uploadBusy || !token}
							/>
						</label>
						<label class="inline-flex items-center gap-2 text-xs text-slate-500" for="artifact-overwrite">
							<input
								id="artifact-overwrite"
								type="checkbox"
								class="h-4 w-4 rounded border-slate-300 text-sky-500 focus:ring-sky-200"
								bind:checked={uploadOverwrite}
								disabled={uploadBusy}
							/>
							<span>Overwrite existing file if present</span>
						</label>
					</div>
					<div class="space-y-2">
						<label class="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400" for="artifact-path">
							Target path
							<input
								id="artifact-path"
								type="text"
								class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
								placeholder={artifactPath === '.' ? 'example.tf' : `${artifactPath}/example.tf`}
								bind:value={uploadTarget}
								disabled={uploadBusy}
							/>
						</label>
						<p class="text-xs text-slate-400">
							Defaults to the current folder ({artifactPath === '.' ? 'root' : artifactPath}).
						</p>
						<div class="flex flex-wrap gap-2">
							<button
								type="submit"
								class="inline-flex items-center justify-center rounded-xl bg-sky-500 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-sky-200 transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
								disabled={uploadBusy || !token}
							>
								{#if uploadBusy}
									<span class="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
								{/if}
								Upload
							</button>
							<button
								type="button"
								class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
								onclick={resetUploadForm}
								disabled={uploadBusy || (!uploadFiles && !uploadTarget)}
							>
								Clear
							</button>
						</div>
					</div>
				</form>
				{#if !token}
					<p class="mt-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
						Provide an API token to enable artifact uploads.
					</p>
				{/if}
				{#if uploadError}
					<p class="mt-2 rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-600">{uploadError}</p>
				{/if}
			</div>

			{#if artifactsError}
				<div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-600">
					{artifactsError}
				</div>
			{:else if artifacts.length}
				<ul class="grid gap-2 md:grid-cols-2">
					{#each artifacts as entry (entry.path)}
						{@const deleting = deleteBusyPath === entry.path}
						<li class="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
							<div class="flex flex-col">
								<span class="font-semibold text-slate-700">{entry.name || entry.path || 'artifact'}</span>
								<span class="text-xs text-slate-400">
									{entry.is_dir ? 'Directory' : `${entry.size ?? 0} bytes`} · {entry.modified_at ?? 'unknown'}
								</span>
							</div>
							<div class="flex items-center gap-2">
								{#if entry.is_dir}
									<button
										type="button"
										class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-500 transition hover:bg-slate-100"
										onclick={() => void navigateToPath(entry.path)}
									>
										Open
									</button>
								{:else}
									<button
										type="button"
										class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-500 transition hover:bg-slate-100"
										onclick={() => void handlePreviewArtifact(entry)}
									>
										Preview
									</button>
									<button
										type="button"
										class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-500 transition hover:bg-slate-100"
										onclick={() => void downloadArtifact(entry)}
									>
										Download
									</button>
										<button
											type="button"
											class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
											onclick={() => openPromoteModal(entry)}
											disabled={promoteBusyPath === entry.path}
										>
										{#if promoteBusyPath === entry.path}
											<span class="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
										{/if}
										Promote
									</button>
									<button
										type="button"
										class="inline-flex items-center gap-2 rounded-xl border border-rose-200 px-3 py-1 text-xs font-semibold text-rose-600 transition hover:bg-rose-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
										onclick={() => void handleDeleteArtifact(entry)}
										disabled={deleting}
									>
										{#if deleting}
											<span class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
										{/if}
										Delete
									</button>
								{/if}
							</div>
						</li>
					{/each}
				</ul>
			{:else}
				<div class="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
					No artifacts recorded for this run yet.
				</div>
			{/if}

			{#if previewPath}
				<div class="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-100">
					<div class="flex flex-wrap items-center justify-between gap-2">
						<div class="space-y-1">
							<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Preview</p>
							<p class="text-sm text-slate-500">{previewPath}</p>
						</div>
						<button
							type="button"
							class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-500 transition hover:bg-slate-100"
							onclick={resetPreview}
						>
							Close preview
						</button>
					</div>
					{#if previewLoading}
						<p class="text-xs text-slate-400">Loading preview…</p>
					{:else if previewError}
						<p class="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-600">{previewError}</p>
					{:else if previewContent}
						<pre class="max-h-96 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700"><code>{previewContent}</code></pre>
					{/if}

					{#if previousRunId}
						<div class="rounded-xl border border-slate-200 bg-slate-50 p-3">
							<div class="flex items-center justify-between gap-2">
								<p class="text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-slate-400">
									Previous run ({previousRunId})
								</p>
								{#if previousLoading}
									<span class="text-[0.65rem] text-slate-400">Loading…</span>
								{/if}
							</div>
							{#if previousError}
								<p class="mt-2 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">{previousError}</p>
							{:else if previousContent}
								<pre class="mt-2 max-h-64 overflow-auto rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600"><code>{previousContent}</code></pre>
							{:else if !previousLoading}
								<p class="mt-2 text-xs text-slate-500">No matching artifact found in the previous run.</p>
							{/if}
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{:else if activeProjectValue}
		<div class="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
			No runs available for this project. Generate a blueprint or upload a review to create one.
		</div>
	{/if}
</section>

{#if promoteTarget}
	<div class="fixed inset-0 z-50 flex items-center justify-center px-4 py-6">
		<button
			type="button"
			class="absolute inset-0 bg-slate-900/60"
			onclick={closePromoteModal}
			aria-label="Close promotion dialog"
		></button>
		<div
			class="relative w-full max-w-lg rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-900/20"
			role="dialog"
			aria-modal="true"
		>
			<div class="flex items-start justify-between gap-4">
				<div>
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Promote artifact</p>
					<p class="mt-1 text-sm text-slate-600">{promoteTarget.path}</p>
				</div>
				<button
					type="button"
					class="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-500"
					onclick={closePromoteModal}
					aria-label="Close promotion dialog"
				>
					Close
				</button>
			</div>
			<form class="mt-4 space-y-4 text-sm" onsubmit={handlePromoteSubmit}>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="promote-name">
						Asset name
					</label>
					<input
						id="promote-name"
						class="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						type="text"
						bind:value={promoteName}
						required
					/>
				</div>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="promote-type">
						Asset type
					</label>
					<input
						id="promote-type"
						class="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						type="text"
						bind:value={promoteType}
						required
					/>
				</div>
				<div class="relative grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="promote-tags">
						Tags
					</label>
					<input
						id="promote-tags"
						class="rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						type="text"
						placeholder="baseline, production"
						bind:value={promoteTags}
						onfocus={() => (showTagSuggestions = tagSuggestions.length > 0)}
						onblur={() => setTimeout(() => (showTagSuggestions = false), 120)}
						onkeydown={(event: KeyboardEvent) => {
							if (event.key === 'Enter' && !event.shiftKey) {
								event.preventDefault();
								const parts = promoteTags
									.split(',')
									.map((tag) => tag.trim())
									.filter((tag) => tag.length > 0);
								promoteTags = Array.from(new Set(parts)).join(', ');
							}
						}}
					/>
					<p class="text-xs text-slate-400">Separate tags with commas.</p>
					{#if showTagSuggestions && tagSuggestions.length}
						<div class="absolute z-20 mt-1 w-full max-w-xs rounded-xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-900/10">
							<p class="px-2 pb-1 text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-slate-400">
								Suggested tags
							</p>
							<ul class="max-h-36 overflow-auto text-xs">
								{#each tagSuggestions as tag (tag)}
									<li>
										<button
											type="button"
											class="w-full rounded-lg px-2 py-1 text-left text-slate-600 transition hover:bg-slate-100"
											onclick={() => {
												applyTagSuggestion(tag);
												showTagSuggestions = false;
											}}
										>
											{tag}
										</button>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
				</div>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="promote-description">
						Description
					</label>
					<textarea
						id="promote-description"
						class="h-20 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						bind:value={promoteDescription}
					></textarea>
				</div>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="promote-notes">
						Notes
					</label>
					<textarea
						id="promote-notes"
						class="h-20 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						bind:value={promoteNotes}
						placeholder="Additional context or instructions"
					></textarea>
				</div>
				<div class="grid gap-3">
					<label class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400" for="promote-metadata">
						Metadata (JSON)
					</label>
					<textarea
						id="promote-metadata"
						class="h-24 rounded-xl border border-slate-200 px-3 py-2 font-mono text-[0.75rem] text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						bind:value={promoteMetadata}
						placeholder={`{
  "env": "prod"
}`}
					></textarea>
				</div>
				{#if promoteError}
					<p class="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600">{promoteError}</p>
				{/if}
				<div class="flex flex-wrap items-center justify-end gap-2 pt-2">
					<button
						type="button"
						class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-500 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
						onclick={closePromoteModal}
						disabled={promoteSubmitting}
					>
						Cancel
					</button>
					<button
						type="submit"
						class="inline-flex items-center gap-2 rounded-xl border border-sky-500 bg-sky-500 px-4 py-2 text-xs font-semibold text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
						disabled={promoteSubmitting}
					>
						{#if promoteSubmitting}
							<span class="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
						{/if}
						Promote to library
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
