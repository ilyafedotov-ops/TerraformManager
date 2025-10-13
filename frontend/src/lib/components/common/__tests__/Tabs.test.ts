import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import Tabs from '../Tabs.svelte';

const tabItems = [
	{ id: 'recent', label: 'Recent' },
	{ id: 'all', label: 'All reports' }
];

describe('Tabs', () => {
	it('emits change when a new tab is selected', async () => {
		const handler = vi.fn();
		const { getByText } = render(Tabs, {
			props: { items: tabItems, active: 'recent' },
			events: { change: handler }
		});

		await fireEvent.click(getByText('All reports'));

		expect(handler).toHaveBeenCalledTimes(1);
		const event = handler.mock.calls[0][0] as CustomEvent<{ id: string }>;
		expect(event.detail).toEqual({ id: 'all' });
	});

	it('does not emit change when clicking the currently active tab', async () => {
		const handler = vi.fn();
		const { getByText } = render(Tabs, {
			props: { items: tabItems, active: 'recent' },
			events: { change: handler }
		});

		await fireEvent.click(getByText('Recent'));

		expect(handler).not.toHaveBeenCalled();
	});
});
