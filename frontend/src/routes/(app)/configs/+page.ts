import type { PageLoad } from './$types';
import { listReviewConfigs } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent }) => {
    const { token } = await parent();
    if (!token) {
        return { token: null, configs: [] };
    }
    try {
        const configs = await listReviewConfigs(fetch, token);
        return { token, configs };
    } catch (error) {
        return {
            token,
            configs: [],
            error: error instanceof Error ? error.message : 'Unable to load configs'
        };
    }
};
