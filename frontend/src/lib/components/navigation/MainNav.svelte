<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Icon from './Icon.svelte';
	import type { NavigationItem, NavigationSection } from '$lib/navigation/types';

	interface Props {
		sections: NavigationSection[];
		activePath?: string;
		expanded?: Record<string, boolean>;
	}

	const { sections, activePath = '', expanded = {} }: Props = $props();

	const dispatch = createEventDispatcher<{ navigate: { href: string }; toggleSection: { key: string; open: boolean } }>();
	let lazyChildren = $state<Record<string, NavigationItem[]>>({});
	let loadingKeys = $state<Record<string, boolean>>({});

	const itemKey = (item: NavigationItem) => item.id ?? item.href ?? item.title;

	const handleNavigate = (href: string | undefined, event: MouseEvent) => {
		if (!href) return;
		event.preventDefault();
		dispatch('navigate', { href });
	};

	const isActive = (href: string | undefined) => {
		if (!href) return false;
		return activePath === href || (href !== '/' && activePath.startsWith(href));
	};

	const resolveChildItems = (item: NavigationItem) => {
		const key = itemKey(item);
		if (item.items && item.items.length) {
			return item.items;
		}
		return lazyChildren[key] ?? [];
	};

	const isExpanded = (item: NavigationItem) => {
		const key = itemKey(item);
		if (expanded[key] !== undefined) {
			return expanded[key];
		}
		return Boolean(item.items?.length);
	};

	const isLoadingChildren = (item: NavigationItem) => {
		const key = itemKey(item);
		return Boolean(loadingKeys[key]);
	};

	const loadLazyChildren = async (item: NavigationItem) => {
		if (!item.lazyImport) return;
		const key = itemKey(item);
		if (lazyChildren[key] || loadingKeys[key]) {
			return;
		}
		loadingKeys = { ...loadingKeys, [key]: true };
		try {
			const children = await item.lazyImport();
			lazyChildren = { ...lazyChildren, [key]: children };
		} catch (error) {
			console.warn('Failed to load navigation items', error);
		} finally {
			loadingKeys = { ...loadingKeys, [key]: false };
		}
	};
</script>

<nav class="space-y-6">
	{#each sections as section (section.title)}
		<section class="space-y-2">
			<h2 class="px-3 text-xs font-semibold uppercase tracking-[0.25em] text-blueGray-400">
				{section.title}
			</h2>
			<ul class="space-y-1">
				{#each section.items as item (item.title)}
					<li>
						{#if item.items?.length || item.lazyImport}
							<details
								class="group"
								open={isExpanded(item) ? true : undefined}
								ontoggle={(event) => {
									const element = event.currentTarget as HTMLDetailsElement;
									const key = itemKey(item);
									dispatch('toggleSection', { key, open: element.open });
									if (element.open) {
										void loadLazyChildren(item);
									}
								}}
							>
								<summary class="flex cursor-pointer items-center justify-between rounded-2xl px-3 py-2 text-sm font-semibold text-blueGray-500 transition hover:bg-lightBlue-50 hover:text-lightBlue-600">
									<span class="flex items-center gap-3">
										<span class="flex h-9 w-9 items-center justify-center rounded-xl bg-blueGray-100 text-sm font-semibold text-lightBlue-500 transition group-open:bg-lightBlue-500 group-open:text-white">
											<Icon name={item.icon} size={16} />
										</span>
										<span>{item.title}</span>
									</span>
									<span class="text-blueGray-300 group-open:rotate-90 transition">›</span>
								</summary>
								<ul class="mt-1 space-y-1 pl-11">
									{#if isLoadingChildren(item)}
										<li class="rounded-xl px-3 py-2 text-xs text-blueGray-400">Loading…</li>
									{:else if resolveChildItems(item).length}
										{#each resolveChildItems(item) as child (child.title)}
											<li>
												<a
													class={`flex items-center justify-between rounded-xl px-3 py-1.5 text-xs font-medium transition hover:bg-lightBlue-50 hover:text-lightBlue-600 ${
														isActive(child.href) ? 'bg-lightBlue-50 text-lightBlue-600' : 'text-blueGray-500'
													}`}
													href={child.href}
													onclick={(event) => handleNavigate(child.href, event)}
												>
													<span class="flex items-center gap-2">
														<Icon name={child.icon} size={14} class="text-blueGray-400" />
														{child.title}
													</span>
													{#if child.label}
														<span class="rounded-full bg-blueGray-100 px-2 py-[2px] text-[0.6rem] font-semibold uppercase tracking-[0.2em] text-blueGray-500">
															{child.label}
														</span>
													{/if}
												</a>
											</li>
										{/each}
									{:else}
										<li class="rounded-xl px-3 py-2 text-xs text-blueGray-300">No items available.</li>
									{/if}
								</ul>
							</details>
						{:else}
							<a
								class={`group flex items-center gap-3 rounded-2xl px-3 py-2 text-sm font-semibold transition ${
									isActive(item.href)
										? 'bg-lightBlue-50 text-lightBlue-600'
										: 'text-blueGray-500 hover:bg-lightBlue-50 hover:text-lightBlue-600'
								}`}
								href={item.href}
								onclick={(event) => handleNavigate(item.href, event)}
							>
								<span class="flex h-9 w-9 items-center justify-center rounded-xl bg-blueGray-100 text-sm font-semibold text-lightBlue-500 transition group-hover:bg-lightBlue-500 group-hover:text-white">
									<Icon name={item.icon} />
								</span>
								<span class="flex-1">{item.title}</span>
								{#if item.label}
									<span class="rounded-full bg-blueGray-100 px-2 py-[2px] text-[0.6rem] font-semibold uppercase tracking-[0.2em] text-blueGray-500">
										{item.label}
									</span>
								{/if}
							</a>
						{/if}
					</li>
				{/each}
			</ul>
		</section>
	{/each}
</nav>
