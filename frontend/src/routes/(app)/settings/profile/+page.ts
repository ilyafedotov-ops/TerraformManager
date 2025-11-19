import type { PageLoad } from './$types';
import { getUserProfile, type UserProfileResponse, type UserPreferences } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent }) => {
	const { token, user } = await parent();

	if (!token) {
		return {
			token: null,
			profile: null,
			loadError: 'Sign in to view your profile.'
		};
	}

	try {
		const profile = await getUserProfile(fetch, token);
		return { token, profile };
	} catch (error) {
		const message = error instanceof Error ? error.message : 'Unable to load profile.';
		const fallback = user
			? ({
					id: user.id,
					email: user.email,
					scopes: user.scopes,
					expires_in: user.expiresIn,
					full_name: user.fullName,
					job_title: user.jobTitle,
					timezone: user.timezone,
					avatar_url: user.avatarUrl,
					preferences: (user.preferences ?? {}) as UserPreferences,
					created_at: user.createdAt,
					updated_at: user.updatedAt,
					last_login_at: user.lastLoginAt
				} satisfies UserProfileResponse)
			: null;
		return {
			token,
			profile: fallback,
			loadError: message
		};
	}
};
