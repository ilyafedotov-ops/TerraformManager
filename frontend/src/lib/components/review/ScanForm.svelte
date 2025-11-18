<script lang="ts" module>
export type ScanFormData = {
	files: FileList | null;
	terraformValidate: boolean;
	saveReport: boolean;
	includeCost: boolean;
	usageFile: File | null;
	planFile: File | null;
};
</script>

<script lang="ts">
import StepBar from '$lib/components/dashboard/StepBar.svelte';
import { createEventDispatcher } from 'svelte';

type ScanFormProps = {
	steps: { title: string; description?: string; status?: 'completed' | 'current' | 'upcoming' }[];
	files?: FileList | null;
	terraformValidate?: boolean;
	saveReport?: boolean;
	includeCost?: boolean;
	usageFiles?: FileList | null;
	planFiles?: FileList | null;
	isSubmitting?: boolean;
	error?: string | null;
};

/** Upload form for reviewer scans with validation toggles and workflow steps. */
let {
	steps,
	files = $bindable<FileList | null>(null),
	terraformValidate = $bindable(false),
	saveReport = $bindable(true),
	includeCost = $bindable(false),
	usageFiles = $bindable<FileList | null>(null),
	planFiles = $bindable<FileList | null>(null),
	isSubmitting = false,
	error = null
}: ScanFormProps = $props();

const dispatch = createEventDispatcher<{ submit: ScanFormData }>();

const acceptedExtensions = ['tf', 'zip'];
let isDragActive = $state(false);
let fileInput = $state<HTMLInputElement | null>(null);

const normaliseFiles = (list: FileList | null): FileList | null => {
	if (!list) return null;
	const entries = Array.from(list).filter((file) => {
		const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
		return acceptedExtensions.includes(ext);
	});
	if (!entries.length) return null;
	if (typeof DataTransfer === 'undefined') {
		return list;
	}
	const dt = new DataTransfer();
	entries.forEach((file) => dt.items.add(file));
	return dt.files;
};

const handleDragOver = (event: DragEvent) => {
	event.preventDefault();
	event.stopPropagation();
	isDragActive = true;
};

const handleDragLeave = (event: DragEvent) => {
	event.preventDefault();
	if (event.currentTarget === event.target) {
		isDragActive = false;
	}
};

const handleDrop = (event: DragEvent) => {
	event.preventDefault();
	event.stopPropagation();
	isDragActive = false;
	const dropped = normaliseFiles(event.dataTransfer?.files ?? null);
	if (dropped) {
		files = dropped;
	}
};

const handleKeyActivate = (event: KeyboardEvent) => {
	if (event.key !== 'Enter' && event.key !== ' ') {
		return;
	}
	event.preventDefault();
	fileInput?.click();
};

const selectedFileNames = () => {
	if (!files) return [] as string[];
	return Array.from(files as FileList).map((file: File) => file.name);
};

const handleSubmit = (event: Event) => {
	event.preventDefault();
	dispatch('submit', {
		files,
		terraformValidate,
		saveReport,
		includeCost,
		usageFile: usageFiles?.item(0) ?? null,
		planFile: planFiles?.item(0) ?? null
	});
};
</script>

<form class="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40" onsubmit={handleSubmit}>
	<div class="rounded-2xl border border-slate-100 bg-slate-50/60 p-4">
		<StepBar steps={steps} />
	</div>
	<div class="space-y-4">
	<section class="space-y-2">
		<p class="text-sm font-semibold text-slate-600">
			<span class="uppercase tracking-[0.3em] text-slate-400">Terraform files / archives</span>
		</p>
		<div
			class={`relative flex min-h-[9rem] flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-5 text-center text-sm transition ${
				isDragActive ? 'border-sky-500 bg-sky-50/60 text-sky-700' : 'border-slate-200 bg-slate-50 text-slate-500'
			}`}
			role="button"
			tabindex="0"
			aria-label="Terraform files dropzone"
			ondragover={handleDragOver}
			ondragleave={handleDragLeave}
			ondrop={handleDrop}
			onkeydown={handleKeyActivate}
		>
			<input
				class="absolute inset-0 h-full w-full cursor-pointer opacity-0"
				type="file"
				multiple
				accept=".tf,.zip"
				bind:files
				aria-label="Terraform files or zip archives"
				bind:this={fileInput}
				onchange={() => {
					files = normaliseFiles(files);
				}}
			/>
			<div class="pointer-events-none space-y-1">
				<p class="font-semibold">
					{#if isDragActive}
						Release to upload
					{:else}
						Drag and drop files or click to browse
					{/if}
				</p>
				<p class="text-xs text-slate-500">Accepts `.tf` modules or `.zip` bundles. Up to 50 files per run.</p>
			</div>
		</div>
		{#if selectedFileNames().length}
			<ul class="space-y-1 rounded-2xl border border-slate-100 bg-white px-4 py-3 text-left text-xs text-slate-500">
				{#each selectedFileNames() as name}
					<li class="truncate">{name}</li>
				{/each}
			</ul>
		{/if}
	</section>

		<div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
			<label class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
				<input class="h-4 w-4 rounded border-slate-300 text-sky-400 focus:ring-sky-400/60" type="checkbox" bind:checked={terraformValidate} />
				<span>
					<span class="font-semibold text-slate-700">Run <code class="rounded bg-slate-200 px-1 py-0.5 text-xs text-slate-600">terraform validate</code></span>
					<span class="block text-xs text-slate-500">Requires terraform binary on the API host.</span>
				</span>
			</label>
			<label class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
				<input class="h-4 w-4 rounded border-slate-300 text-sky-400 focus:ring-sky-400/60" type="checkbox" bind:checked={saveReport} />
				<span>
					<span class="font-semibold text-slate-700">Store report in database</span>
					<span class="block text-xs text-slate-500">Enables follow-up review from the Reports tab.</span>
				</span>
			</label>
			<label class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
				<input class="h-4 w-4 rounded border-slate-300 text-sky-400 focus:ring-sky-400/60" type="checkbox" bind:checked={includeCost} />
				<span>
					<span class="font-semibold text-slate-700">Include cost estimates</span>
					<span class="block text-xs text-slate-500">Runs Infracost to highlight total and delta spend.</span>
				</span>
			</label>
		</div>
		{#if includeCost}
			<label class="block text-sm font-semibold text-slate-600">
				<span class="uppercase tracking-[0.3em] text-slate-400">Infracost usage file (optional)</span>
				<input
					class="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
					type="file"
					accept=".yml,.yaml,.json"
					bind:files={usageFiles}
					aria-label="Infracost usage file"
				/>
			</label>
		{/if}
		<label class="block text-sm font-semibold text-slate-600">
			<span class="uppercase tracking-[0.3em] text-slate-400">Terraform plan (JSON)</span>
			<input
				class="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
				type="file"
				accept=".json"
				bind:files={planFiles}
				aria-label="Terraform plan JSON"
			/>
		</label>
	</div>

	{#if error}
		<div class="rounded-2xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700">
			{error}
		</div>
	{/if}

	<button
		class="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-300/50 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
		type="submit"
		disabled={isSubmitting}
	>
		{#if isSubmitting}
			<span class="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-transparent"></span>
			Running scan…
		{:else}
			Run scan
		{/if}
	</button>
</form>
