<script lang="ts">
	import { goto } from '$app/navigation';

	const handleSubmit = (event: SubmitEvent) => {
		event.preventDefault();
		console.info('Registration placeholder triggered');
		goto('/login');
	};
</script>

<form class="space-y-8" on:submit={handleSubmit}>
	<div class="space-y-2">
		<h2 class="text-3xl font-semibold text-white">Request access</h2>
		<p class="text-sm text-slate-400">
			Provisioning workflows will integrate with your identity provider in a later milestone. For now, this screen
			captures intent and loops you back to the sign-in flow.
		</p>
	</div>

	<div class="space-y-6">
		<label class="block space-y-2 text-sm font-medium text-slate-200">
			<span>Work email</span>
			<input
				class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
				type="email"
				name="email"
				placeholder="platform@company.com"
				required
			/>
		</label>

		<label class="block space-y-2 text-sm font-medium text-slate-200">
			<span>Team / project</span>
			<input
				class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
				type="text"
				name="team"
				placeholder="SRE / Terraform Foundations"
				required
			/>
		</label>

		<label class="block space-y-2 text-sm font-medium text-slate-200">
			<span>Deployment region</span>
			<select
				class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
				name="region"
			>
				<option value="us">US</option>
				<option value="eu">EU</option>
				<option value="apac">APAC</option>
			</select>
		</label>
	</div>

	<button
		class="inline-flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-emerald-500 via-emerald-400 to-green-500 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-emerald-900/40 transition hover:from-emerald-400 hover:via-emerald-300 hover:to-green-400 focus:outline-none focus:ring-2 focus:ring-emerald-300/40"
		type="submit"
	>
		Request workspace access
	</button>

	<p class="text-xs text-slate-500">
		Already provisioned?
		<a class="font-semibold text-sky-300 hover:text-sky-200" href="/login">Return to sign-in</a>
	</p>
</form>
