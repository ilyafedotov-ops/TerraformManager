import type { PageLoad } from './$types';
import { API_BASE } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent }) => {
    const { token } = await parent();

	if (!token) {
		return { projects: [], token: null };
	}

    const response = await fetch(`${API_BASE}/projects`, {
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
