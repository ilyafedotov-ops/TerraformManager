/// <reference types="@sveltejs/kit" />
// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		interface UserIdentity {
			id: string;
			email: string;
			scopes: string[];
			expiresIn: number;
			fullName: string | null;
			jobTitle: string | null;
			timezone: string | null;
			avatarUrl: string | null;
			preferences: Record<string, unknown>;
			createdAt: string | null;
			updatedAt: string | null;
			lastLoginAt: string | null;
		}

		interface Locals {
			token: string | null;
			user: UserIdentity | null;
		}

			interface PageData {
				token?: string | null;
				user?: UserIdentity | null;
				section?: {
					title: string;
					subtitle?: string | null;
					breadcrumbs?: Array<{ href: string; label: string }>;
				} | null;
			}
		}
	}

export {};
