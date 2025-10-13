<script lang="ts">
	import { browser } from '$app/environment';
	import { downloadRunArtifact, type ArtifactEntry } from '$lib/api/client';
	import { notifyError, notifySuccess } from '$lib/stores/notifications';
	import { activeProject, activeProjectRuns, projectState } from '$lib/stores/project';

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

	const activeProjectValue = $derived($activeProject);
	const projectRuns = $derived($activeProjectRuns);
const selectedRun = $derived(projectRuns.find((run) => run.id === selectedRunId) ?? null);
const highlightedRunId = $derived(() => {
	if (!highlightReportId) return null;
	const match = projectRuns.find((run) => {
		const summary = run.summary as Record<string, unknown> | null | undefined;
		const savedId = summary && typeof summary === 'object' ? (summary as { saved_report_id?: string | null }).saved_report_id : null;
		return savedId === highlightReportId;
	});
	return match?.id ?? null;
});

	const normalisePath = (value: string) => (value && value !== '.' ? value : '.');

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
	};

	const loadArtifacts = async (path: string, runId: string, projectId: string) => {
		const targetPath = normalisePath(path);
		if (!token) {
			artifacts = [];
			artifactsLoading = false;
			artifactsError = 'Missing API token – unable to load artifacts.';
			updateBreadcrumbs('.');
			return;
		}
		artifactsLoading = true;
		artifactsError = null;
		try {
			const cached = projectState.getCachedArtifacts(runId, targetPath);
			if (cached) {
				applyArtifacts(targetPath, cached.entries);
			} else {
				const entries = await projectState.loadArtifacts(fetch, token, projectId, runId, targetPath);
				applyArtifacts(targetPath, entries);
			}
		} catch (error) {
			const message = error instanceof Error ? error.message : 'Failed to load run artifacts.';
			artifactsError = message;
			artifacts = [];
			updateBreadcrumbs('.');
		} finally {
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
	};

	const selectRun = async (runId: string | null, path = '.') => {
		if (!activeProjectValue || !runId) {
			selectedRunId = null;
			resetArtifacts();
			return;
		}
		selectedRunId = runId;
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

			{#if artifactsError}
				<div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-600">
					{artifactsError}
				</div>
			{:else if artifacts.length}
				<ul class="grid gap-2 md:grid-cols-2">
					{#each artifacts as entry (entry.path)}
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
										onclick={() => void downloadArtifact(entry)}
									>
										Download
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
		</div>
	{:else if activeProjectValue}
		<div class="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
			No runs available for this project. Generate a blueprint or upload a review to create one.
		</div>
	{/if}
</section>
