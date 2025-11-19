import type { Handle } from '@sveltejs/kit';
import { ApiError, refreshSession, getUserProfile, type UserProfileResponse } from '$lib/api/client';
import { dev } from '$app/environment';

const ACCESS_COOKIE = 'tm_api_token';
const REFRESH_COOKIE = 'tm_refresh_token';
const CSRF_COOKIE = 'tm_refresh_csrf';
const DEFAULT_COOKIE_MAX_AGE = 60 * 15;
const secureCookie = !dev;

export const handle: Handle = async ({ event, resolve }) => {
	let accessToken = event.cookies.get(ACCESS_COOKIE) ?? null;
	let csrfToken = event.cookies.get(CSRF_COOKIE) ?? null;
	const refreshCookie = event.cookies.get(REFRESH_COOKIE) ?? null;
	const cookieHeader = event.request.headers.get('cookie') ?? '';

	const setAccessCookie = (token: string, maxAge: number) => {
		event.cookies.set(ACCESS_COOKIE, token, {
			path: '/',
			maxAge,
			sameSite: 'lax',
			httpOnly: false,
			secure: secureCookie
		});
	};

	const setRefreshArtifacts = (refreshToken: string | null, antiCsrf: string | null, maxAge: number) => {
		if (refreshToken) {
			event.cookies.set(REFRESH_COOKIE, refreshToken, {
				path: '/',
				maxAge,
				sameSite: 'lax',
				httpOnly: true,
				secure: secureCookie
			});
		} else {
			event.cookies.delete(REFRESH_COOKIE, { path: '/' });
		}
		if (antiCsrf) {
			csrfToken = antiCsrf;
			event.cookies.set(CSRF_COOKIE, antiCsrf, {
				path: '/',
				maxAge,
				sameSite: 'lax',
				httpOnly: false,
				secure: secureCookie
			});
		} else {
			csrfToken = null;
			event.cookies.delete(CSRF_COOKIE, { path: '/' });
		}
	};

	const clearSession = () => {
		event.cookies.delete(ACCESS_COOKIE, { path: '/' });
		event.cookies.delete(REFRESH_COOKIE, { path: '/' });
		event.cookies.delete(CSRF_COOKIE, { path: '/' });
		accessToken = null;
		csrfToken = null;
		event.locals.token = null;
		event.locals.user = null;
	};

	const attemptRefresh = async (): Promise<boolean> => {
		if (!csrfToken || !refreshCookie) return false;
		try {
			const data = await refreshSession(event.fetch, csrfToken, cookieHeader);
			const accessMaxAge = Math.max(Number(data.expires_in ?? DEFAULT_COOKIE_MAX_AGE), DEFAULT_COOKIE_MAX_AGE);
			setAccessCookie(data.access_token, accessMaxAge);
			const refreshMaxAge = Math.max(Number(data.refresh_expires_in ?? accessMaxAge), accessMaxAge);
			setRefreshArtifacts(data.refresh_token ?? null, data.anti_csrf_token ?? null, refreshMaxAge);
			accessToken = data.access_token;
			return true;
		} catch (_error) {
			clearSession();
			return false;
		}
	};

	const mapProfile = (profile: UserProfileResponse) => ({
		id: profile.id,
		email: profile.email,
		scopes: profile.scopes ?? [],
		expiresIn: profile.expires_in,
		fullName: profile.full_name ?? null,
		jobTitle: profile.job_title ?? null,
		timezone: profile.timezone ?? null,
		avatarUrl: profile.avatar_url ?? null,
		preferences: profile.preferences ?? {},
		createdAt: profile.created_at ?? null,
		updatedAt: profile.updated_at ?? null,
		lastLoginAt: profile.last_login_at ?? null
	});

	const loadProfile = async () => {
		if (!accessToken) return;
		const profile = await getUserProfile(event.fetch, accessToken);
		event.locals.user = mapProfile(profile);
	};

	event.locals.token = accessToken;
	event.locals.user = null;

	if (!accessToken && refreshCookie && csrfToken) {
		const refreshed = await attemptRefresh();
		if (refreshed) {
			await loadProfile().catch(() => clearSession());
			event.locals.token = accessToken;
			return resolve(event);
		}
	}

	if (accessToken) {
		try {
			await loadProfile();
		} catch (error) {
			if (error instanceof ApiError && error.status === 401) {
				const refreshed = await attemptRefresh();
				if (refreshed) {
					try {
						await loadProfile();
					} catch {
						clearSession();
					}
				} else {
					clearSession();
				}
			} else {
				clearSession();
			}
		}
	}

	event.locals.token = accessToken;

	return resolve(event);
};
