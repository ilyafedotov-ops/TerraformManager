import type { PageLoad } from './$types';
import { API_BASE, getReport, ApiError, type ReportDetail } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent, url }) => {
	const { token } = await parent();
	const reportId = (url.searchParams.get('report') ?? '').trim();
	let reportDetail: ReportDetail | null = null;
	let reportError: string | undefined;

	if (!token) {
		return { projects: [], token: null, selectedReportId: reportId || null, report: null };
	}

	const response = await fetch(`${API_BASE}/projects`, {
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (!response.ok) {
		return {
			projects: [],
			token,
			error: `Failed to load projects (status ${response.status})`,
			selectedReportId: reportId || null,
			report: null,
			reportError
		};
	}

	const projects = await response.json();
	if (reportId) {
		try {
			reportDetail = await getReport(fetch, token, reportId);
		} catch (error) {
			reportError =
				error instanceof ApiError
					? `${error.message}${error.detail ? ` (${JSON.stringify(error.detail)})` : ''}`
					: error instanceof Error
						? error.message
						: 'Failed to load report';
		}
	}
	return {
		projects,
		token,
		selectedReportId: reportId || null,
		report: reportDetail,
		reportError
	};
};
