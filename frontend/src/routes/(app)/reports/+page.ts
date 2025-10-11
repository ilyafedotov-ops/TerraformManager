import type { PageLoad } from './$types';
import { listReports, type ReportSummary, ApiError } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent }) => {
	const { token } = await parent();
	if (!token) {
		return { reports: [], error: 'Missing API token' };
	}

	try {
		const reports = await listReports(fetch, token, 100);
		return { reports };
	} catch (error) {
		const message =
			error instanceof ApiError
				? `${error.message}${error.detail ? ` (${JSON.stringify(error.detail)})` : ''}`
				: error instanceof Error
					? error.message
					: 'Failed to load reports';
		return { reports: [], error: message };
	}
};
