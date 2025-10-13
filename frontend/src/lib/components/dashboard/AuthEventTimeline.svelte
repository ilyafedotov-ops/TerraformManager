<script lang="ts">
	import type { AuthEvent } from '$lib/api/client';

	export let events: AuthEvent[] = [];

	const EVENT_LABELS: Record<string, string> = {
		login_success: 'Login success',
		login_failed: 'Login failed',
		token_refreshed: 'Token refreshed',
		refresh_reuse_detected: 'Refresh reuse detected',
		session_revoked: 'Session revoked',
		register_request: 'Access request submitted',
		recover_request: 'Recovery request submitted',
		logout: 'Logout complete'
	};

	const formatLabel = (eventName: string) =>
		EVENT_LABELS[eventName] ?? eventName.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());

	const formatTimestamp = (value: string) => {
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return value;
		return new Intl.DateTimeFormat(undefined, {
			dateStyle: 'medium',
			timeStyle: 'short'
		}).format(date);
	};

	const truncateAgent = (agent: string) => {
		const trimmed = agent.trim();
		if (!trimmed) return 'Unknown device';
		return trimmed.length > 110 ? `${trimmed.slice(0, 107)}…` : trimmed;
	};

	const abbreviateSession = (sessionId: string | null | undefined) => {
		if (!sessionId) return null;
		return `${sessionId.slice(0, 8)}…`;
	};

	const hasDetails = (details: Record<string, unknown> | null | undefined) =>
		!!details && Object.keys(details).length > 0;

	const formatDetails = (details: Record<string, unknown> | null | undefined) =>
		details ? JSON.stringify(details, null, 2) : '{}';
</script>

<div class="space-y-4">
	{#each events as event (event.id)}
		<article class="rounded-3xl border border-blueGray-100 bg-white p-5 shadow-sm shadow-blueGray-200/40">
			<header class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
				<div>
					<h3 class="text-sm font-semibold text-blueGray-700">{formatLabel(event.event)}</h3>
					<p class="text-xs uppercase tracking-[0.25em] text-blueGray-400">{formatTimestamp(event.created_at)}</p>
				</div>
				{#if abbreviateSession(event.session_id)}
					<span class="inline-flex w-fit items-center gap-2 rounded-full bg-blueGray-50 px-3 py-1 text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-blueGray-500 md:self-center">
						Session {abbreviateSession(event.session_id)}
					</span>
				{/if}
			</header>

			<dl class="mt-4 grid gap-4 text-xs text-blueGray-600 md:grid-cols-3">
				<div>
					<dt class="font-semibold uppercase tracking-[0.2em] text-blueGray-400">IP address</dt>
					<dd class="mt-1 text-blueGray-700">{event.ip_address ?? '—'}</dd>
				</div>
				<div class="md:col-span-2">
					<dt class="font-semibold uppercase tracking-[0.2em] text-blueGray-400">User agent</dt>
					<dd class="mt-1 text-blueGray-700">{event.user_agent ? truncateAgent(event.user_agent) : '—'}</dd>
				</div>
			</dl>

			{#if event.scopes.length}
				<div class="mt-4 flex flex-wrap gap-2">
					{#each event.scopes as scope (scope)}
						<span class="rounded-full bg-blueGray-100 px-2 py-[2px] text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-blueGray-500">
							{scope}
						</span>
					{/each}
				</div>
			{/if}

			{#if hasDetails(event.details)}
				<details class="mt-4 rounded-2xl border border-blueGray-100 bg-blueGray-50 px-4 py-3 text-xs text-blueGray-600">
					<summary class="cursor-pointer text-blueGray-500">Details</summary>
					<pre class="mt-2 whitespace-pre-wrap break-words text-[0.65rem] leading-relaxed text-blueGray-600">{formatDetails(event.details)}</pre>
				</details>
			{/if}
		</article>
	{/each}
</div>
