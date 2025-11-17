import { env } from '$env/dynamic/public';
import { redirect } from '@sveltejs/kit';

const API_BASE = (env.PUBLIC_API_BASE ?? 'http://localhost:8890').replace(/\/$/, '');

export const load = async ({ parent, params, fetch }) => {
	const parentData = await parent();
	const token = parentData.token;
	if (!token) {
		throw redirect(302, '/login');
	}
	const projectId = params.projectId;
	if (!projectId) {
		throw redirect(302, '/projects');
	}
	const response = await fetch(`${API_BASE}/projects/${projectId}`, {
		headers: {
			Authorization: `Bearer ${token}`
		}
	});
	if (!response.ok) {
		throw redirect(302, '/projects');
	}
	const project = await response.json();
	return {
		project,
		projectId
	};
};
