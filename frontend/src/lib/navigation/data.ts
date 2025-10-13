import type { NavigationSection } from './types';

export const navigationSections: NavigationSection[] = [
	{
		title: 'Workbench',
		items: [
			{ title: 'Dashboard', href: '/dashboard', icon: 'grid' },
			{ title: 'Generate', href: '/generate', icon: 'sparkles', label: 'Beta' },
			{ title: 'Review', href: '/review', icon: 'upload-cloud', label: 'Core' },
			{ title: 'Reports', href: '/reports', icon: 'file-bar-chart-2' },
			{ title: 'Configs', href: '/configs', icon: 'settings-2' },
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
