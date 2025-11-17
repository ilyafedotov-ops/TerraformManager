import { env } from '$env/dynamic/public';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const apiBase = (env.PUBLIC_API_BASE ?? 'http://localhost:8890').replace(/\/$/, '');
	const response = await fetch(`${apiBase}/generators/metadata`);
	if (!response.ok) {
		return { metadata: [], error: `Failed to load generator metadata (status ${response.status})` };
	}
	const metadata = await response.json();
	return { metadata };
};
