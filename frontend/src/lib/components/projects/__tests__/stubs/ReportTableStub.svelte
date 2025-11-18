<script lang="ts">
	import { createEventDispatcher } from 'svelte';
import type { ReportSummary } from '$lib/api/client';

interface Props {
	reports?: ReportSummary[];
	deletingId?: string | null;
	selectedId?: string | null;
	selectable?: boolean;
}

const {
	reports = [],
	deletingId = null,
	selectedId = null
}: Props = $props();

const dispatch = createEventDispatcher<{ select: { id: string }; delete: { id: string } }>();

const handleSelect = (id: string) => dispatch('select', { id });
const handleDelete = (id: string) => dispatch('delete', { id });
</script>

<div
	data-testid="report-table-stub"
	data-total={reports.length}
	data-selected={selectedId ?? ''}
	data-deleting={deletingId ?? ''}
>
	{#if reports.length}
		<ul class="space-y-2 text-sm">
			{#each reports as report (report.id)}
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
</div>
