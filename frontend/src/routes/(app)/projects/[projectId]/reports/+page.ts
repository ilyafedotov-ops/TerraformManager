import type { PageLoad } from './$types';
import { listReports, type ReportListResponse, ApiError } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent, params }) => {
	const { token } = await parent();
	if (!token) {
		return { reports: null, error: 'Missing API token', token: null };
	}

	try {
		const reports = await listReports(fetch, token, {
			limit: 50,
			project_id: params.projectId
		});
		return { reports, token };
	} catch (error) {
		const message =
			error instanceof ApiError
				? `${error.message}${error.detail ? ` (${JSON.stringify(error.detail)})` : ''}`
				: error instanceof Error
					? error.message
					: 'Failed to load reports';
		return { reports: null, error: message, token };
	}
};
