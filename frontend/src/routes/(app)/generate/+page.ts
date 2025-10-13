import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
    const response = await fetch('/generators/metadata');
    const metadata = response.ok ? await response.json() : [];
    return { metadata };
};
