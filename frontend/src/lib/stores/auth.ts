import { browser } from '$app/environment';
import { writable } from 'svelte/store';

const STORAGE_KEY = 'tmApiToken';
const COOKIE_NAME = 'tm_api_token';
const CSRF_COOKIE_NAME = 'tm_refresh_csrf';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 30; // 30 days

function readCookie(name: string): string | null {
	if (!browser) return null;
	const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
	return match ? decodeURIComponent(match[1]) : null;
}

function writeCookie(value: string | null) {
	if (!browser) return;
	if (value) {
		document.cookie = `${COOKIE_NAME}=${encodeURIComponent(value)}; Path=/; Max-Age=${COOKIE_MAX_AGE}; SameSite=Lax`;
	} else {
		document.cookie = `${COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax`;
	}
}

function writeCsrfCookie(value: string | null) {
	if (!browser) return;
	if (value) {
		document.cookie = `${CSRF_COOKIE_NAME}=${encodeURIComponent(value)}; Path=/; Max-Age=${COOKIE_MAX_AGE}; SameSite=Lax`;
	} else {
		document.cookie = `${CSRF_COOKIE_NAME}=; Path=/; Max-Age=0; SameSite=Lax`;
	}
}

function readInitialToken(): string | null {
	if (!browser) return null;
	const fromStorage = window.localStorage.getItem(STORAGE_KEY);
	if (fromStorage) return fromStorage;
	return readCookie(COOKIE_NAME);
}

function createTokenStore() {
	const store = writable<string | null>(readInitialToken());

	if (browser) {
		store.subscribe((value) => {
			if (value) {
				window.localStorage.setItem(STORAGE_KEY, value);
			} else {
				window.localStorage.removeItem(STORAGE_KEY);
			}
			writeCookie(value);
		});
	}

	return store;
}

export const token = createTokenStore();

export function setToken(value: string) {
	token.set(value.trim());
}

export function clearToken() {
	token.set(null);
	setRefreshCsrf(null);
}

export function setRefreshCsrf(value: string | null) {
	writeCsrfCookie(value ? value.trim() : null);
}
