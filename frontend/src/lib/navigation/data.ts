import type { NavigationSection } from './types';

export const navigationSections: NavigationSection[] = [
	{
		title: 'Workbench',
		items: [
			{ title: 'Projects', href: '/projects', icon: 'folder-tree' },
			{
				title: 'Dashboard',
				icon: 'grid',
				projectScoped: true,
				projectPath: '/projects/{projectId}/dashboard'
			},
			{
				title: 'Generate',
				icon: 'sparkles',
				label: 'Beta',
				projectScoped: true,
				projectPath: '/projects/{projectId}/generate'
			},
			{
				title: 'Review',
				icon: 'upload-cloud',
				label: 'Core',
				projectScoped: true,
				projectPath: '/projects/{projectId}/review'
			},
			{
				title: 'Reports',
				icon: 'file-bar-chart-2',
				projectScoped: true,
				projectPath: '/projects/{projectId}/reports'
			},
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
