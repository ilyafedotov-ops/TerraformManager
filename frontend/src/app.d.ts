/// <reference types="@sveltejs/kit" />
// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		interface Locals {
			token: string | null;
			user: {
				email: string;
				scopes: string[];
				expiresIn: number;
			} | null;
		}

			interface PageData {
				token?: string | null;
				user?: {
					email: string;
					scopes: string[];
					expiresIn: number;
				} | null;
				section?: {
					title: string;
					subtitle?: string | null;
					breadcrumbs?: Array<{ href: string; label: string }>;
				} | null;
			}
		}
	}

export {};
