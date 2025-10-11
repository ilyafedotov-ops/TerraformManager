import { redirect } from '@sveltejs/kit';

export const load = ({ cookies }) => {
	const token = cookies.get('tm_api_token');
	throw redirect(302, token ? '/dashboard' : '/login');
};
