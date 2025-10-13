<script lang="ts">
	import { enhance } from '$app/forms';

const { form } = $props();
let email = $state(form?.values?.email ?? '');
let password = $state('');

	$effect(() => {
		const nextEmail = form?.values?.email;
		if (nextEmail !== undefined && nextEmail !== email) {
			email = nextEmail;
		}
	});
</script>

<form class="space-y-8" method="POST" use:enhance>
<div class="space-y-2">
    <h2 class="text-3xl font-semibold text-blueGray-700">Welcome back 👋</h2>
    <p class="text-sm text-blueGray-500">
        Sign in with your Terraform Manager account email and password. Legacy API tokens still work while you migrate.
    </p>
</div>

	{#if form?.error}
		<div class="rounded-2xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700">
			{form.error}
		</div>
	{/if}

	<div class="space-y-6">
		<label class="block space-y-2 text-sm font-medium text-blueGray-600">
			<span>Email</span>
			<input
				class="w-full rounded-2xl border border-blueGray-300 bg-white px-4 py-3 text-base text-blueGray-700 shadow-inner shadow-blueGray-200 focus:border-lightBlue-400 focus:outline-none focus:ring-2 focus:ring-lightBlue-200"
				type="email"
				name="email"
				placeholder="you@example.com"
				bind:value={email}
				required
			/>
		</label>

    <label class="block space-y-2 text-sm font-medium text-blueGray-600">
        <span>Password or API Token</span>
        <input
            class="w-full rounded-2xl border border-blueGray-300 bg-white px-4 py-3 text-base text-blueGray-700 shadow-inner shadow-blueGray-200 focus:border-lightBlue-400 focus:outline-none focus:ring-2 focus:ring-lightBlue-200"
            type="password"
            name="password"
            placeholder="Enter your password"
            bind:value={password}
        />
        <p class="text-xs text-blueGray-400">
            Hint: if <code class="rounded bg-blueGray-200 px-1 py-0.5 text-xs text-blueGray-600">TFM_API_TOKEN</code> is still configured, paste it here
            until your password is provisioned.
        </p>
    </label>
	</div>

	<button
		class="inline-flex w-full items-center justify-center rounded-2xl bg-gradient-to-r from-lightBlue-500 via-indigo-500 to-blue-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-lightBlue-300/50 transition hover:from-lightBlue-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-lightBlue-200"
		type="submit"
	>
		Sign in
	</button>

	<div class="flex flex-col gap-2 text-xs text-blueGray-400 sm:flex-row sm:items-center sm:justify-between">
		<a class="font-semibold text-lightBlue-600 hover:text-lightBlue-700" href="/forgot-password">Forgot token?</a>
		<div>
			New here?
			<a class="font-semibold text-lightBlue-600 hover:text-lightBlue-700" href="/register">Create workspace access</a>
		</div>
	</div>
</form>
