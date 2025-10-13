import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { get, type Readable } from 'svelte/store';
import MainNav from '../MainNav.svelte';
import { navigationState } from '$lib/stores/navigation';

type NavigationReadable<T> = Readable<T>;

const readNavigation = () => get(navigationState as unknown as NavigationReadable<any>);

afterEach(() => {
	navigationState.reset();
});

describe('MainNav', () => {
	it('emits navigate events when a link is clicked', async () => {
		const sections = [
			{
				title: 'Workbench',
				items: [
					{ title: 'Dashboard', href: '/dashboard', icon: 'grid' },
					{ title: 'Reports', href: '/reports', icon: 'file' }
				]
			}
		];

		const navigate = vi.fn();
		const { getByText } = render(MainNav, {
			props: { sections, activePath: '', expanded: {} },
			events: { navigate }
		});

		await fireEvent.click(getByText('Reports'));

		expect(navigate).toHaveBeenCalledTimes(1);
		const event = navigate.mock.calls[0][0] as CustomEvent<{ href: string }>;
		expect(event.detail).toEqual({ href: '/reports' });
	});

	it('loads lazy child links when expanding grouped items', async () => {
		const lazyChildren = [
			{ title: 'Team settings', href: '/settings/team', icon: 'users' },
			{ title: 'Billing', href: '/settings/billing', icon: 'credit-card' }
		];
		const lazyImport = vi.fn().mockResolvedValue(lazyChildren);

		const sections = [
			{
				title: 'Workspace',
				items: [{ title: 'Settings', icon: 'sliders-horizontal', lazyImport }]
			}
		];

		let expanded: Record<string, boolean> = {};
		const { getByText, queryByText, rerender } = render(MainNav, {
			props: { sections, activePath: '', expanded },
			events: {
				toggleSection: (event: CustomEvent<{ key: string; open: boolean }>) => {
					expanded = { ...expanded, [event.detail.key]: event.detail.open };
					void rerender({ sections, activePath: '', expanded });
				}
			}
		});

		expect(queryByText('Team settings')).toBeNull();

		const summary = getByText('Settings').closest('summary');
		expect(summary).not.toBeNull();
		await fireEvent.click(summary!);

		await waitFor(() => expect(lazyImport).toHaveBeenCalledTimes(1));
		await waitFor(() => expect(getByText('Team settings')).toBeInTheDocument());
		await waitFor(() => expect(getByText('Billing')).toBeInTheDocument());
	});

	it('reflects active path updates from the navigation store', async () => {
		const sections = [
			{
				title: 'Workbench',
				items: [
					{ title: 'Dashboard', href: '/dashboard', icon: 'grid' },
					{ title: 'Reports', href: '/reports', icon: 'file' }
				]
			}
		];

		const { getByText, rerender } = render(MainNav, {
			props: { sections, activePath: '', expanded: {} }
		});

		navigationState.setActivePath('/reports');
		const state = readNavigation();

		await rerender({ sections, activePath: state.activePath });

		const reportsLink = getByText('Reports').closest('a');
		expect(reportsLink).not.toBeNull();
		expect(reportsLink?.className).toContain('bg-lightBlue-50');
		expect(reportsLink?.className).toContain('text-lightBlue-600');
	});
});
