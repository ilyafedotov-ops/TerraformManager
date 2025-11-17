import type { PageLoad } from './$types';
import { getReport, ApiError } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent, params }) => {
	const { token } = await parent();
	if (!token) {
		return { report: null, error: 'Missing API token', token: null };
	}

	try {
		const report = await getReport(fetch, token, params.id);
		return { report, token };
	} catch (error) {
		const message =
			error instanceof ApiError
				? `${error.message}${error.detail ? ` (${JSON.stringify(error.detail)})` : ''}`
				: error instanceof Error
					? error.message
					: 'Failed to load report';
		return { report: null, error: message, token };
	}
};
