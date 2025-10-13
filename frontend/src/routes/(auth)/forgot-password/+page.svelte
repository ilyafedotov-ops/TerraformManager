<script lang="ts">
	import { enhance } from '$app/forms';
	import { browser } from '$app/environment';
	import { notifySuccess } from '$lib/stores/notifications';

	const { form } = $props();
	let email = $state(form?.values?.email ?? '');
	let lastMessage = $state<string | null>(null);

	$effect(() => {
		const nextEmail = form?.values?.email;
		if (nextEmail !== undefined && nextEmail !== email) {
			email = nextEmail;
		}
	});

	$effect(() => {
		const message = form?.success ? form?.message ?? null : null;
		if (!browser) return;
		if (message && message !== lastMessage) {
			notifySuccess(message, { duration: 6000 });
			lastMessage = message;
		}
	});
</script>

<form class="space-y-8" method="POST" use:enhance>
	<div class="space-y-2">
		<h2 class="text-3xl font-semibold text-slate-700">Recover API token</h2>
		<p class="text-sm text-slate-500">
			Enter your work email and we&rsquo;ll send the latest onboarding instructions. Automated delivery will hook into
			your identity provider later in the migration, but this keeps the workflow in-product today.
		</p>
	</div>

	{#if form?.error}
		<div class="rounded-2xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700">
			{form.error}
		</div>
	{/if}

	{#if form?.success && form.message}
		<div class="rounded-2xl border border-violet-300 bg-violet-50 px-4 py-3 text-sm text-violet-700">
			{form.message}
		</div>
	{/if}

	<div class="space-y-6">
		<label class="block space-y-2 text-sm font-medium text-slate-600">
			<span>Email</span>
			<input
				class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
				type="email"
				name="email"
				placeholder="security@company.com"
				bind:value={email}
				required
			/>
		</label>
	</div>

	<button
		class="inline-flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-violet-500 via-indigo-500 to-purple-500 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-violet-300/40 transition hover:from-violet-400 hover:via-indigo-400 hover:to-purple-400 focus:outline-none focus:ring-2 focus:ring-violet-200"
		type="submit"
	>
		Send recovery email
	</button>

	<p class="text-xs text-slate-400">
		Remembered your token?
		<a class="font-semibold text-sky-600 hover:text-sky-700" href="/login">Back to sign-in</a>
	</p>
</form>
