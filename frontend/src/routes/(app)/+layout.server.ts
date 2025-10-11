import { redirect } from '@sveltejs/kit';

export const load = ({ cookies, url }) => {
	const token = cookies.get('tm_api_token');
	if (!token) {
		const redirectTo = url.pathname === '/login' ? '/login' : `/login?redirect=${encodeURIComponent(url.pathname + url.search)}`;
		throw redirect(302, redirectTo);
	}

	return {
		token
	};
};
