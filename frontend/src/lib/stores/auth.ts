import { browser } from '$app/environment';
import { writable } from 'svelte/store';

const STORAGE_KEY = 'tmApiToken';

function createTokenStore() {
	const initial = browser ? window.localStorage.getItem(STORAGE_KEY) : null;
	const store = writable<string | null>(initial);

	if (browser) {
		store.subscribe((value) => {
			if (value) {
				window.localStorage.setItem(STORAGE_KEY, value);
			} else {
				window.localStorage.removeItem(STORAGE_KEY);
			}
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
}
