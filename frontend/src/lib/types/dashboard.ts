import type { ReportSummary } from '$lib/api/client';

export interface DashboardStats {
	reports: number;
	last: ReportSummary | null;
	severityCounts: Record<string, number>;
	recentSeverityCounts: Record<string, number>;
}
