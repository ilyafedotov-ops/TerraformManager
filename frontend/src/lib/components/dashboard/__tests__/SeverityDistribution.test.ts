import { fireEvent, render, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import SeverityDistribution from '../SeverityDistribution.svelte';
import type { DashboardStats } from '$lib/types/dashboard';

const buildStats = (overrides: Partial<DashboardStats> = {}): DashboardStats => ({
	reports: 3,
	last: null,
	severityCounts: {
		critical: 4,
		high: 6,
		medium: 2
	},
	recentSeverityCounts: {
		critical: 2,
		high: 3
	},
	...overrides
});

describe('SeverityDistribution', () => {
	it('renders severity entries and tracker for overall stats', () => {
		const stats = buildStats();
		const { getByText, getAllByText, getByTestId } = render(SeverityDistribution, {
			props: { stats }
		});

		expect(getByText('Severity distribution')).toBeInTheDocument();
		expect(getByText('Aggregated across 3 reports.')).toBeInTheDocument();
		const entries = getByTestId('severity-entries');
		expect(entries).toBeInTheDocument();
		expect(within(entries).getAllByText(/critical/i)[0]).toBeInTheDocument();
		expect(getAllByText('4')).toBeTruthy();
		expect(getByText('Overall severity mix')).toBeInTheDocument();
	});

	it('shows recent tab results when selected', async () => {
		const stats = buildStats({ reports: 10 });
		const { getByText, getByTestId } = render(SeverityDistribution, {
			props: { stats, recentLimit: 5 }
		});

		await fireEvent.click(getByText('Last 5 reports'));

		expect(getByText('Aggregated across 5 reports.')).toBeInTheDocument();
		expect(getByText('Recent severity mix')).toBeInTheDocument();
		expect(within(getByTestId('severity-entries')).queryByText(/medium/i)).toBeNull();
	});

	it('falls back to guidance when no stats are available', () => {
		const { getByText } = render(SeverityDistribution, {
			props: { stats: null }
		});

		expect(getByText('Run your first scan to populate severity trends.')).toBeInTheDocument();
	});
});
