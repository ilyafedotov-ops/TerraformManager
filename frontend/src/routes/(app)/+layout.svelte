<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { onDestroy, onMount } from 'svelte';
	import { clearToken, token } from '$lib/stores/auth';

	const { children, data } = $props();

	let sidebarOpen = $state(false);
	let currentToken = $state<string | null>(data.token ?? null);
	let unsubscribe: (() => void) | null = null;

	if (browser) {
		unsubscribe = token.subscribe((value) => {
			currentToken = value;
		});
	}

	onDestroy(() => {
		unsubscribe?.();
	});

	onMount(() => {
		if (!currentToken) {
			goto('/login');
		} else if (browser) {
			token.set(currentToken);
		}
	});

	const handleSignOut = () => {
		clearToken();
		goto('/login', { replaceState: true });
	};

	const mainNav = [
		{ href: '/dashboard', label: 'Dashboard' },
		{ href: '/generate', label: 'Generate' },
		{ href: '/review', label: 'Review' },
		{ href: '/reports', label: 'Reports' },
		{ href: '/configs', label: 'Configs' },
		{ href: '/knowledge', label: 'Knowledge' },
		{ href: '/settings/llm', label: 'Settings' }
	];
</script>

<div class="flex min-h-screen bg-slate-950 text-slate-100">
	<button
		class="fixed left-4 top-4 z-40 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-900/90 text-slate-200 shadow-lg shadow-slate-900/60 ring-1 ring-white/10 transition hover:text-white lg:hidden"
		type="button"
		onclick={() => (sidebarOpen = !sidebarOpen)}
		aria-label="Toggle navigation"
	>
		<span class="sr-only">Toggle navigation</span>
		{#if sidebarOpen}
			&times;
		{:else}
			&#9776;
		{/if}
	</button>

	<aside
		class="fixed inset-y-0 left-0 z-30 w-72 transform space-y-6 overflow-y-auto border-r border-white/5 bg-slate-950/90 px-6 py-10 shadow-2xl shadow-slate-950/60 backdrop-blur transition duration-200 ease-out lg:translate-x-0 lg:opacity-100"
		class:translate-x-0={sidebarOpen}
		class:-translate-x-full={!sidebarOpen}
	>
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3 text-lg font-semibold uppercase tracking-[0.4em] text-slate-400">
				<span class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500/40 to-indigo-500/40 text-xl font-semibold text-white">
					TF
				</span>
				<span class="flex flex-col gap-0 leading-tight">
					<span class="text-xs text-slate-500">Terraform</span>
					<span class="text-sm text-white">Manager</span>
				</span>
			</div>
		</div>

		<nav class="space-y-2">
			<h2 class="px-3 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">Workbench</h2>
			{#each mainNav as item}
				<a
					class="group flex items-center gap-3 rounded-2xl px-3 py-2 text-sm font-medium text-slate-300 transition hover:bg-slate-900/80 hover:text-white"
					href={item.href}
					onclick={() => (sidebarOpen = false)}
				>
					<span class="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900/70 text-sm font-semibold text-slate-400 transition group-hover:bg-sky-500/20 group-hover:text-sky-300">
						#
					</span>
					<span>{item.label}</span>
				</a>
			{/each}
		</nav>

		<div class="rounded-2xl border border-white/5 bg-slate-900/50 p-4 text-xs text-slate-400">
			<p class="font-semibold uppercase tracking-[0.3em] text-slate-500">Environment</p>
			<p class="mt-2 font-mono text-slate-300">Local Development</p>
			<p class="mt-2 text-slate-500">
				API server: <code class="rounded bg-slate-800 px-1 py-0.5 text-slate-300">http://localhost:8787</code>
			</p>
		</div>
	</aside>

	<div class="flex flex-1 flex-col lg:ml-72">
		<header class="sticky top-0 z-20 flex items-center justify-between border-b border-white/5 bg-slate-950/80 px-6 py-5 backdrop-blur">
			<div>
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Terraform Manager</p>
				<h1 class="text-2xl font-semibold text-white">Control plane</h1>
			</div>
			<div class="flex items-center gap-3">
				<div class="hidden flex-col text-right text-xs text-slate-500 sm:flex">
					<span class="uppercase tracking-[0.35em]">API Token</span>
					<span class="font-mono text-slate-300">
						{currentToken ? `${currentToken.slice(0, 4)}...${currentToken.slice(-4)}` : 'Not set'}
					</span>
				</div>
				<button
					type="button"
					class="rounded-2xl border border-white/10 bg-slate-900/80 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-sky-400/30 hover:text-white"
				>
					Command Palette
				</button>
				<button
					type="button"
					class="rounded-2xl border border-white/10 bg-slate-900/80 px-4 py-2 text-sm font-medium text-slate-200 transition hover:border-rose-400/40 hover:text-white"
					onclick={handleSignOut}
				>
					Sign out
				</button>
				<div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500/30 to-indigo-500/30 text-base font-semibold text-white">
					EM
				</div>
			</div>
		</header>

		<main class="flex-1 px-6 py-10">
			<div class="mx-auto w-full max-w-6xl">
				{@render children?.()}
			</div>
		</main>

		<footer class="border-t border-white/5 px-6 py-6 text-xs text-slate-500">
			<div class="mx-auto flex w-full max-w-6xl items-center justify-between">
				<p>&copy; {new Date().getFullYear()} Terraform Manager</p>
				<p>
					Built with SvelteKit + Notus theme
					<span aria-hidden="true">•</span>
					<a class="font-semibold text-sky-300 hover:text-sky-200" href="/knowledge">Knowledge base</a>
				</p>
			</div>
		</footer>
	</div>
</div>
