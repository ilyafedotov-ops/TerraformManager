import { redirect } from '@sveltejs/kit';
import { API_BASE } from '$lib/api/client';

export const load = async ({ parent, params, fetch }) => {
	const parentData = await parent();
	const token = parentData.token;
	if (!token) {
		throw redirect(302, '/login');
	}
	const projectSlug = params.projectSlug;
	if (!projectSlug) {
		throw redirect(302, '/projects');
	}
	const response = await fetch(`${API_BASE}/projects/${projectSlug}`, {
		headers: {
			Authorization: `Bearer ${token}`
		}
	});
	if (!response.ok) {
		throw redirect(302, '/projects');
	}
	const project = await response.json();
	const canonicalSlug = project?.slug ?? projectSlug ?? project?.id ?? null;
	return {
		project,
		projectId: project?.id ?? null,
		projectSlug: canonicalSlug,
		projectSlugParam: projectSlug
	};
};
