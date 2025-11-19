import type { NavigationSection } from './types';

export const navigationSections: NavigationSection[] = [
	{
		title: 'Workbench',
		items: [
			{ title: 'Dashboard', href: '/dashboard', icon: 'grid' },
			{ title: 'Projects', href: '/projects', icon: 'folder-tree' },
			{ title: 'Knowledge', href: '/knowledge', icon: 'book-open', label: 'New' }
		]
	},
	{
		title: 'Workspace',
		items: [
			{
				title: 'Settings',
				icon: 'sliders-horizontal',
				lazyImport: async () => (await import('./lazy/settings')).loadSettingsNavigation()
			}
		]
	}
];
