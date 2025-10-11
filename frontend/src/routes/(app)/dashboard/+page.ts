import type { PageLoad } from './$types';
import { listReports, type ReportSummary } from '$lib/api/client';

interface DashboardStats {
	reports: number;
	last: ReportSummary | null;
	severityCounts: Record<string, number>;
}

export const load: PageLoad = async ({ fetch, parent }) => {
	const { token } = await parent();

	if (!token) {
		return {
			stats: null,
			error: 'Missing API token'
		};
	}

	try {
		const reports = await listReports(fetch, token, 20);
		const severityCounts: Record<string, number> = {};
		for (const report of reports) {
			const counts = report.summary?.severity_counts ?? {};
			for (const [severity, value] of Object.entries(counts)) {
				severityCounts[severity] = (severityCounts[severity] ?? 0) + Number(value ?? 0);
			}
		}

		const stats: DashboardStats = {
			reports: reports.length,
			last: reports[0] ?? null,
			severityCounts
		};

		return { stats };
	} catch (error) {
		return {
			stats: null,
			error: error instanceof Error ? error.message : 'Failed to load dashboard data'
		};
	}
};
