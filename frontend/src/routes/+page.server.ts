import { redirect } from '@sveltejs/kit';

export const load = ({ locals }) => {
	throw redirect(302, locals.token ? '/projects' : '/login');
};
