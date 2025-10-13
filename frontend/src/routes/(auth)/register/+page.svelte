<script lang="ts">
	import { enhance } from '$app/forms';
	import { browser } from '$app/environment';
	import { notifySuccess } from '$lib/stores/notifications';

	const { form } = $props();
	let email = $state(form?.values?.email ?? '');
	let team = $state(form?.values?.team ?? '');
	let region = $state(form?.values?.region ?? 'us');
	let notes = $state(form?.values?.notes ?? '');

	let lastSuccessMessage = $state<string | null>(null);

	$effect(() => {
		const nextEmail = form?.values?.email;
		if (nextEmail !== undefined && nextEmail !== email) {
			email = nextEmail;
		}
	});

	$effect(() => {
		const nextTeam = form?.values?.team;
		if (nextTeam !== undefined && nextTeam !== team) {
			team = nextTeam;
		}
	});

	$effect(() => {
		const nextRegion = form?.values?.region;
		if (nextRegion !== undefined && nextRegion !== region) {
			region = nextRegion;
		}
	});

	$effect(() => {
		const nextNotes = form?.values?.notes;
		if (nextNotes !== undefined && nextNotes !== notes) {
			notes = nextNotes;
		}
	});

	$effect(() => {
		const message = form?.success ? form?.message ?? null : null;
		if (!browser) return;
		if (message && message !== lastSuccessMessage) {
			notifySuccess(message, { duration: 6000 });
			lastSuccessMessage = message;
		}
	});
</script>

<form class="space-y-8" method="POST" use:enhance>
	<div class="space-y-2">
		<h2 class="text-3xl font-semibold text-slate-700">Request access</h2>
		<p class="text-sm text-slate-500">
			Provisioning workflows will integrate with your identity provider in a later milestone. Fill out the request below
			and we&rsquo;ll notify the platform team to provision your workspace credentials.
		</p>
	</div>

	{#if form?.error}
		<div class="rounded-2xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700">
			{form.error}
		</div>
	{/if}

	{#if form?.success && form.message}
		<div class="rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
			{form.message}
		</div>
	{/if}

	<div class="space-y-6">
		<label class="block space-y-2 text-sm font-medium text-slate-600">
			<span>Work email</span>
			<input
				class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
				type="email"
				name="email"
				placeholder="platform@company.com"
				bind:value={email}
				required
			/>
		</label>

		<label class="block space-y-2 text-sm font-medium text-slate-600">
			<span>Team / project</span>
			<input
				class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
				type="text"
				name="team"
				placeholder="SRE / Terraform Foundations"
				bind:value={team}
				required
			/>
		</label>

		<label class="block space-y-2 text-sm font-medium text-slate-600">
			<span>Deployment region</span>
			<select
				class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
				name="region"
				bind:value={region}
			>
				<option value="us">US</option>
				<option value="eu">EU</option>
				<option value="apac">APAC</option>
			</select>
		</label>

		<label class="block space-y-2 text-sm font-medium text-slate-600">
			<span>Additional context (optional)</span>
			<textarea
				class="h-24 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
				name="notes"
				placeholder="Share workloads, compliance context, or preferred onboarding timeline."
				bind:value={notes}
			></textarea>
		</label>
	</div>

	<button
		class="inline-flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-emerald-500 via-emerald-400 to-green-500 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-emerald-300/40 transition hover:from-emerald-400 hover:via-emerald-300 hover:to-green-400 focus:outline-none focus:ring-2 focus:ring-emerald-200"
		type="submit"
	>
		Request workspace access
	</button>

	<p class="text-xs text-slate-400">
		Already provisioned?
		<a class="font-semibold text-sky-600 hover:text-sky-700" href="/login">Return to sign-in</a>
	</p>
</form>
