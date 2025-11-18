import type { PageLoad } from './$types';
import { listAuthEvents, listReports } from '$lib/api/client';
import type { ListReportsParams } from '$lib/api/client';
import type { DashboardStats } from '$lib/types/dashboard';

async function buildDashboardStats(
	fetchFn: typeof fetch,
	token: string,
	projectId?: string | null,
	projectSlug?: string | null
): Promise<DashboardStats> {
	const params: ListReportsParams = { limit: 20 };
	if (projectId) {
		params.project_id = projectId;
	}
	if (projectSlug) {
		params.project_slug = projectSlug;
	}
	const payload = await listReports(fetchFn, token, params);
	const reports = payload.items ?? [];
	const severityCounts: Record<string, number> = {};
	const recentSeverityCounts: Record<string, number> = {};

	for (const report of reports) {
		const counts = report.summary?.severity_counts ?? {};
		for (const [severity, value] of Object.entries(counts)) {
			severityCounts[severity] = (severityCounts[severity] ?? 0) + Number(value ?? 0);
		}
	}

	for (const report of reports.slice(0, 5)) {
		const counts = report.summary?.severity_counts ?? {};
		for (const [severity, value] of Object.entries(counts)) {
			recentSeverityCounts[severity] = (recentSeverityCounts[severity] ?? 0) + Number(value ?? 0);
		}
	}

	return {
		reports: reports.length,
		last: reports[0] ?? null,
		severityCounts,
		recentSeverityCounts
	};
}

const humaniseError = (error: unknown): string =>
	error instanceof Error ? error.message : 'Failed to load dashboard data';

export const load = (async ({ fetch, parent }) => {
	const { token, project, projectId, projectSlug } = await parent();

	if (!token) {
		return {
			stats: Promise.resolve<DashboardStats | null>(null),
			error: 'Missing API token',
			authEvents: Promise.resolve([]),
			authEventsError: 'Missing API token'
		};
	}

	const resolvedProjectId = (projectId as string | null) ?? (project?.id as string | null) ?? null;
	const resolvedProjectSlug = (projectSlug as string | null) ?? (project?.slug as string | null) ?? null;
	const statsPromise = buildDashboardStats(fetch, token, resolvedProjectId, resolvedProjectSlug);
	const eventsPromise = listAuthEvents(fetch, token, 20).then((payload) => payload.events);
	const safeEventsPromise = eventsPromise.catch(() => []);

	return {
		stats: statsPromise.catch(() => null),
		error: statsPromise.then(() => null).catch((error) => humaniseError(error)),
		authEvents: safeEventsPromise,
		authEventsError: eventsPromise.then(() => null).catch((error) => humaniseError(error))
	};
}) satisfies PageLoad<{
	stats: Promise<DashboardStats | null>;
	error: Promise<string | null> | string | null;
	authEvents: Promise<Awaited<ReturnType<typeof listAuthEvents>>['events']>;
	authEventsError: Promise<string | null> | string | null;
}>;
