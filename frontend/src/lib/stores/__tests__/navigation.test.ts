import { describe, expect, it, afterEach } from 'vitest';
import { get, type Readable } from 'svelte/store';
import { navigationSections } from '$lib/navigation/data';
import { navigationState, navigationSectionsStore, commandResults } from '../navigation';
import { projectState } from '$lib/stores/project';

type NavigationReadable<T> = Readable<T>;

const readState = () => get(navigationState as unknown as NavigationReadable<any>);

afterEach(() => {
	navigationState.reset();
	navigationSectionsStore.set(navigationSections);
	projectState.reset();
});

const seedProject = (id = 'proj-123') => {
	projectState.upsertProject({
		id,
		name: 'Workspace',
		slug: 'workspace',
		root_path: '.'
	});
	projectState.setActiveProject(id);
};

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
		navigationState.setActivePath('/projects/test-project/reports');
		expect(readState().activePath).toBe('/projects/test-project/reports');
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
					{
						title: 'Dashboard',
						icon: 'grid',
						projectScoped: true,
						projectPath: '/projects/{projectId}/dashboard'
					},
					{ title: 'Knowledge', href: '/knowledge', icon: 'book' }
				]
			}
		]);
		seedProject();
		navigationState.setCommandQuery('');

		expect(get(commandResults).map((item) => item.href)).toEqual([
			'/projects/proj-123/dashboard',
			'/knowledge'
		]);
	});

	it('filters items case-insensitively using title or href', () => {
		navigationSectionsStore.set([
			{
				title: 'Test',
				items: [
					{
						title: 'Dashboard',
						icon: 'grid',
						projectScoped: true,
						projectPath: '/projects/{projectId}/dashboard'
					},
					{
						title: 'Terraform Reports',
						icon: 'file',
						projectScoped: true,
						projectPath: '/projects/{projectId}/reports'
					}
				]
			}
		]);
		seedProject();

		navigationState.setCommandQuery('reports');
		expect(get(commandResults).map((item) => item.title)).toEqual(['Terraform Reports']);

		navigationState.setCommandQuery('/projects/proj-123/dash');
		expect(get(commandResults).map((item) => item.title)).toEqual(['Dashboard']);
	});

	it('falls back to /projects when no project is active', () => {
		navigationSectionsStore.set([
			{
				title: 'Test',
				items: [
					{
						title: 'Dashboard',
						icon: 'grid',
						projectScoped: true,
						projectPath: '/projects/{projectId}/dashboard'
					}
				]
			}
		]);
		projectState.reset();
		navigationState.setCommandQuery('');

		expect(get(commandResults).map((item) => item.href)).toEqual(['/projects']);
	});
});
