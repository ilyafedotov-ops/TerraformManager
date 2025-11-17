import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { API_BASE } from '$lib/api/client';
import { dev } from '$app/environment';

const COOKIE_NAME = 'tm_api_token';
const REFRESH_COOKIE_NAME = 'tm_refresh_token';
const REFRESH_CSRF_COOKIE = 'tm_refresh_csrf';
const DEFAULT_COOKIE_MAX_AGE = 60 * 15;

const secureCookie = !dev;

export const load: PageServerLoad = ({ locals, url }) => {
	if (locals.token) {
	throw redirect(303, '/projects');
	}

	return {
	redirectTo: url.searchParams.get('redirect') ?? '/projects'
	};
};

export const actions: Actions = {
	default: async ({ fetch, cookies, request, url }) => {
		const formData = await request.formData();
		const email = String(formData.get('email') ?? '').trim().toLowerCase();
		const rawPassword = formData.get('password');
		const password = typeof rawPassword === 'string' ? rawPassword.trim() : '';

		if (!email) {
			return fail(400, { error: 'Email is required', values: { email } });
		}

		if (!password) {
			return fail(400, { error: 'Password or API token is required', values: { email } });
		}

		const body = new URLSearchParams();
		body.set('username', email);
		body.set('password', password);
		body.set('scope', 'console:read console:write');

		const response = await fetch(`${API_BASE}/auth/token`, {
			method: 'POST',
			body,
			headers: { Accept: 'application/json' },
			credentials: 'include'
		});

		if (!response.ok) {
			if (response.status === 401) {
				return fail(401, {
					error: 'Invalid credentials. Verify your details and try again.',
					values: { email }
				});
			}
			return fail(response.status, {
				error: 'Unexpected error logging in. Please try again later.',
				values: { email }
			});
		}

		let payload: {
			access_token: string;
			expires_in: number;
			refresh_token?: string | null;
			refresh_expires_in: number;
			anti_csrf_token?: string | null;
		} | null = null;

		try {
			payload = await response.json();
		} catch {
			return fail(500, { error: 'Failed to parse authentication response', values: { email } });
		}

		const antiCsrf = response.headers.get('X-Refresh-Token-CSRF') ?? payload?.anti_csrf_token ?? null;
		const accessToken = payload?.access_token;
		const refreshToken = payload?.refresh_token ?? null;
		const expiresIn = Number(payload?.expires_in ?? DEFAULT_COOKIE_MAX_AGE);
		const refreshExpires = Number(payload?.refresh_expires_in ?? expiresIn);

		if (!accessToken) {
			return fail(500, { error: 'Authentication response missing access token', values: { email } });
		}

		const maxAgeSeconds = Math.max(expiresIn, DEFAULT_COOKIE_MAX_AGE);
		cookies.set(COOKIE_NAME, accessToken, {
			path: '/',
			maxAge: maxAgeSeconds,
			sameSite: 'lax',
			httpOnly: false,
			secure: secureCookie
		});

		const refreshMaxAge = Math.max(refreshExpires, maxAgeSeconds);
		if (refreshToken) {
			cookies.set(REFRESH_COOKIE_NAME, refreshToken, {
				path: '/',
				maxAge: refreshMaxAge,
				sameSite: 'lax',
				httpOnly: true,
				secure: secureCookie
			});
		} else {
			cookies.delete(REFRESH_COOKIE_NAME, { path: '/' });
		}

		if (antiCsrf) {
			cookies.set(REFRESH_CSRF_COOKIE, antiCsrf, {
				path: '/',
				maxAge: refreshMaxAge,
				sameSite: 'lax',
				httpOnly: false,
				secure: secureCookie
			});
		} else {
			cookies.delete(REFRESH_CSRF_COOKIE, { path: '/' });
		}

		const redirectTo = url.searchParams.get('redirect') ?? '/projects';
		throw redirect(303, redirectTo);
	}
};
