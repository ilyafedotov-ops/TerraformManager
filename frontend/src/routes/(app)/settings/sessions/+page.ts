import type { PageLoad } from './$types';
import { listAuthSessions } from '$lib/api/client';

export const load: PageLoad = async ({ fetch, parent }) => {
	const { token } = await parent();

	if (!token) {
		return { token: null, sessions: [], currentSessionId: null };
	}

	try {
		const payload = await listAuthSessions(fetch, token);
		return {
			token,
			sessions: payload.sessions,
			currentSessionId: payload.current_session_id ?? null
		};
	} catch (error) {
		const message =
			error instanceof Error ? error.message : 'Unable to load active sessions.';
		return {
			token,
			sessions: [],
			currentSessionId: null,
			error: message
		};
	}
};
