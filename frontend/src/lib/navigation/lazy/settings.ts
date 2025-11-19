import type { NavigationItem } from '../types';

export const settingsNavigation: NavigationItem[] = [
	{ title: 'User Profile', href: '/settings/profile', icon: 'user' },
	{ title: 'Active Sessions', href: '/settings/sessions', icon: 'shield-check' },
	{ title: 'LLM Settings', href: '/settings/llm', icon: 'bot' }
];

export const loadSettingsNavigation = async (): Promise<NavigationItem[]> => {
	return settingsNavigation;
};
