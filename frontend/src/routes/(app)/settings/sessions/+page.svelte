<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import {
		type AuthSession,
		ApiError,
		listAuthSessions,
		revokeAuthSession
	} from '$lib/api/client';
	import { token as tokenStore } from '$lib/stores/auth';
	import { notifyError, notifySuccess } from '$lib/stores/notifications';

	const { data } = $props();

	let authToken = $state<string | null>(data.token ?? null);
	let sessions = $state<AuthSession[]>(data.sessions ?? []);
	let currentSessionId = $state<string | null>(data.currentSessionId ?? null);
	let error = $state<string | null>(data.error ?? null);
	let loading = $state(false);
	let revokingId = $state<string | null>(null);
	let unsubscribe: (() => void) | null = null;

	$effect(() => {
		if (data.sessions !== undefined) {
			sessions = data.sessions ?? [];
		}
		if (data.currentSessionId !== undefined) {
			currentSessionId = data.currentSessionId ?? null;
		}
		if (data.error !== undefined) {
			error = data.error ?? null;
		}
		if (data.token !== undefined) {
			authToken = data.token ?? null;
		}
	});

	if (browser) {
		unsubscribe = tokenStore.subscribe((value) => {
			if (value === authToken) {
				return;
			}
			authToken = value;
			if (authToken) {
				void refreshSessions(true);
			} else {
				sessions = [];
				currentSessionId = null;
			}
		});
	}

	onDestroy(() => {
		unsubscribe?.();
	});

	const formatDateTime = (value: string | null | undefined) => {
		if (!value) return '—';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return value;
		return date.toLocaleString();
	};

	const describeAgent = (agent: string | null | undefined) => {
		if (!agent) return 'Unknown device';
		const trimmed = agent.trim();
		if (!trimmed) return 'Unknown device';
		return trimmed.length > 90 ? `${trimmed.slice(0, 87)}…` : trimmed;
	};

	const refreshSessions = async (silent = false) => {
		if (!authToken) {
			if (!silent) {
				error = 'Missing authentication token; sign in again to manage sessions.';
				notifyError(error);
			}
			return;
		}

		loading = true;
		if (!silent) {
			error = null;
		}

		try {
			const payload = await listAuthSessions(fetch, authToken);
			sessions = payload.sessions;
			currentSessionId = payload.current_session_id ?? null;
			error = null;
			if (!silent) {
				notifySuccess('Sessions refreshed.', { duration: 3500 });
			}
		} catch (err) {
			if (err instanceof ApiError) {
				const detail =
					typeof err.detail === 'string'
						? err.detail
						: err.detail
						? JSON.stringify(err.detail)
						: null;
				error = detail || err.message;
				notifyError(error);
			} else if (err instanceof Error) {
				error = err.message;
				notifyError(error);
			} else {
				error = 'Failed to load sessions.';
				notifyError(error);
			}
		} finally {
			loading = false;
		}
	};

	const handleRevoke = async (sessionId: string) => {
		if (!authToken) {
			error = 'Missing authentication token; sign in again to manage sessions.';
			notifyError(error);
			return;
		}

		const isCurrent = sessionId === currentSessionId;
		if (browser) {
			const confirmation = window.confirm(
				`Revoke ${isCurrent ? 'this device session' : 'the selected session'}?`
			);
			if (!confirmation) return;
		}

		revokingId = sessionId;
		error = null;

		try {
			const result = await revokeAuthSession(fetch, authToken, sessionId);
			const initialMessage =
				result.status === 'revoked'
					? 'Session revoked.'
					: 'Session already revoked.';
			await refreshSessions(true);
			const message = isCurrent
				? `${initialMessage} Sign out to finish clearing local tokens.`
				: initialMessage;
			notifySuccess(message, { duration: 5000 });
		} catch (err) {
			if (err instanceof ApiError) {
				const detail =
					typeof err.detail === 'string'
						? err.detail
						: err.detail
						? JSON.stringify(err.detail)
						: null;
				error = detail || err.message;
				notifyError(error);
			} else if (err instanceof Error) {
				error = err.message;
				notifyError(error);
			} else {
				error = 'Failed to revoke session.';
				notifyError(error);
			}
		} finally {
			revokingId = null;
		}
	};
</script>

<section class="space-y-8">
	<header class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
		<div class="space-y-3">
			<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Security</p>
			<h2 class="text-3xl font-semibold text-slate-700">Active device sessions</h2>
			<p class="max-w-2xl text-sm text-slate-500">
				Each login issues a refresh session. Revoke entries you do not recognise to immediately sign
				out those devices and require fresh authentication.
			</p>
		</div>
		<div class="flex gap-3">
			<button
				type="button"
				class="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white px-5 py-2 text-sm font-semibold text-sky-600 shadow-sm transition hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-70"
				onclick={() => void refreshSessions()}
				disabled={loading || !authToken}
			>
				{#if loading}
					<span class="h-2 w-2 animate-pulse rounded-full bg-sky-400"></span>
				{/if}
				<span>{loading ? 'Refreshing…' : 'Refresh list'}</span>
			</button>
		</div>
	</header>

	{#if !authToken}
		<div class="rounded-3xl border border-amber-200 bg-amber-50 px-6 py-4 text-sm text-amber-700">
			Sign in to manage active sessions.
		</div>
	{:else}
		{#if error}
			<div class="rounded-3xl border border-rose-300 bg-rose-50 px-6 py-4 text-sm text-rose-700">
				<strong class="font-semibold">Request failed.</strong>
				<span class="ml-2 text-rose-600">{error}</span>
			</div>
		{/if}

		{#if loading && !sessions.length}
			<div class="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-4 text-sm text-slate-500">
				Loading active sessions…
			</div>
		{/if}

		{#if sessions.length}
			<div class="overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-sm">
				<table class="min-w-full divide-y divide-slate-100">
					<thead class="bg-slate-50 text-xs uppercase tracking-[0.25em] text-slate-400">
						<tr>
							<th scope="col" class="px-6 py-3 text-left">Device</th>
							<th scope="col" class="px-6 py-3 text-left">IP address</th>
							<th scope="col" class="px-6 py-3 text-left">Last active</th>
							<th scope="col" class="px-6 py-3 text-left">Expires</th>
							<th scope="col" class="px-6 py-3 text-left">Scopes</th>
							<th scope="col" class="px-6 py-3 text-right">Actions</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-slate-100 text-sm text-slate-600">
						{#each sessions as session (session.id)}
							<tr class={session.is_current ? 'bg-sky-50/60' : ''}>
								<td class="px-6 py-4">
									<div class="flex flex-col gap-1">
										<span class="font-semibold text-slate-700">{describeAgent(session.user_agent)}</span>
										<span class="text-xs text-slate-400">
											Session ID: {session.id}
										</span>
										{#if session.is_current}
											<span class="inline-flex w-fit items-center gap-1 rounded-full bg-sky-500 px-2 py-[2px] text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-white">
												This device
											</span>
										{/if}
									</div>
								</td>
								<td class="px-6 py-4 text-slate-500">
									{session.ip_address ?? '—'}
								</td>
								<td class="px-6 py-4 text-slate-500">
									{formatDateTime(session.last_used_at ?? session.created_at)}
								</td>
								<td class="px-6 py-4 text-slate-500">
									{formatDateTime(session.expires_at)}
								</td>
								<td class="px-6 py-4">
									<div class="flex flex-wrap gap-2">
										{#each session.scopes as scope (scope)}
											<span class="rounded-full bg-slate-100 px-2 py-[2px] text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-slate-500">
												{scope}
											</span>
										{/each}
									</div>
								</td>
								<td class="px-6 py-4 text-right">
									<button
										type="button"
										class={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.2em] transition ${
											session.is_current
												? 'border border-amber-200 bg-amber-50 text-amber-600 hover:bg-amber-100'
												: 'border border-rose-200 bg-rose-50 text-rose-600 hover:bg-rose-100'
										}`}
										onclick={() => void handleRevoke(session.id)}
										disabled={revokingId === session.id || loading}
									>
										{revokingId === session.id ? 'Revoking…' : 'Revoke'}
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{:else if !loading}
			<div class="rounded-3xl border border-slate-200 bg-slate-50 px-6 py-6 text-sm text-slate-500">
				No active sessions found. Log in from another device to see it listed here.
			</div>
		{/if}
	{/if}
</section>
