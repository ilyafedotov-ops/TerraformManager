import type { PageLoad } from './$types';
import { API_BASE } from '$lib/api/client';

export const load: PageLoad = async ({ fetch }) => {
	const response = await fetch(`${API_BASE}/generators/metadata`);
	if (!response.ok) {
		return { metadata: [], error: `Failed to load generator metadata (status ${response.status})` };
	}
	const metadata = await response.json();
	return { metadata };
};
