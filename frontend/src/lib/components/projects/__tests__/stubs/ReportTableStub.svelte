<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { ReportListResponse, ReportSummary } from '$lib/api/client';

	interface Props {
		data?: ReportListResponse | null;
		items?: ReportSummary[];
		isLoading?: boolean;
		offset?: number;
		limit?: number;
		deletingId?: string | null;
		selectedId?: string | null;
	}

	const {
		data = null,
		items = [],
		isLoading = false,
		offset = 0,
		limit = 50,
		deletingId = null,
		selectedId = null
	}: Props = $props();

	const dispatch = createEventDispatcher<{ select: string; delete: string; pageChange: number }>();

	const handleSelect = (id: string) => dispatch('select', id);
	const handleDelete = (id: string) => dispatch('delete', id);
	const handlePageChange = () => dispatch('pageChange', offset + limit);
</script>

<div
	data-testid="report-table-stub"
	data-total={data?.total_count ?? items.length}
	data-selected={selectedId ?? ''}
	data-deleting={deletingId ?? ''}
>
	{#if isLoading}
		<p>Loading…</p>
	{:else if items.length}
		<ul class="space-y-2 text-sm">
			{#each items as report (report.id)}
				<li class="flex gap-2">
					<button type="button" onclick={() => handleSelect(report.id)}>
						{report.id}
					</button>
					<button type="button" onclick={() => handleDelete(report.id)}>
						Delete {report.id}
					</button>
				</li>
			{/each}
		</ul>
	{:else}
		<p>No reports</p>
	{/if}
	<button type="button" onclick={handlePageChange}>Next page</button>
</div>
