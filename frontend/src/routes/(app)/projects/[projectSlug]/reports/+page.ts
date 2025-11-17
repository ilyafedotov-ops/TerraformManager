import type { PageLoad } from './$types';
import { listReports, ApiError } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent, params }) => {
	const parentData = await parent();
	const token = parentData.token;
	const project = parentData.project as { id?: string | null } | null;
	const projectId = project?.id ?? parentData.projectId ?? null;
	const projectSlug = parentData.projectSlug ?? params.projectSlug ?? null;

	if (!token) {
		return { reports: null, error: 'Missing API token', token: null };
	}
	if (!projectId && !projectSlug) {
		return { reports: null, error: 'Project context missing', token };
	}

	try {
		const reports = await listReports(fetch, token, {
			limit: 50,
			project_id: projectId ?? undefined
		});
		return { reports, token, projectId, projectSlug };
	} catch (error) {
		const message =
			error instanceof ApiError
				? `${error.message}${error.detail ? ` (${JSON.stringify(error.detail)})` : ''}`
				: error instanceof Error
					? error.message
					: 'Failed to load reports';
		return { reports: null, error: message, token, projectId, projectSlug };
	}
};
