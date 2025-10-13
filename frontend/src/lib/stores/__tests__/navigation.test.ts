import { describe, expect, it, afterEach } from 'vitest';
import { get, type Readable } from 'svelte/store';
import { navigationSections } from '$lib/navigation/data';
import {
	navigationState,
	navigationSectionsStore,
	commandResults
} from '../navigation';

type NavigationReadable<T> = Readable<T>;

const readState = () => get(navigationState as unknown as NavigationReadable<any>);

afterEach(() => {
	navigationState.reset();
	navigationSectionsStore.set(navigationSections);
});

describe('navigationState store', () => {
	it('toggles the sidebar visibility', () => {
		expect(readState().sidebarOpen).toBe(false);

		navigationState.toggleSidebar();
		expect(readState().sidebarOpen).toBe(true);

		navigationState.closeSidebar();
		expect(readState().sidebarOpen).toBe(false);
	});

	it('manages command palette visibility and query', () => {
		navigationState.openCommandPalette();
		expect(readState().commandOpen).toBe(true);
		expect(readState().commandQuery).toBe('');

		navigationState.setCommandQuery('reports');
		expect(readState().commandQuery).toBe('reports');

		navigationState.closeCommandPalette();
		const state = readState();
		expect(state.commandOpen).toBe(false);
		expect(state.commandQuery).toBe('');
	});

	it('tracks the active path', () => {
		navigationState.setActivePath('/reports');
		expect(readState().activePath).toBe('/reports');
	});

	it('manages expanded navigation groups', () => {
		expect(readState().expanded).toEqual({});

		navigationState.setExpanded('settings', true);
		expect(readState().expanded).toEqual({ settings: true });

		navigationState.toggleExpanded('settings');
		expect(readState().expanded).toEqual({});
	});
});

describe('commandResults derived store', () => {
	it('returns all items when the query is empty', () => {
		navigationSectionsStore.set([
			{
				title: 'Test',
				items: [
					{ title: 'Dashboard', href: '/dashboard', icon: 'grid' },
					{ title: 'Reports', href: '/reports', icon: 'file' }
				]
			}
		]);
		navigationState.setCommandQuery('');

		expect(get(commandResults).map((item) => item.title)).toEqual(['Dashboard', 'Reports']);
	});

	it('filters items case-insensitively using title or href', () => {
		navigationSectionsStore.set([
			{
				title: 'Test',
				items: [
					{ title: 'Dashboard', href: '/dashboard', icon: 'grid' },
					{ title: 'Terraform Reports', href: '/reports', icon: 'file' }
				]
			}
		]);

		navigationState.setCommandQuery('reports');
		expect(get(commandResults).map((item) => item.title)).toEqual(['Terraform Reports']);

		navigationState.setCommandQuery('/dash');
		expect(get(commandResults).map((item) => item.title)).toEqual(['Dashboard']);
	});
});
