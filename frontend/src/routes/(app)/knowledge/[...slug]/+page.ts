import type { PageLoad } from './$types';
import { getKnowledgeDocument, ApiError } from '$lib/api/client';

const decodeSlug = (value: string | undefined): string => {
	if (!value) return '';
	return value
		.split('/')
		.map((segment) => decodeURIComponent(segment))
		.join('/');
};

export const load: PageLoad = async ({ fetch, parent, params }) => {
	const { token } = await parent();
	const path = decodeSlug(params.slug);

	if (!path) {
		return {
			doc: null,
			error: 'Document path missing.'
		};
	}

	if (!token) {
		return {
			doc: null,
			error: 'Missing API token for knowledge document access.'
		};
	}

	try {
		const doc = await getKnowledgeDocument(fetch, token, path);
		return {
			doc,
			error: null
		};
	} catch (error) {
		const message =
			error instanceof ApiError
				? `${error.message}${error.detail ? ` (${error.detail})` : ''}`
				: error instanceof Error
					? error.message
					: 'Failed to load knowledge document.';
		return {
			doc: null,
			error: message
		};
	}
};
