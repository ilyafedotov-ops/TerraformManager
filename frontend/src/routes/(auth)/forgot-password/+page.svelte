<script lang="ts">
	import { goto } from '$app/navigation';

	const handleSubmit = (event: SubmitEvent) => {
		event.preventDefault();
		console.info('Password reset placeholder triggered');
		goto('/login');
	};
</script>

<form class="space-y-8" on:submit={handleSubmit}>
	<div class="space-y-2">
		<h2 class="text-3xl font-semibold text-white">Recover API token</h2>
		<p class="text-sm text-slate-400">
			Need access again? Enter your work email and we&rsquo;ll share token retrieval instructions. Automated delivery
			will be wired into identity integrations later in the migration.
		</p>
	</div>

	<div class="space-y-6">
		<label class="block space-y-2 text-sm font-medium text-slate-200">
			<span>Email</span>
			<input
				class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
				type="email"
				name="email"
				placeholder="security@company.com"
				required
			/>
		</label>
	</div>

	<button
		class="inline-flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-violet-500 via-indigo-500 to-purple-500 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-violet-900/40 transition hover:from-violet-400 hover:via-indigo-400 hover:to-purple-400 focus:outline-none focus:ring-2 focus:ring-violet-400/40"
		type="submit"
	>
		Send recovery email
	</button>

	<p class="text-xs text-slate-500">
		Remembered your token?
		<a class="font-semibold text-sky-300 hover:text-sky-200" href="/login">Back to sign-in</a>
	</p>
</form>
