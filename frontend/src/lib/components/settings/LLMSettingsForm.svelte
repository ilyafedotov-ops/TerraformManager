<script lang="ts" context="module">
export type LLMTestStatus = { ok: boolean; stage: string; message: string } | null;
</script>

<script lang="ts">
import { createEventDispatcher } from 'svelte';

/** Form wrapper for configuring LLM provider settings and testing connectivity. */
export let providers: { label: string; value: string }[] = [];
export let provider = 'off';
export let model = '';
export let enableExplanations = false;
export let enablePatches = false;
export let apiBase = '';
export let apiVersion = '';
export let deploymentName = '';
export let saveStatus: string | null = null;
export let testStatus: LLMTestStatus = null;
export let loadError: string | null | undefined = null;
export let tokenPresent = false;
export let isSaving = false;
export let isTesting = false;

const dispatch = createEventDispatcher<{ save: void; test: { live: boolean }; change: void }>();

const isAzure = () => provider === 'azure';
const isOpenAI = () => provider === 'openai';
</script>

<form
	class="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40"
	oninput={() => dispatch('change')}
>
	{#if loadError}
		<div class="rounded-2xl border border-rose-300 bg-rose-50 px-4 py-2 text-xs text-rose-700">{loadError}</div>
	{/if}
	{#if !tokenPresent}
		<div class="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-700">
			No API token detected. Save/test actions require authenticated API access.
		</div>
	{/if}

	<label class="block space-y-2 text-sm font-medium text-slate-600">
		<span>Provider</span>
		<select
			class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
			bind:value={provider}
		>
			{#each providers as option}
				<option value={option.value}>{option.label}</option>
			{/each}
		</select>
	</label>

	<label class="block space-y-2 text-sm font-medium text-slate-600">
		<span>Model / deployment</span>
		<input
			class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:cursor-not-allowed disabled:border-slate-300 disabled:bg-slate-100 disabled:text-slate-600"
			type="text"
			bind:value={model}
			placeholder={provider === 'azure' ? 'azure-deployment-name' : 'gpt-4.1-mini'}
			disabled={provider === 'off'}
		/>
	</label>

	<div class="grid gap-4 md:grid-cols-2">
		<label class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
			<input class="h-4 w-4 rounded border-slate-300 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={enableExplanations} />
			<span class="flex-1">
				<span class="font-semibold text-slate-700">Enable AI explanations</span>
				<p class="text-xs text-slate-500">Show LLM-authored rationale next to reviewer findings.</p>
			</span>
		</label>
		<label class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
			<input class="h-4 w-4 rounded border-slate-300 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={enablePatches} />
			<span class="flex-1">
				<span class="font-semibold text-slate-700">Enable AI patch suggestions</span>
				<p class="text-xs text-slate-500">Experimental diff guidance that supplements deterministic rules.</p>
			</span>
		</label>
	</div>

	{#if isOpenAI()}
		<label class="block space-y-2 text-sm font-medium text-slate-600">
			<span>OpenAI API base (optional)</span>
			<input
				class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
				type="text"
				placeholder="https://api.openai.com/v1"
				bind:value={apiBase}
			/>
		</label>
	{/if}

	{#if isAzure()}
		<div class="grid gap-4 md:grid-cols-3">
			<label class="space-y-2 text-sm font-medium text-slate-600">
				<span>Azure resource URL</span>
		<input
			class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
			type="text"
			placeholder={'https://{resource}.openai.azure.com'}
			bind:value={apiBase}
		/>
			</label>
			<label class="space-y-2 text-sm font-medium text-slate-600">
				<span>API version</span>
				<input
					class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
					type="text"
					placeholder="2024-02-15"
					bind:value={apiVersion}
				/>
			</label>
			<label class="space-y-2 text-sm font-medium text-slate-600">
				<span>Deployment name</span>
				<input
					class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
					type="text"
					placeholder="gpt-4o-mini"
					bind:value={deploymentName}
				/>
			</label>
		</div>
	{/if}

	<div class="flex flex-wrap gap-3">
		<button
			class="rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-5 py-2 text-sm font-semibold text-slate-700 shadow-lg shadow-sky-300/50 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
			type="button"
			onclick={() => dispatch('save')}
			disabled={isSaving}
		>
			{#if isSaving}
				<span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
				Saving…
			{:else}
				Save settings
			{/if}
		</button>
		<button
			class="rounded-2xl border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-600 transition hover:bg-sky-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
			type="button"
			onclick={() => dispatch('test', { live: false })}
			disabled={isTesting}
		>
			Validate configuration
		</button>
		<button
			class="rounded-2xl border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-600 transition hover:bg-sky-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
			type="button"
			onclick={() => dispatch('test', { live: true })}
			disabled={isTesting}
		>
			Live ping
		</button>
	</div>

	{#if saveStatus}
		<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-600">{saveStatus}</div>
	{/if}
	{#if testStatus}
		<div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-600">
			Stage <strong>{testStatus.stage}</strong>: {testStatus.message}
		</div>
	{/if}

	<div class="rounded-2xl border border-sky-200 bg-sky-50 p-4 text-xs text-sky-600">
		<p class="font-semibold uppercase tracking-[0.3em] text-sky-600">Operational tips</p>
		<p class="mt-2">
			Ensure the backend environment exposes the required API keys (OpenAI) or Azure credentials before enabling AI
			assistance. Deterministic findings remain unaffected when the provider is set to <em>Off</em>.
		</p>
	</div>
</form>
