<script lang="ts">
import { env } from '$env/dynamic/public';
import { deleteReport, ApiError, type ReportSummary } from '$lib/api/client';
import ReportTable from '$lib/components/reports/ReportTable.svelte';
	import { browser } from '$app/environment';

	const { data } = $props();
	let reports = $state<ReportSummary[]>(data.reports ?? []);
	const error = data.error as string | undefined;
	const token = data.token as string | null;
	let deleteStatus = $state<string | null>(null);
	let deletingId = $state<string | null>(null);

const apiBase = (env.PUBLIC_API_BASE ?? 'http://localhost:8890').replace(/\/$/, '');

	const handleDelete = async (id: string) => {
		if (!token) {
			deleteStatus = 'Missing API token; cannot delete reports.';
			return;
		}
		if (browser) {
			const confirmed = window.confirm(`Delete report ${id}? This action cannot be undone.`);
			if (!confirmed) {
				return;
			}
		}
		deletingId = id;
		deleteStatus = null;
		try {
			await deleteReport(fetch, token, id);
			reports = reports.filter((report) => report.id !== id);
			deleteStatus = `Report ${id} deleted.`;
		} catch (err) {
			if (err instanceof ApiError) {
				const detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
				deleteStatus = detail ? `${err.message}: ${detail}` : err.message;
			} else if (err instanceof Error) {
				deleteStatus = err.message;
			} else {
				deleteStatus = 'Failed to delete report.';
			}
		} finally {
			deletingId = null;
		}
	};

</script>

<section class="space-y-8">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-blueGray-400">Reports</p>
		<h2 class="text-3xl font-semibold text-blueGray-700">Saved reviewer results</h2>
		<p class="max-w-3xl text-sm text-blueGray-500">
			This table will hydrate from the FastAPI `/reports` endpoint and support filtering, export, and direct navigation
			to the embedded report viewer.
		</p>
	</header>

	{#if error}
		<div class="rounded-3xl border border-rose-300 bg-rose-50 px-6 py-4 text-sm text-rose-700">
			<strong class="font-semibold">Failed to load reports.</strong>
			<span class="ml-2 text-rose-600">{error}</span>
		</div>
	{/if}

	{#if deleteStatus}
		<div class="rounded-3xl border border-blueGray-200 bg-blueGray-50 px-6 py-3 text-xs text-blueGray-600">{deleteStatus}</div>
	{/if}

	{#if reports.length}
		<ReportTable
			reports={reports}
			apiBase={apiBase}
			token={token}
			deletingId={deletingId}
			on:delete={(event) => void handleDelete(event.detail.id)}
		/>
	{:else if !error}
		<div class="rounded-3xl border border-blueGray-200 bg-blueGray-50 px-6 py-6 text-sm text-blueGray-500">
			No reports saved yet. Run <code class="rounded bg-blueGray-50 px-1 py-0.5 text-xs text-blueGray-600">python -m backend.cli scan sample --out tmp/report.json</code> to generate one.
		</div>
	{/if}
</section>
