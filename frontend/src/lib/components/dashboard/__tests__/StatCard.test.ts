import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import StatCard from '../StatCard.svelte';

describe('StatCard', () => {
	it('renders provided title, value, and description', () => {
		const { getByText } = render(StatCard, {
			props: {
				title: 'Reports indexed',
				value: 42,
				description: 'Latest summaries'
			}
		});

		expect(getByText('Reports indexed')).toBeInTheDocument();
		expect(getByText('42')).toBeInTheDocument();
		expect(getByText('Latest summaries')).toBeInTheDocument();
	});

	it('applies accent styles when requested', () => {
		const { container } = render(StatCard, {
			props: {
				title: 'Alerts',
				value: 'Critical',
				accent: 'danger'
			}
		});

		const card = container.querySelector('article');
		expect(card).not.toBeNull();
		expect(card).toHaveClass('border-rose-200');
		expect(card).toHaveClass('bg-rose-50');
		expect(card).toHaveClass('shadow-rose-200/40');
	});
});
