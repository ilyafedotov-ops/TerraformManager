import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { apiFetch, ApiError } from '$lib/api/client';

const successMessage = 'Recovery instructions are on the way. Check your inbox for the latest API token guidance.';

export const load: PageServerLoad = ({ locals, url }) => {
	if (locals.token) {
		throw redirect(303, url.searchParams.get('redirect') ?? '/dashboard');
	}

	return {};
};

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const formData = await request.formData();
		const email = String(formData.get('email') ?? '').trim().toLowerCase();

		if (!email) {
			return fail(400, {
				error: 'Email is required to send recovery instructions.',
				values: { email }
			});
		}

		try {
			await apiFetch(fetch, '/auth/recover', {
				method: 'POST',
				body: { email }
			});

			return {
				success: true,
				message: successMessage,
				values: { email }
			};
		} catch (error) {
			if (error instanceof ApiError && error.status < 500) {
				return fail(error.status, {
					error: typeof error.detail === 'string' ? error.detail : 'Unable to process recovery request.',
					values: { email }
				});
			}

			return fail(500, {
				error: 'Unexpected error requesting recovery. Please try again later.',
				values: { email }
			});
		}
	}
};
