import type { PageLoad } from './$types';
import { getLLMSettings } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent }) => {
    const { token } = await parent();
    if (!token) {
        return { token: null, settings: null };
    }
    try {
        const settings = await getLLMSettings(fetch, token);
        return { token, settings };
    } catch (error) {
        return {
            token,
            settings: null,
            error: error instanceof Error ? error.message : 'Unable to load LLM settings'
        };
    }
};
