<script lang="ts" context="module">
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

/** Upload form for reviewer scans with validation toggles and workflow steps. */
export let steps: { title: string; description?: string; status?: 'completed' | 'current' | 'upcoming' }[];
export let files: FileList | null = null;
export let terraformValidate = false;
export let saveReport = true;
export let includeCost = false;
export let usageFiles: FileList | null = null;
export let planFiles: FileList | null = null;
export let isSubmitting = false;
export let error: string | null = null;

const dispatch = createEventDispatcher<{ submit: ScanFormData }>();

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

<form class="space-y-6 rounded-3xl border border-blueGray-200 bg-white p-6 shadow-xl shadow-blueGray-300/40" onsubmit={handleSubmit}>
	<div class="rounded-2xl border border-blueGray-100 bg-blueGray-50/60 p-4">
		<StepBar steps={steps} />
	</div>
	<div class="space-y-4">
		<label class="block text-sm font-semibold text-blueGray-600">
			<span class="uppercase tracking-[0.3em] text-blueGray-400">Terraform files / archives</span>
			<input
				class="mt-2 w-full cursor-pointer rounded-2xl border border-dashed border-sky-500/40 bg-blueGray-50 px-4 py-6 text-sm text-blueGray-500 transition hover:border-sky-400 hover:bg-blueGray-50"
				type="file"
				multiple
				accept=".tf,.zip"
				bind:files
				aria-label="Terraform files or zip archives"
			/>
		</label>

		<div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
			<label class="flex items-center gap-3 rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-600">
				<input class="h-4 w-4 rounded border-blueGray-300 text-sky-400 focus:ring-sky-400/60" type="checkbox" bind:checked={terraformValidate} />
				<span>
					<span class="font-semibold text-blueGray-700">Run <code class="rounded bg-blueGray-200 px-1 py-0.5 text-xs text-blueGray-600">terraform validate</code></span>
					<span class="block text-xs text-blueGray-500">Requires terraform binary on the API host.</span>
				</span>
			</label>
			<label class="flex items-center gap-3 rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-600">
				<input class="h-4 w-4 rounded border-blueGray-300 text-sky-400 focus:ring-sky-400/60" type="checkbox" bind:checked={saveReport} />
				<span>
					<span class="font-semibold text-blueGray-700">Store report in database</span>
					<span class="block text-xs text-blueGray-500">Enables follow-up review from the Reports tab.</span>
				</span>
			</label>
			<label class="flex items-center gap-3 rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-600">
				<input class="h-4 w-4 rounded border-blueGray-300 text-sky-400 focus:ring-sky-400/60" type="checkbox" bind:checked={includeCost} />
				<span>
					<span class="font-semibold text-blueGray-700">Include cost estimates</span>
					<span class="block text-xs text-blueGray-500">Runs Infracost to highlight total and delta spend.</span>
				</span>
			</label>
		</div>
		{#if includeCost}
			<label class="block text-sm font-semibold text-blueGray-600">
				<span class="uppercase tracking-[0.3em] text-blueGray-400">Infracost usage file (optional)</span>
				<input
					class="mt-2 w-full rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-600 focus:border-lightBlue-400 focus:outline-none focus:ring-2 focus:ring-lightBlue-200"
					type="file"
					accept=".yml,.yaml,.json"
					bind:files={usageFiles}
					aria-label="Infracost usage file"
				/>
			</label>
		{/if}
		<label class="block text-sm font-semibold text-blueGray-600">
			<span class="uppercase tracking-[0.3em] text-blueGray-400">Terraform plan (JSON)</span>
			<input
				class="mt-2 w-full rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-600 focus:border-lightBlue-400 focus:outline-none focus:ring-2 focus:ring-lightBlue-200"
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
		class="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-lightBlue-500 via-indigo-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-lightBlue-300/50 transition hover:from-lightBlue-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-lightBlue-200 disabled:cursor-not-allowed disabled:opacity-60"
		type="submit"
		disabled={isSubmitting}
	>
		{#if isSubmitting}
			<span class="h-4 w-4 animate-spin rounded-full border-2 border-blueGray-200 border-t-transparent"></span>
			Running scan…
		{:else}
			Run scan
		{/if}
	</button>
</form>
