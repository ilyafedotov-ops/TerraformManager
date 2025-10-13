import { env } from '$env/dynamic/public';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, parent }) => {
	const { token } = await parent();
	const apiBase = (env.PUBLIC_API_BASE ?? 'http://localhost:8890').replace(/\/$/, '');

	if (!token) {
		return { projects: [], token: null };
	}

	const response = await fetch(`${apiBase}/projects`, {
		headers: {
			Authorization: `Bearer ${token}`
		}
	});

	if (!response.ok) {
		return { projects: [], token, error: `Failed to load projects (status ${response.status})` };
	}

	const projects = await response.json();
	return { projects, token };
};
