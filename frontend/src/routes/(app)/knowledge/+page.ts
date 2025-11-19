import type { PageLoad } from './$types';
import { searchKnowledge } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent, url }) => {
	const { token } = await parent();
	const query = url.searchParams.get('q') ?? 'terraform security best practices';
	const provider = url.searchParams.get('provider') ?? '';
	const topK = Number(url.searchParams.get('top_k') ?? 3);
	const boundedTopK = Number.isFinite(topK) ? Math.min(Math.max(topK, 1), 10) : 3;
	try {
		const items = await searchKnowledge(fetch, query, boundedTopK, provider || undefined);
		return { token, query, topK: boundedTopK, provider, items };
	} catch (error) {
		return {
			token,
			query,
			topK: boundedTopK,
			provider,
			items: [],
			error: error instanceof Error ? error.message : 'Unable to load knowledge results'
		};
	}
};
