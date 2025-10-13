import { writable } from 'svelte/store';

export type NotificationVariant = 'info' | 'success' | 'error';

export interface Notification {
	id: number;
	message: string;
	variant: NotificationVariant;
}

export interface NotifyOptions {
	duration?: number;
}

let counter = 0;

export const notifications = writable<Notification[]>([]);

export function dismissNotification(id: number) {
	notifications.update((items) => items.filter((item) => item.id !== id));
}

function pushNotification(message: string, variant: NotificationVariant, options?: NotifyOptions) {
	const id = ++counter;
	const entry: Notification = { id, message, variant };
	notifications.update((items) => [...items, entry]);

	const duration = options?.duration ?? 5000;
	if (duration > 0 && typeof window !== 'undefined') {
		window.setTimeout(() => dismissNotification(id), duration);
	}

	return id;
}

export function notify(message: string, options?: NotifyOptions) {
	return pushNotification(message, 'info', options);
}

export function notifySuccess(message: string, options?: NotifyOptions) {
	return pushNotification(message, 'success', options);
}

export function notifyError(message: string, options?: NotifyOptions) {
	return pushNotification(message, 'error', options);
}
