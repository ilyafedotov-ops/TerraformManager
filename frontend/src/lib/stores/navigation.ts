import { derived, writable } from 'svelte/store';
import type { NavigationSection, NavigationItem } from '$lib/navigation/types';
import { navigationSections } from '$lib/navigation/data';
import { activeProject } from '$lib/stores/project';

export interface NavigationState {
	sidebarOpen: boolean;
	commandOpen: boolean;
	commandQuery: string;
	activePath: string;
	expanded: Record<string, boolean>;
}

const initialState: NavigationState = {
	sidebarOpen: false,
	commandOpen: false,
	commandQuery: '',
	activePath: '',
	expanded: {}
};

const flattenItems = (sections: NavigationSection[]): NavigationItem[] => {
	const result: NavigationItem[] = [];
	for (const section of sections) {
		for (const item of section.items) {
			result.push(item);
			if (item.items) {
				result.push(...item.items);
			}
		}
	}
	return result;
};

function createNavigationStore() {
	const { subscribe, update, set } = writable<NavigationState>(initialState);

	return {
		subscribe,
		setActivePath(path: string) {
			update((state) => ({ ...state, activePath: path }));
		},
		toggleSidebar() {
			update((state) => ({ ...state, sidebarOpen: !state.sidebarOpen }));
		},
		closeSidebar() {
			update((state) => ({ ...state, sidebarOpen: false }));
		},
		openCommandPalette() {
			update((state) => ({ ...state, commandOpen: true, commandQuery: '' }));
		},
		closeCommandPalette() {
			update((state) => ({ ...state, commandOpen: false, commandQuery: '' }));
		},
		setCommandQuery(value: string) {
			update((state) => ({ ...state, commandQuery: value }));
		},
		setExpanded(key: string, expanded: boolean) {
			update((state) => ({
				...state,
				expanded: expanded
					? { ...state.expanded, [key]: true }
					: Object.fromEntries(Object.entries(state.expanded).filter(([entryKey]) => entryKey !== key))
			}));
		},
		toggleExpanded(key: string) {
			update((state) => {
				const next = { ...state.expanded };
				if (next[key]) {
					delete next[key];
				} else {
					next[key] = true;
				}
				return { ...state, expanded: next };
			});
		},
		reset() {
			set(initialState);
		}
	};
}

export const navigationState = createNavigationStore();

export const navigationSectionsStore = writable(navigationSections);

const resolveNavigationItem = (item: NavigationItem, projectId: string | null): NavigationItem => {
	const resolved: NavigationItem = { ...item };
	if (item.projectScoped) {
		if (projectId) {
			resolved.href = item.projectPath?.replace('{projectId}', projectId) ?? `/projects/${projectId}`;
		} else {
			resolved.href = '/projects';
		}
	}
	if (item.items?.length) {
		resolved.items = item.items.map((child) => resolveNavigationItem(child, projectId));
	}
	return resolved;
};

export const materialiseNavigationSections = (
	sections: NavigationSection[],
	projectId: string | null
): NavigationSection[] =>
	sections.map((section) => ({
		title: section.title,
		items: section.items.map((item) => resolveNavigationItem(item, projectId))
	}));

export const commandResults = derived(
	[navigationSectionsStore, navigationState, activeProject],
	([$sections, $state, $activeProject]) => {
		const resolvedSections = materialiseNavigationSections($sections, $activeProject?.id ?? null);
		const allItems = flattenItems(resolvedSections);
		const query = $state.commandQuery.trim().toLowerCase();
		if (!query) {
			return allItems;
		}
		return allItems.filter((item) => {
			if (item.title.toLowerCase().includes(query)) {
				return true;
			}
			return item.href?.toLowerCase().includes(query);
		});
	}
);
