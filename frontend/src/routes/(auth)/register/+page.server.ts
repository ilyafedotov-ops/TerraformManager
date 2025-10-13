import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { apiFetch, ApiError } from '$lib/api/client';

const successMessage =
	'Thanks! The platform team has received your request and will share onboarding details shortly.';

export const load: PageServerLoad = ({ locals }) => {
	if (locals.token) {
		throw redirect(303, '/dashboard');
	}

	return {};
};

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const formData = await request.formData();
		const email = String(formData.get('email') ?? '').trim().toLowerCase();
		const team = String(formData.get('team') ?? '').trim();
		const region = String(formData.get('region') ?? '').trim() || 'us';
		const notesRaw = formData.get('notes');
		const notes = typeof notesRaw === 'string' ? notesRaw.trim() : '';

		if (!email) {
			return fail(400, {
				error: 'Email is required.',
				values: { email, team, region, notes }
			});
		}

		if (!team) {
			return fail(400, {
				error: 'Team or project name is required.',
				values: { email, team, region, notes }
			});
		}

		try {
			await apiFetch(fetch, '/auth/register', {
				method: 'POST',
				body: {
					email,
					team,
					region,
					notes: notes || null
				}
			});

			return {
				success: true,
				message: successMessage,
				values: { email, team, region, notes }
			};
		} catch (error) {
			if (error instanceof ApiError && error.status < 500) {
				return fail(error.status, {
					error: typeof error.detail === 'string' ? error.detail : 'Unable to submit request.',
					values: { email, team, region, notes }
				});
			}

			return fail(500, {
				error: 'Unexpected error submitting the access request. Please try again later.',
				values: { email, team, region, notes }
			});
		}
	}
};
