<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { onDestroy, onMount, tick } from 'svelte';
import { clearToken, token } from '$lib/stores/auth';
import { API_BASE, ApiError } from '$lib/api/client';
import MainNav from '$lib/components/navigation/MainNav.svelte';
import { navigationSectionsStore, navigationState, commandResults, materialiseNavigationSections } from '$lib/stores/navigation';
import { projectState, activeProject } from '$lib/stores/project';
import type { NavigationItem } from '$lib/navigation/types';

	const { children, data } = $props();

	const toMutableSection = (
		value: (typeof data)['section']
	): { title: string; subtitle?: string | null; breadcrumbs?: Array<{ href: string; label: string }> } | null => {
		if (!value) {
			return null;
		}

		return {
			...value,
			breadcrumbs: value.breadcrumbs ? [...value.breadcrumbs] : undefined
		};
	};

	let currentToken = $state<string | null>(data.token ?? null);
	let profile = $state<{ email: string; scopes: string[]; expiresIn: number } | null>(data.user ?? null);
	let section = $state<{ title: string; subtitle?: string | null; breadcrumbs?: Array<{ href: string; label: string }> } | null>(
		toMutableSection(data.section ?? null)
	);
let unsubscribe: (() => void) | null = null;
let lastServerToken = $state<string | null>(data.token ?? null);
let commandInput = $state<HTMLInputElement | null>(null);
let commandDialog = $state<HTMLDivElement | null>(null);
let previouslyFocused: HTMLElement | null = null;
let redirectingToLogin = false;
let headerSearchInput = $state<HTMLInputElement | null>(null);
let headerSearchDropdown = $state<HTMLDivElement | null>(null);
let showHeaderSearch = $state(false);
let headerSearchQuery = $state('');

const redirectToLogin = () => {
	if (!browser || redirectingToLogin) {
		return;
	}
	redirectingToLogin = true;
	const currentPath = window.location.pathname + window.location.search;
	const redirectTarget = currentPath && currentPath !== '/' ? currentPath : '/projects';
	void goto(`/login?redirect=${encodeURIComponent(redirectTarget)}`, { replaceState: true });
};

const handleProjectStoreError = (error: unknown, label: string) => {
	console.error(label, error);
	if (error instanceof ApiError && error.status === 401) {
		clearToken();
		if (browser) {
			document.cookie = 'tm_refresh_csrf=; Path=/; Max-Age=0; SameSite=Lax';
		}
		redirectToLogin();
	}
};

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
		} else if (browser && currentToken) {
			token.set(currentToken);
		}

		if (!browser) {
			return;
		}

		const handler = (event: KeyboardEvent) => {
			const meta = event.metaKey || event.ctrlKey;
			const commandOpen = $navigationState.commandOpen;
			if (!commandOpen && meta && event.key.toLowerCase() === 'k') {
				event.preventDefault();
				void openCommandPalette();
			} else if (commandOpen && event.key === 'Escape') {
				event.preventDefault();
				closeCommandPalette();
			} else if (showHeaderSearch && event.key === 'Escape') {
				event.preventDefault();
				closeHeaderSearch();
			}
		};

		const clickHandler = (event: MouseEvent) => {
			if (showHeaderSearch && headerSearchDropdown && headerSearchInput) {
				const target = event.target as Node;
				if (!headerSearchDropdown.contains(target) && !headerSearchInput.contains(target)) {
					closeHeaderSearch();
				}
			}
		};

		window.addEventListener('keydown', handler);
		window.addEventListener('click', clickHandler);
		return () => {
			window.removeEventListener('keydown', handler);
			window.removeEventListener('click', clickHandler);
		};
	});

	$effect(() => {
		const nextToken = data.token ?? null;
		if (nextToken === lastServerToken) {
			return;
		}

		lastServerToken = nextToken;
		currentToken = nextToken;

		if (!browser) {
			return;
		}

		if (nextToken) {
			token.set(nextToken);
		} else {
			clearToken();
		}
	});

	$effect(() => {
		if (data.user !== undefined) {
			profile = data.user ?? null;
		}
	});

	$effect(() => {
		if (data.section !== undefined) {
			section = toMutableSection(data.section ?? null);
		}
	});

	const tokenExpiryMinutes = $derived(profile ? Math.max(Math.ceil(profile.expiresIn / 60), 0) : null);
	const breadcrumbs = $derived(section?.breadcrumbs ?? []);

	$effect(() => {
		navigationState.setActivePath($page.url.pathname);
	});

	const handleSignOut = async () => {
		try {
			await fetch(`${API_BASE}/auth/logout`, {
				method: 'POST',
				headers: currentToken
					? {
						Authorization: `Bearer ${currentToken}`
					}
					: undefined,
				credentials: 'include'
			});
		} catch (error) {
			console.warn('Failed to sign out', error);
		} finally {
			clearToken();
			if (browser) {
				document.cookie = 'tm_refresh_csrf=; Path=/; Max-Age=0; SameSite=Lax';
			}
			goto('/login', { replaceState: true });
		}
	};

	const focusableSelector =
		'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

	const restoreFocus = async () => {
		if (!browser) return;
		const target = previouslyFocused;
		previouslyFocused = null;
		if (target && typeof target.focus === 'function') {
			await tick();
			target.focus();
		}
	};

	const openCommandPalette = async () => {
		if (browser) {
			previouslyFocused = document.activeElement as HTMLElement | null;
		}
		navigationState.openCommandPalette();
		await tick();
		commandInput?.focus();
	};

	const closeCommandPalette = () => {
		navigationState.closeCommandPalette();
		if (browser) {
			void restoreFocus();
		}
	};

	const handleCommandSelect = async (href: string | undefined) => {
		if (!href) return;
		closeCommandPalette();
		await goto(href, { replaceState: false });
		navigationState.setActivePath(href);
	};

	const handleCommandInputKeydown = (event: KeyboardEvent, firstHref: string | undefined) => {
		if (event.key === 'Enter') {
			event.preventDefault();
			void handleCommandSelect(firstHref);
		} else if (event.key === 'Escape') {
			event.preventDefault();
			closeCommandPalette();
		}
	};

	const handleDialogKeydown = (event: KeyboardEvent) => {
		if (event.key === 'Tab') {
			if (!commandDialog) return;
			const focusable = Array.from(
				commandDialog.querySelectorAll<HTMLElement>(focusableSelector)
			).filter((element) => !element.hasAttribute('disabled') && element.getAttribute('tabindex') !== '-1');
			if (!focusable.length) {
				event.preventDefault();
				return;
			}
			const first = focusable[0];
			const last = focusable[focusable.length - 1];
			const active = document.activeElement as HTMLElement | null;
			if (event.shiftKey) {
				if (!active || active === first || !commandDialog.contains(active)) {
					event.preventDefault();
					last.focus();
				}
			} else if (active === last) {
				event.preventDefault();
				first.focus();
			}
		} else if (event.key === 'Escape') {
			event.preventDefault();
			closeCommandPalette();
		}
	};

const actionableCommandItems = $derived(
	$commandResults.filter(
		(item): item is NavigationItem & { href: string } => Boolean(item.href)
	)
);
const commandItemKey = (item: NavigationItem) => `${item.href ?? 'nohref'}::${item.title}`;
const firstCommandHref = $derived(actionableCommandItems[0]?.href);

const headerSearchResults = $derived(() => {
	const query = headerSearchQuery.trim().toLowerCase();
	if (!query) return [];

	const allItems = materialiseNavigationSections($navigationSectionsStore, $activeProject?.id ?? null)
		.flatMap(section => section.items);

	return allItems
		.filter((item): item is NavigationItem & { href: string } =>
			Boolean(item.href) && item.title.toLowerCase().includes(query)
		)
		.slice(0, 8);
});

const projectNavigationSections = $derived(
	materialiseNavigationSections($navigationSectionsStore, $activeProject?.id ?? null)
);
type QuickAction = { id: string; label: string; href: string };
const projectSlugPath = $derived($activeProject?.slug ?? null);
const projectQuickActions = $derived<QuickAction[]>(
	(() => {
		const slug = projectSlugPath;
		if (!slug) {
			return [];
		}
		return [
			{ id: 'run-scan', label: 'Start scan', href: `/projects?project=${slug}&tab=review` },
			{ id: 'generate', label: 'Generate config', href: `/projects?project=${slug}&tab=generate` },
			{ id: 'view-reports', label: 'View reports', href: `/projects?project=${slug}&tab=reports` }
		];
	})()
);

const handleNavNavigate = async (event: CustomEvent<{ href: string }>) => {
	const { href } = event.detail;
	await goto(href, { replaceState: false });
	navigationState.setActivePath(href);
	navigationState.closeSidebar();
};

const handleQuickAction = async (href: string) => {
	if (!href) return;
	await goto(href, { replaceState: false });
	navigationState.setActivePath(href);
};

	let projectsInitialised = false;
	let lastRunsProjectId: string | null = null;

	$effect(() => {
		if (!browser) {
			return;
		}
		if (!currentToken) {
			projectsInitialised = false;
			projectState.reset();
			return;
		}
	if (!projectsInitialised) {
			projectsInitialised = true;
			void projectState.loadProjects(fetch, currentToken).catch((err) => {
				handleProjectStoreError(err, 'Failed to load projects');
			});
		}
	});

	$effect(() => {
		if (!browser || !currentToken) {
			return;
		}
		const projectId = $activeProject?.id ?? null;
		if (!projectId) {
			lastRunsProjectId = null;
			return;
		}
		if (projectId === lastRunsProjectId) {
			return;
		}
		lastRunsProjectId = projectId;
		void projectState.refreshRuns(fetch, currentToken, projectId, 10).catch((err) => {
			handleProjectStoreError(err, 'Failed to load project runs');
		});
	});

const handleProjectChange = async (event: Event) => {
	const select = event.target as HTMLSelectElement;
	const projectId = select.value || null;
	projectState.setActiveProject(projectId);
	if (projectId && browser && currentToken) {
		await projectState.refreshRuns(fetch, currentToken, projectId, 10).catch((err) => {
			handleProjectStoreError(err, 'Failed to refresh runs');
		});
		const slug = projectState.getProjectSlug(projectId);
		await goto(slug ? `/projects?project=${slug}&tab=overview` : '/projects', { replaceState: false });
	}
};

	const handleReloadProjects = async () => {
		if (!browser || !currentToken) return;
		await projectState.loadProjects(fetch, currentToken).catch((err) => {
			handleProjectStoreError(err, 'Failed to reload projects');
		});
	};

	const closeHeaderSearch = () => {
		showHeaderSearch = false;
		headerSearchQuery = '';
	};

	const handleHeaderSearchInput = (event: Event) => {
		const input = event.target as HTMLInputElement;
		headerSearchQuery = input.value;
		showHeaderSearch = headerSearchQuery.trim().length > 0;
	};

	const handleHeaderSearchSelect = async (href: string) => {
		closeHeaderSearch();
		await goto(href, { replaceState: false });
		navigationState.setActivePath(href);
	};

	const handleHeaderSearchKeydown = (event: KeyboardEvent) => {
		const results = headerSearchResults();
		if (event.key === 'Enter' && results.length > 0) {
			event.preventDefault();
			void handleHeaderSearchSelect(results[0].href);
		} else if (event.key === 'Escape') {
			event.preventDefault();
			closeHeaderSearch();
		}
	};
</script>

<div class="flex min-h-screen bg-slate-100 text-slate-700">
	<button
		class="fixed left-4 top-4 z-40 inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 shadow-lg shadow-slate-300 transition hover:text-slate-700 lg:hidden"
		type="button"
		onclick={() => navigationState.toggleSidebar()}
		aria-label="Toggle navigation"
	>
		<span class="sr-only">Toggle navigation</span>
		{#if $navigationState.sidebarOpen}
			&times;
		{:else}
			&#9776;
		{/if}
	</button>

	<aside
		class="fixed inset-y-0 left-0 z-30 w-72 transform space-y-6 overflow-y-auto border-r border-slate-200 bg-white px-6 py-10 shadow-xl shadow-slate-300 transition duration-200 ease-out lg:translate-x-0 lg:opacity-100"
		class:translate-x-0={$navigationState.sidebarOpen}
		class:-translate-x-full={!$navigationState.sidebarOpen}
	>
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3 text-lg font-semibold uppercase tracking-[0.4em] text-slate-400">
				<span class="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500 text-xl font-semibold text-white shadow-lg shadow-sky-200">
					TF
				</span>
				<span class="flex flex-col gap-0 leading-tight">
					<span class="text-xs text-slate-400">Terraform</span>
					<span class="text-sm text-slate-700">Manager</span>
				</span>
			</div>
		</div>

		<div class="space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-500">
			<div class="flex items-center justify-between gap-2">
				<div>
					<p class="font-semibold uppercase tracking-[0.3em] text-slate-400">Project</p>
					<p class="mt-1 text-sm font-semibold text-slate-700">
						{$activeProject?.name ?? 'No project selected'}
					</p>
				</div>
				<button
					type="button"
					class="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-2 py-1 text-[0.65rem] font-semibold uppercase tracking-[0.25em] text-slate-500 transition hover:bg-slate-100"
					onclick={() => void handleReloadProjects()}
					aria-label="Reload projects"
				>
					↻
				</button>
			</div>

			<select
				class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
				onchange={handleProjectChange}
				value={$activeProject?.id ?? ''}
				aria-label="Select project"
			>
				<option value="">Select a project…</option>
				{#each $projectState.projects as project (project.id)}
					<option value={project.id}>
						{project.name}
					</option>
				{/each}
			</select>

			{#if $projectState.error}
				<p class="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-600">
					{$projectState.error}
				</p>
			{/if}

				{#if $projectState.projects.length === 0 && !$projectState.loading}
					<p class="rounded-xl bg-white px-3 py-2 text-xs text-slate-500">
						Use the Projects page to create a workspace and start tracking runs.
					</p>
				{/if}
			{#if projectQuickActions.length}
				<div class="flex flex-wrap gap-2 pt-2">
					{#each projectQuickActions as action}
						<button
							type="button"
							class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500 transition hover:border-sky-200 hover:text-sky-600"
							onclick={() => void handleQuickAction(action.href)}
						>
							{action.label}
						</button>
					{/each}
				</div>
			{/if}
		</div>

	<MainNav
		sections={projectNavigationSections}
		activePath={$navigationState.activePath}
		expanded={$navigationState.expanded}
		on:navigate={handleNavNavigate}
		on:toggleSection={(event) => navigationState.setExpanded(event.detail.key, event.detail.open)}
	/>

		<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-500">
			<p class="font-semibold uppercase tracking-[0.3em] text-slate-400">Environment</p>
			<p class="mt-2 font-mono text-slate-600">Local Development</p>
			<p class="mt-2 text-slate-500">
				API server:
				<code class="rounded border border-slate-200 bg-white px-1 py-0.5 text-slate-600">{API_BASE}</code>
			</p>
		</div>
	</aside>

	<div class="flex flex-1 flex-col lg:ml-72">
		<header class="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/90 px-6 py-5 backdrop-blur">
			<div class="space-y-1">
				{#if breadcrumbs.length}
					<nav class="flex items-center gap-2 text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-slate-400">
						{#each breadcrumbs as crumb, index (crumb.href)}
							<a class="text-slate-400 hover:text-slate-600" href={crumb.href}>{crumb.label}</a>
							{#if index < breadcrumbs.length - 1}
								<span aria-hidden="true">/</span>
							{/if}
						{/each}
					</nav>
				{:else}
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Terraform Manager</p>
				{/if}
				<h1 class="text-2xl font-semibold text-slate-700">{section?.title ?? 'Control plane'}</h1>
				{#if section?.subtitle}
					<p class="text-xs text-slate-400">{section.subtitle}</p>
				{/if}
				{#if $activeProject}
					<p class="mt-2 text-[0.7rem] text-slate-500">
						Active project:
						<span class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600">
							{$activeProject.name}
							{#if $activeProject.slug}
								<span class="text-[0.6rem] uppercase tracking-[0.2em] text-slate-400">{$activeProject.slug}</span>
							{/if}
						</span>
					</p>
				{/if}
			</div>
			<div class="flex items-center gap-3">
				<div class="hidden flex-col items-end text-right text-xs text-slate-400 sm:flex">
					<span class="uppercase tracking-[0.35em]">Signed in as</span>
					<span class="text-sm font-semibold text-slate-700">{profile?.email ?? 'Unknown user'}</span>
					{#if tokenExpiryMinutes !== null}
						<span class="mt-1 inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.25em] text-slate-500">
							Token renew in ~{tokenExpiryMinutes}m
						</span>
					{/if}
				</div>
				<div class="relative">
					<input
						type="text"
						bind:this={headerSearchInput}
						bind:value={headerSearchQuery}
						class="w-64 rounded-xl border border-slate-200 bg-white px-4 py-2 pr-24 text-sm text-slate-700 transition focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						class:border-sky-400={showHeaderSearch}
						class:ring-2={showHeaderSearch}
						class:ring-sky-200={showHeaderSearch}
						placeholder="Search or jump to..."
						oninput={handleHeaderSearchInput}
						onkeydown={handleHeaderSearchKeydown}
					/>
					<div class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
						<kbd class="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-semibold text-slate-400">
							{browser ? (navigator.platform.includes('Mac') ? '⌘K' : 'Ctrl+K') : 'Ctrl+K'}
						</kbd>
					</div>
					{#if showHeaderSearch}
						<div
							bind:this={headerSearchDropdown}
							class="absolute right-0 top-full z-50 mt-2 w-96 rounded-xl border border-slate-200 bg-white shadow-xl shadow-slate-900/10"
						>
							{#if headerSearchResults().length > 0}
								<ul class="divide-y divide-slate-100 text-sm text-slate-600">
									{#each headerSearchResults() as item (commandItemKey(item))}
										<li>
											<button
												class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-sky-50 hover:text-sky-600"
												type="button"
												onclick={() => void handleHeaderSearchSelect(item.href)}
											>
												<span class="font-semibold">{item.title}</span>
												<span class="text-xs uppercase tracking-[0.2em] text-slate-400">{item.href}</span>
											</button>
										</li>
									{/each}
								</ul>
							{:else}
								<p class="px-4 py-6 text-sm text-slate-400">No matching pages found.</p>
							{/if}
						</div>
					{/if}
				</div>
				<button
					type="button"
					class="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-50"
					onclick={handleSignOut}
				>
					Sign out
				</button>
				<div class="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-500 text-base font-semibold text-white shadow-md shadow-sky-200">
					{#if profile?.email}
						{profile.email.slice(0, 2).toUpperCase()}
					{:else}
						EM
					{/if}
				</div>
			</div>
		</header>

		<main class="flex-1 px-4 py-10 sm:px-6">
			<div class="mx-auto w-full max-w-[90rem]">
				{@render children?.()}
			</div>
		</main>

		<footer class="border-t border-slate-200 bg-white/70 px-6 py-6 text-xs text-slate-400">
			<div class="mx-auto flex w-full max-w-6xl items-center justify-between">
				<p>&copy; {new Date().getFullYear()} Terraform Manager</p>
				<p>
					Built with SvelteKit + Notus theme
					<span aria-hidden="true">•</span>
					<a class="font-semibold text-sky-500 hover:text-sky-600" href="/knowledge">Knowledge base</a>
				</p>
			</div>
		</footer>
	</div>

	{#if $navigationState.commandOpen}
		<div
			class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm"
			role="presentation"
			onclick={(event) => {
				if (event.target === event.currentTarget) {
					closeCommandPalette();
				}
			}}
		>
			<div
				class="w-full max-w-xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-900/20"
				role="dialog"
				aria-modal="true"
				aria-labelledby="command-palette-title"
				tabindex="-1"
				data-testid="command-palette"
				bind:this={commandDialog}
				onclick={(event) => {
					event.stopPropagation();
				}}
				onkeydown={handleDialogKeydown}
			>
				<div class="flex items-center justify-between gap-3">
					<h2 id="command-palette-title" class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">
						Command palette
					</h2>
					<button
						type="button"
						class="rounded-xl border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-500 transition hover:bg-slate-50"
						onclick={closeCommandPalette}
					>
						Close
					</button>
				</div>
				<div class="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-3">
					<input
						class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						type="search"
						placeholder="Jump to a page…"
						value={$navigationState.commandQuery}
						bind:this={commandInput}
						oninput={(event) => navigationState.setCommandQuery((event.target as HTMLInputElement).value)}
						onkeydown={(event) => handleCommandInputKeydown(event, firstCommandHref)}
					/>
					<p class="mt-2 text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-slate-400">
						Press Esc to close • {browser ? (navigator.platform.includes('Mac') ? '⌘K' : 'Ctrl+K') : 'Ctrl+K'} to open
					</p>
				</div>
				<div class="mt-4 max-h-60 overflow-auto rounded-2xl border border-slate-200 bg-white">
					{#if actionableCommandItems.length}
						<ul class="divide-y divide-slate-100 text-sm text-slate-600">
							{#each actionableCommandItems as item (commandItemKey(item))}
								<li>
									<button
										class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-sky-50 hover:text-sky-600"
										type="button"
										onclick={() => void handleCommandSelect(item.href)}
									>
										<span class="font-semibold">{item.title}</span>
										<span class="text-xs uppercase tracking-[0.2em] text-slate-400">{item.href}</span>
									</button>
								</li>
							{/each}
						</ul>
					{:else}
						<p class="px-4 py-6 text-sm text-slate-400">No matching destinations.</p>
					{/if}
				</div>
			</div>
		</div>
	{/if}
</div>
