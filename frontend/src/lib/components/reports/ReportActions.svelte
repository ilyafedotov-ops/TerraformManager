<script lang="ts">
	import { browser } from '$app/environment';
	import { createEventDispatcher } from 'svelte';
	import { notifyError, notifySuccess } from '$lib/stores/notifications';

interface Props {
	id: string;
	apiBase: string;
	viewHref?: string | null;
	deleting?: boolean;
	deleteEnabled?: boolean;
	compact?: boolean;
	showView?: boolean;
	showApiLinks?: boolean;
	showCopyJson?: boolean;
	showDelete?: boolean;
	projectId?: string | null;
}

const props: Props = $props();

const {
	id,
	apiBase,
	deleting = false,
	deleteEnabled = true,
	compact = false,
	showView = true,
	showApiLinks = true,
	showCopyJson = true,
	showDelete = true,
	projectId = null
} = props;

const viewHref =
	props.viewHref ?? (projectId ? `/projects/${projectId}/reports/${id}` : `/reports/${id}`);

	const dispatcher = createEventDispatcher<{ delete: void }>();

	const jsonHref = `${apiBase}/reports/${id}`;
	const csvHref = `${apiBase}/reports/${id}/csv`;
	const htmlHref = `${apiBase}/reports/${id}/html`;

	const layoutClass = compact ? 'gap-1 text-[0.65rem]' : 'gap-2 text-xs';

	const handleDelete = () => {
		if (!deleteEnabled || deleting) return;
		dispatcher('delete');
	};

	const copyJsonLink = async () => {
		if (!browser) return;
		try {
			await navigator.clipboard.writeText(jsonHref);
			notifySuccess('Report JSON link copied to clipboard.', { duration: 2500 });
		} catch (error) {
			console.warn('Failed to copy report link', error);
			notifyError('Unable to copy JSON link.');
		}
	};
</script>

<div class={`flex flex-wrap items-center ${layoutClass}`}>
	{#if showView}
		<a
			class="inline-flex items-center gap-2 rounded-xl border border-sky-200 px-4 py-2 font-semibold text-sky-600 transition hover:bg-sky-500 hover:text-white"
			href={viewHref}
		>
			View
		</a>
	{/if}

	{#if showApiLinks}
		<a
			class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 font-semibold text-slate-600 transition hover:bg-sky-500 hover:text-white"
			href={jsonHref}
			target="_blank"
			rel="noreferrer"
		>
			JSON
		</a>
		<a
			class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 font-semibold text-slate-600 transition hover:bg-sky-500 hover:text-white"
			href={csvHref}
		>
			CSV
		</a>
		<a
			class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 font-semibold text-slate-600 transition hover:bg-sky-500 hover:text-white"
			href={htmlHref}
			target="_blank"
			rel="noreferrer"
		>
			HTML
		</a>
	{/if}

	{#if showCopyJson}
		<button
			type="button"
			class="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 font-semibold text-slate-500 transition hover:bg-slate-50"
			onclick={copyJsonLink}
		>
			Copy JSON link
		</button>
	{/if}

	{#if showDelete}
		<button
			type="button"
			class="inline-flex items-center gap-2 rounded-xl border border-rose-200 px-4 py-2 font-semibold text-rose-600 transition hover:bg-rose-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
			onclick={handleDelete}
			disabled={deleting || !deleteEnabled}
		>
			{#if deleting}
				<span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
				Deleting…
			{:else}
				Delete
			{/if}
		</button>
	{/if}
</div>
