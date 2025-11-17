<script lang="ts">
	import { createEventDispatcher, onDestroy, onMount, tick } from 'svelte';
	import { navigationSectionsStore, navigationState, commandResults } from '$lib/stores/navigation';
	import { projectState } from '$lib/stores/project';
	import type { NavigationItem, NavigationSection } from '$lib/navigation/types';
	import type { ProjectSummary } from '$lib/api/client';

	interface Props {
		sections: NavigationSection[];
		project?: ProjectSummary | null;
	}

	const { sections, project = null }: Props = $props();

	navigationSectionsStore.set(sections);
	projectState.reset();
	if (project) {
		projectState.upsertProject(project);
		projectState.setActiveProject(project.id);
	}

	const dispatch = createEventDispatcher<{ select: { href: string } }>();
	let commandInput = $state<HTMLInputElement | null>(null);
	let commandDialog = $state<HTMLDivElement | null>(null);
	let previouslyFocused: HTMLElement | null = null;

	const actionableItems = $derived(
		$commandResults.filter(
			(item): item is NavigationItem & { href: string } => Boolean(item.href)
		)
	);
	const commandKey = (item: NavigationItem) => `${item.href ?? 'nohref'}::${item.title}`;
	const firstHref = $derived(actionableItems[0]?.href);

	const focusableSelector =
		'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

	const restoreFocus = async () => {
		const target = previouslyFocused;
		previouslyFocused = null;
		if (target && typeof target.focus === 'function') {
			await tick();
			target.focus();
		}
	};

	const openCommandPalette = async () => {
		previouslyFocused = document.activeElement as HTMLElement | null;
		navigationState.openCommandPalette();
		await tick();
		commandInput?.focus();
	};

	const closeCommandPalette = () => {
		navigationState.closeCommandPalette();
		void restoreFocus();
	};

	const handleCommandSelect = (href: string | undefined) => {
		if (!href) return;
		closeCommandPalette();
		dispatch('select', { href });
	};

	const handleCommandInputKeydown = (event: KeyboardEvent) => {
		if (event.key === 'Enter') {
			event.preventDefault();
			handleCommandSelect(firstHref);
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

	onMount(() => {
		const handler = (event: KeyboardEvent) => {
			const meta = event.metaKey || event.ctrlKey;
			const commandOpen = $navigationState.commandOpen;
			if (!commandOpen && meta && event.key.toLowerCase() === 'k') {
				event.preventDefault();
				void openCommandPalette();
			} else if (commandOpen && event.key === 'Escape') {
				event.preventDefault();
				closeCommandPalette();
			}
		};
		window.addEventListener('keydown', handler);
		return () => {
			window.removeEventListener('keydown', handler);
		};
	});

	onDestroy(() => {
		navigationState.reset();
		navigationSectionsStore.set(sections);
		projectState.reset();
	});
</script>

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
					onkeydown={handleCommandInputKeydown}
				/>
			</div>
			<div class="mt-4 max-h-60 overflow-auto rounded-2xl border border-slate-200 bg-white" data-testid="command-results">
				{#if actionableItems.length}
						<ul class="divide-y divide-slate-100 text-sm text-slate-600">
							{#each actionableItems as item (commandKey(item))}
								<li>
									<button
									class="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-sky-50 hover:text-sky-600"
									type="button"
									onclick={() => handleCommandSelect(item.href)}
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
