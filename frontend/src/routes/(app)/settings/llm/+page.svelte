<script lang="ts">
	let provider = 'off';
	let model = 'gpt-4.1-mini';
	let enableExplanations = true;
	let enablePatches = false;

	const providers = [
		{ label: 'Off', value: 'off' },
		{ label: 'OpenAI', value: 'openai' },
		{ label: 'Azure OpenAI', value: 'azure' }
	];
</script>

<section class="space-y-8">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Settings</p>
		<h2 class="text-3xl font-semibold text-white">LLM assistance</h2>
		<p class="max-w-2xl text-sm text-slate-400">
			This configuration maps directly to the SQLite-backed settings stored via `/settings/llm`. Toggle providers and
			models here; the backend will continue to gate deterministic findings separately.
		</p>
	</header>

	<form class="space-y-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40">
		<label class="block space-y-2 text-sm font-medium text-slate-200">
			<span>Provider</span>
			<select
				class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
				bind:value={provider}
			>
				{#each providers as option}
					<option value={option.value}>{option.label}</option>
				{/each}
			</select>
		</label>

		<label class="block space-y-2 text-sm font-medium text-slate-200">
			<span>Model / deployment</span>
			<input
				class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/40 disabled:text-slate-600"
				type="text"
				bind:value={model}
				placeholder="gpt-4.1-mini"
				disabled={provider === 'off'}
			/>
			<p class="text-xs text-slate-500">
				OpenAI: enter model name. Azure: supply deployment identifier. Additional fields (API base, version, deployment)
				will appear once backend schema is exposed.
			</p>
		</label>

		<div class="grid gap-4 md:grid-cols-2">
			<label class="flex items-center gap-3 rounded-2xl border border-white/5 bg-slate-900/70 px-4 py-3 text-sm text-slate-200">
				<input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={enableExplanations} />
				<span class="flex-1">
					<span class="font-semibold text-white">Enable AI explanations</span>
					<p class="text-xs text-slate-400">Show LLM-authored rationale next to rule summaries.</p>
				</span>
			</label>
			<label class="flex items-center gap-3 rounded-2xl border border-white/5 bg-slate-900/70 px-4 py-3 text-sm text-slate-200">
				<input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={enablePatches} />
				<span class="flex-1">
					<span class="font-semibold text-white">Enable AI patch suggestions</span>
					<p class="text-xs text-slate-400">Experimental diff guidance displayed with reviewer findings.</p>
				</span>
			</label>
		</div>

		<div class="flex flex-wrap gap-3">
			<button
				class="rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-sky-900/40 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
				type="button"
			>
				Save settings
			</button>
			<button class="rounded-2xl border border-white/10 px-5 py-2 text-sm font-semibold text-slate-200 hover:border-sky-400/40 hover:text-white" type="button">
				Test connection
			</button>
		</div>

		<div class="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4 text-xs text-sky-100">
			<p class="font-semibold uppercase tracking-[0.3em] text-sky-300">Next steps</p>
			<p class="mt-2">Wire these controls to `/settings/llm` GET/POST and `/settings/llm/test` endpoints in Phase 3.</p>
		</div>
	</form>
</section>
