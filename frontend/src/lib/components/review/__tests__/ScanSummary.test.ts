import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import ScanSummary from '../ScanSummary.svelte';

describe('ScanSummary', () => {
	it('renders report metrics and export links', () => {
		const { getByText, queryByText } = render(ScanSummary, {
			props: {
				reportId: 'rpt-123',
				summary: {
					issues_found: 4,
					files_scanned: 2,
					cost: {
						total_monthly_cost: 120,
						diff_monthly_cost: 10,
						currency: 'USD'
					},
					drift: {
						total_changes: 1,
						has_changes: true,
						counts: { create: 1 }
					}
				},
				report: {
					waived_findings: [1, 2],
					cost: {
						summary: {
							total_monthly_cost: 120,
							diff_monthly_cost: 10,
							total_hourly_cost: 0.2,
							diff_hourly_cost: 0.01,
							currency: 'USD'
						},
						projects: [
							{ name: 'core', path: '.', monthly_cost: 120, diff_monthly_cost: 10 }
						]
					},
					drift: {
						resource_changes: [{ address: 'aws_s3_bucket.example', action: 'update' }],
						output_changes: [],
						has_changes: true,
						counts: { create: 1 }
					}
				},
				severityEntries: [
					['critical', 2],
					['high', 1]
				],
				apiBase: 'https://api.example.dev'
			}
		});

		expect(getByText('rpt-123')).toBeInTheDocument();
		expect(getByText('4')).toBeInTheDocument();
		expect(getByText('Waived')).toBeInTheDocument();
		expect(getByText('critical')).toBeInTheDocument();
        expect(getByText('Cost insights')).toBeInTheDocument();
        expect(getByText('Plan drift')).toBeInTheDocument();

		const viewLink = getByText('View');
		expect(viewLink.getAttribute('href')).toBe('/reports/rpt-123');
		expect(getByText('JSON')).toHaveAttribute('href', 'https://api.example.dev/reports/rpt-123');
		expect(queryByText('Delete')).not.toBeInTheDocument();
	});

	it('shows placeholder when counts are missing', () => {
		const { getByText, queryByText } = render(ScanSummary, {
			props: {
				reportId: null,
				summary: null,
				report: null,
				severityEntries: [],
				apiBase: 'https://api.example.dev'
			}
		});

		expect(getByText('Unsaved result')).toBeInTheDocument();
		expect(getByText('No severity counts reported.')).toBeInTheDocument();
		expect(queryByText('View')).not.toBeInTheDocument();
	});
});
