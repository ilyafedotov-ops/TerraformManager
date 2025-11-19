<script lang="ts">
	import { browser } from '$app/environment';
	import { onDestroy } from 'svelte';
	import {
		type UserProfileResponse,
		type ProfileUpdatePayload,
		type PasswordChangePayload,
		ApiError,
		getUserProfile,
		updateUserProfile,
		changePassword
	} from '$lib/api/client';
	import { token as tokenStore } from '$lib/stores/auth';
	import { notifyError, notifySuccess } from '$lib/stores/notifications';

	const { data } = $props();

	type ProfileResponse = UserProfileResponse | null;

	let authToken = $state<string | null>(data.token ?? null);
	let profile = $state<ProfileResponse>(data.profile ?? null);
	let loadError = $state<string | null>(data.loadError ?? null);
	let refreshing = $state(false);
	let profileSaving = $state(false);
	let passwordSaving = $state(false);
	let profileError = $state<string | null>(null);
	let passwordError = $state<string | null>(null);

let profileForm = $state({
	fullName: '',
	jobTitle: '',
	timezone: '',
	avatarUrl: '',
	notifyEmail: false,
	notifyBrowser: false
});

	let passwordForm = $state({
		current: '',
		next: '',
		confirm: ''
	});

	let unsubscribe: (() => void) | null = null;

	const timezoneOptions = [
		'UTC',
		'America/New_York',
		'America/Los_Angeles',
		'Europe/London',
		'Europe/Berlin',
		'Asia/Singapore',
		'Asia/Tokyo',
		'Australia/Sydney'
	];

	const formatDateTime = (value: string | null | undefined) => {
		if (!value) return '—';
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return value;
		return date.toLocaleString();
	};

	const resolveErrorMessage = (error: unknown, fallback: string) => {
		if (error instanceof ApiError) {
			if (typeof error.detail === 'string') return error.detail;
			if (error.detail) return JSON.stringify(error.detail);
			return error.message;
		}
		if (error instanceof Error) {
			return error.message;
		}
		return fallback;
	};

	const syncProfileForm = (nextProfile: ProfileResponse) => {
		if (!nextProfile) {
			profileForm = {
				fullName: '',
				jobTitle: '',
				timezone: '',
				avatarUrl: '',
				notifyEmail: false,
				notifyBrowser: false
			};
			return;
		}
		profileForm = {
			fullName: nextProfile.full_name ?? '',
			jobTitle: nextProfile.job_title ?? '',
			timezone: nextProfile.timezone ?? '',
			avatarUrl: nextProfile.avatar_url ?? '',
			notifyEmail: Boolean(nextProfile.preferences?.notifications?.email),
			notifyBrowser: Boolean(nextProfile.preferences?.notifications?.browser)
		};
	};

	const reloadProfile = async (silent = false) => {
		if (!authToken) {
			if (!silent) {
				const message = 'Missing authentication token; sign in again to manage your profile.';
				loadError = message;
				notifyError(message);
			}
			return;
		}
		refreshing = true;
		if (!silent) {
			loadError = null;
		}
		try {
			const response = await getUserProfile(fetch, authToken);
			profile = response;
			syncProfileForm(response);
			loadError = null;
			if (!silent) {
				notifySuccess('Profile refreshed.');
			}
		} catch (error) {
			const message = resolveErrorMessage(error, 'Failed to load profile.');
			loadError = message;
			notifyError(message);
		} finally {
			refreshing = false;
		}
	};

	const handleProfileSubmit = async () => {
		if (!authToken) {
			profileError = 'Missing authentication token; sign in again to update your profile.';
			notifyError(profileError);
			return;
		}
		profileSaving = true;
		profileError = null;
		const payload: ProfileUpdatePayload = {
			full_name: profileForm.fullName,
			job_title: profileForm.jobTitle,
			timezone: profileForm.timezone,
			avatar_url: profileForm.avatarUrl,
			preferences: {
				notifications: {
					email: profileForm.notifyEmail,
					browser: profileForm.notifyBrowser
				}
			}
		};
		try {
			const updated = await updateUserProfile(fetch, authToken, payload);
			profile = updated;
			syncProfileForm(updated);
			notifySuccess('Profile updated.');
		} catch (error) {
			const message = resolveErrorMessage(error, 'Unable to update profile.');
			profileError = message;
			notifyError(message);
		} finally {
			profileSaving = false;
		}
	};

	const clearPasswordForm = () => {
		passwordForm = {
			current: '',
			next: '',
			confirm: ''
		};
	};

	const handlePasswordSubmit = async () => {
		if (!authToken) {
			passwordError = 'Missing authentication token; sign in again to rotate your password.';
			notifyError(passwordError);
			return;
		}
		if (!passwordForm.next || passwordForm.next.length < 8) {
			passwordError = 'New password must be at least 8 characters long.';
			return;
		}
		if (passwordForm.next !== passwordForm.confirm) {
			passwordError = 'New passwords do not match.';
			return;
		}
		passwordSaving = true;
		passwordError = null;
		const payload: PasswordChangePayload = {
			current_password: passwordForm.current,
			new_password: passwordForm.next,
			confirm_new_password: passwordForm.confirm
		};
		try {
			const result = await changePassword(fetch, authToken, payload);
			notifySuccess(
				result.revoked_sessions && result.revoked_sessions > 0
					? `Password changed. ${result.revoked_sessions} other session(s) revoked.`
					: 'Password changed successfully.'
			);
			clearPasswordForm();
		} catch (error) {
			const message = resolveErrorMessage(error, 'Unable to change password.');
			passwordError = message;
			notifyError(message);
		} finally {
			passwordSaving = false;
		}
	};

	$effect(() => {
		if (data.token !== undefined) {
			authToken = data.token ?? null;
		}
		if (data.profile !== undefined) {
			profile = data.profile ?? null;
			syncProfileForm(profile);
		}
		if (data.loadError !== undefined) {
			loadError = data.loadError ?? null;
		}
	});

	$effect(() => {
		syncProfileForm(profile);
	});

	if (browser) {
		unsubscribe = tokenStore.subscribe((value) => {
			if (value === authToken) {
				return;
			}
			authToken = value;
			if (authToken) {
				void reloadProfile(true);
			} else {
				profile = null;
				loadError = 'Sign in to manage your profile.';
				syncProfileForm(null);
			}
		});
	}

	onDestroy(() => {
		unsubscribe?.();
	});

	const overviewName = $derived(profile?.full_name?.trim() || profile?.email || 'Unknown user');
	const overviewEmail = $derived(profile?.email ?? '—');
	const scopes = $derived(profile?.scopes ?? []);
	const avatarUrl = $derived(profile?.avatar_url ?? null);
	const avatarInitials = $derived(() => {
		const source = profile?.full_name?.trim() || profile?.email || 'EM';
		const letters = source
			.split(/\s+/)
			.map((part) => part.charAt(0))
			.filter(Boolean)
			.slice(0, 2)
			.join('');
		return letters.toUpperCase() || 'EM';
	});
</script>

<section class="space-y-8">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Account</p>
		<h1 class="text-3xl font-semibold text-slate-700">User profile</h1>
		<p class="max-w-2xl text-sm text-slate-500">
			Manage the contact details associated with your account, adjust notification preferences, and rotate
			your password. Password updates revoke other active sessions and require fresh login on those devices.
		</p>
		<div class="flex flex-wrap gap-3">
			<button
				type="button"
				class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500 transition hover:border-sky-300 hover:text-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
				onclick={() => void reloadProfile()}
				disabled={!authToken || refreshing}
			>
				{#if refreshing}
					<span class="h-2 w-2 animate-pulse rounded-full bg-sky-400"></span>
				{/if}
				Refresh profile
			</button>
			<a
				class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.25em] text-slate-500 transition hover:border-sky-300 hover:text-sky-600"
				href="/settings/sessions"
			>
				Manage sessions
			</a>
		</div>
	</header>

	{#if !authToken}
		<div class="rounded-3xl border border-amber-200 bg-amber-50 px-6 py-4 text-sm text-amber-700">
			Sign in to view or edit your profile.
		</div>
	{:else}
		{#if loadError}
			<div class="rounded-3xl border border-rose-300 bg-rose-50 px-6 py-4 text-sm text-rose-700">
				<strong class="font-semibold">Request failed.</strong>
				<span class="ml-2 text-rose-600">{loadError}</span>
			</div>
		{/if}

		<div class="grid gap-8 lg:grid-cols-3">
			<div class="space-y-6">
				<article class="rounded-3xl border border-slate-100 bg-white p-6 shadow-sm">
					<div class="flex items-center gap-4">
						<div class="flex h-16 w-16 items-center justify-center overflow-hidden rounded-2xl bg-sky-500 text-lg font-semibold text-white">
							{#if avatarUrl}
								<img src={avatarUrl} alt={overviewName} class="h-full w-full object-cover" loading="lazy" />
							{:else}
								{avatarInitials}
							{/if}
						</div>
						<div>
							<p class="text-lg font-semibold text-slate-700">{overviewName}</p>
							<p class="text-sm text-slate-500">{overviewEmail}</p>
						</div>
					</div>
					<dl class="mt-6 space-y-3 text-sm text-slate-600">
						<div class="flex justify-between">
							<dt class="text-slate-400">Project scopes</dt>
							<dd class="flex flex-wrap justify-end gap-2">
								{#if scopes.length}
									{#each scopes as scope (scope)}
										<span class="rounded-full bg-slate-100 px-2 py-[2px] text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-slate-500">
											{scope}
										</span>
									{/each}
								{:else}
									<span>—</span>
								{/if}
							</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-slate-400">Created at</dt>
							<dd>{formatDateTime(profile?.created_at)}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-slate-400">Last login</dt>
							<dd>{formatDateTime(profile?.last_login_at)}</dd>
						</div>
					</dl>
				</article>
				<article class="rounded-3xl border border-slate-100 bg-slate-50 p-6 text-sm text-slate-600">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Security tips</p>
					<ul class="mt-3 list-disc space-y-2 pl-4">
						<li>Rotate your password every few months and avoid credential reuse.</li>
						<li>Review the sessions page periodically to revoke stale devices.</li>
						<li>Consider using a password manager to generate strong credentials.</li>
					</ul>
				</article>
			</div>

			<div class="space-y-6 lg:col-span-2">
				<form
					class="space-y-6 rounded-3xl border border-slate-100 bg-white p-6 shadow-sm"
					onsubmit={(event) => {
						event.preventDefault();
						void handleProfileSubmit();
					}}
				>
					<div>
						<h2 class="text-xl font-semibold text-slate-700">Profile details</h2>
						<p class="text-sm text-slate-500">These details are shown throughout the workspace.</p>
					</div>

					<div class="grid gap-4 md:grid-cols-2">
						<label class="space-y-2 text-sm font-semibold text-slate-600">
							<span>Full name</span>
							<input
								type="text"
								class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
								bind:value={profileForm.fullName}
								placeholder="Jane Doe"
							/>
						</label>
						<label class="space-y-2 text-sm font-semibold text-slate-600">
							<span>Job title</span>
							<input
								type="text"
								class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
								bind:value={profileForm.jobTitle}
								placeholder="Platform Engineer"
							/>
						</label>
					</div>

					<div class="grid gap-4 md:grid-cols-2">
						<label class="space-y-2 text-sm font-semibold text-slate-600">
							<span>Timezone</span>
							<input
								list="timezone-options"
								type="text"
								class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
								bind:value={profileForm.timezone}
								placeholder="UTC"
							/>
							<datalist id="timezone-options">
								{#each timezoneOptions as option (option)}
									<option value={option}></option>
								{/each}
							</datalist>
						</label>
						<label class="space-y-2 text-sm font-semibold text-slate-600">
							<span>Avatar URL</span>
							<input
								type="url"
								class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
								bind:value={profileForm.avatarUrl}
								placeholder="https://example.com/avatar.png"
							/>
						</label>
					</div>

					<div class="grid gap-4 md:grid-cols-2">
						<label class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
							<input class="h-4 w-4 rounded border-slate-300 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={profileForm.notifyEmail} />
							<span class="flex-1">
								<span class="font-semibold text-slate-700">Email notifications</span>
								<p class="text-xs text-slate-500">Receive alerts for scan completions and workspace updates.</p>
							</span>
						</label>
						<label class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
							<input class="h-4 w-4 rounded border-slate-300 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={profileForm.notifyBrowser} />
							<span class="flex-1">
								<span class="font-semibold text-slate-700">In-app notifications</span>
								<p class="text-xs text-slate-500">Show reminders inside the dashboard for assigned actions.</p>
							</span>
						</label>
					</div>

					{#if profileError}
						<p class="rounded-2xl border border-rose-300 bg-rose-50 px-4 py-2 text-sm text-rose-700">{profileError}</p>
					{/if}

					<div class="flex flex-wrap gap-3">
						<button
							type="submit"
							class="rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-sky-300/50 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
							disabled={profileSaving}
						>
							{profileSaving ? 'Saving…' : 'Save changes'}
						</button>
					</div>
				</form>

				<form
					class="space-y-6 rounded-3xl border border-slate-100 bg-white p-6 shadow-sm"
					onsubmit={(event) => {
						event.preventDefault();
						void handlePasswordSubmit();
					}}
				>
					<div>
						<h2 class="text-xl font-semibold text-slate-700">Password</h2>
						<p class="text-sm text-slate-500">Set a strong password to protect access to your workspace.</p>
					</div>

					<label class="space-y-2 text-sm font-semibold text-slate-600">
						<span>Current password</span>
						<input
							type="password"
							class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
							bind:value={passwordForm.current}
							autocomplete="current-password"
						/>
					</label>
					<div class="grid gap-4 md:grid-cols-2">
						<label class="space-y-2 text-sm font-semibold text-slate-600">
							<span>New password</span>
							<input
								type="password"
								class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
								bind:value={passwordForm.next}
								autocomplete="new-password"
							/>
						</label>
						<label class="space-y-2 text-sm font-semibold text-slate-600">
							<span>Confirm password</span>
							<input
								type="password"
								class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
								bind:value={passwordForm.confirm}
								autocomplete="new-password"
							/>
						</label>
					</div>

					{#if passwordError}
						<p class="rounded-2xl border border-rose-300 bg-rose-50 px-4 py-2 text-sm text-rose-700">{passwordError}</p>
					{/if}

					<div class="flex flex-wrap gap-3">
						<button
							type="submit"
							class="rounded-2xl border border-slate-200 bg-white px-5 py-2 text-sm font-semibold text-slate-600 transition hover:bg-sky-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
							disabled={passwordSaving}
						>
							{passwordSaving ? 'Updating…' : 'Update password'}
						</button>
						<button
							type="button"
							class="rounded-2xl border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-100"
							onclick={clearPasswordForm}
						>
							Clear form
						</button>
					</div>
				</form>
			</div>
		</div>
	{/if}
</section>
