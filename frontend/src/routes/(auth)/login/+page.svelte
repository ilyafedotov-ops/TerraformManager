<script lang="ts">
	let email = '';
	let apiToken = '';

	const handleSubmit = (event: SubmitEvent) => {
		event.preventDefault();
		// TODO: Replace with real authentication workflow when backend auth is available.
		console.info('Attempted login with', { email, apiToken });
	};
</script>

<form class="space-y-8" on:submit={handleSubmit}>
	<div class="space-y-2">
		<h2 class="text-3xl font-semibold text-white">Welcome back 👋</h2>
		<p class="text-sm text-slate-400">
			Use your Terraform Manager workspace credentials or personal API token. Authentication integrations will be wired
			up in a future milestone.
		</p>
	</div>

	<div class="space-y-6">
		<label class="block space-y-2 text-sm font-medium text-slate-200">
			<span>Email</span>
			<input
				class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
				type="email"
				name="email"
				placeholder="you@example.com"
				bind:value={email}
				required
			/>
		</label>

		<label class="block space-y-2 text-sm font-medium text-slate-200">
			<span>API Token</span>
			<input
				class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
				type="password"
				name="token"
				placeholder="Paste your Terraform Manager token"
				bind:value={apiToken}
			/>
			<p class="text-xs text-slate-500">
				Hint: set <code class="rounded bg-slate-800 px-1 py-0.5 text-xs text-slate-200">TFM_API_TOKEN</code> on the server, then paste it
				here to unlock API access.
			</p>
		</label>
	</div>

	<button
		class="inline-flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-sky-900/40 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
		type="submit"
	>
		Sign in
	</button>

	<div class="flex flex-col gap-2 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
		<a class="font-semibold text-sky-300 hover:text-sky-200" href="/forgot-password">Forgot token?</a>
		<div>
			New here?
			<a class="font-semibold text-sky-300 hover:text-sky-200" href="/register">Create workspace access</a>
		</div>
	</div>
</form>
