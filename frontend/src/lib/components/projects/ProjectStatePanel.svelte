<script lang="ts">
	import type { TerraformStateRecord, WorkspaceRecord, PlanRecord } from '$lib/api/client';

	export let states: TerraformStateRecord[] = [];
	export let workspaces: WorkspaceRecord[] = [];
	export let plans: PlanRecord[] = [];
	export let loading = false;
	export let error: string | null = null;
	export let onRefresh: (() => void | Promise<void>) | null = null;

	const formatDate = (value?: string | null) => {
		if (!value) {
			return '—';
		}
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) {
			return value;
		}
		return date.toLocaleString();
	};
</script>

<div class="space-y-6">
	<section class="rounded-xl border border-surface-200 bg-surface-50 p-5 shadow-sm">
		<div class="mb-4 flex items-center justify-between gap-4">
			<div>
				<h3 class="text-base font-semibold text-surface-900">Terraform States</h3>
				<p class="text-sm text-surface-500">Imported snapshots grouped by workspace and backend.</p>
			</div>
			{#if onRefresh}
				<button
					type="button"
					class="rounded-md border border-indigo-600 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-60"
					onclick={() => onRefresh?.()}
					disabled={loading}
				>
					{loading ? 'Refreshing…' : 'Refresh'}
				</button>
			{/if}
		</div>
		{#if error}
			<p class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
		{/if}
		{#if !loading && states.length === 0}
			<p class="text-sm text-surface-500">No Terraform state snapshots recorded for this project yet.</p>
		{:else}
			<div class="overflow-auto rounded-lg border border-surface-200">
				<table class="min-w-full divide-y divide-surface-200 text-sm">
					<thead class="bg-surface-100 text-xs font-semibold uppercase tracking-wide text-surface-500">
						<tr>
							<th class="px-4 py-2 text-left">Workspace</th>
							<th class="px-4 py-2 text-left">Backend</th>
							<th class="px-4 py-2 text-left">Resources</th>
							<th class="px-4 py-2 text-left">Outputs</th>
							<th class="px-4 py-2 text-left">Version</th>
							<th class="px-4 py-2 text-left">Imported</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-surface-200 bg-white text-surface-800">
						{#if loading}
							<tr>
								<td colspan="6" class="px-4 py-6 text-center text-surface-500">Loading state snapshots…</td>
							</tr>
						{:else}
							{#each states as state}
								<tr>
									<td class="px-4 py-3 font-medium">{state.workspace}</td>
									<td class="px-4 py-3 uppercase tracking-wide text-xs text-surface-500">{state.backend_type}</td>
									<td class="px-4 py-3">{state.resource_count}</td>
									<td class="px-4 py-3">{state.output_count}</td>
									<td class="px-4 py-3">
										{#if state.terraform_version}
											<span class="rounded bg-surface-100 px-2 py-0.5 text-xs text-surface-700">{state.terraform_version}</span>
										{:else}
											—
										{/if}
									</td>
									<td class="px-4 py-3 text-surface-500">{formatDate(state.imported_at ?? state.created_at)}</td>
								</tr>
							{/each}
						{/if}
					</tbody>
				</table>
			</div>
		{/if}
	</section>

	<section class="rounded-xl border border-surface-200 bg-white p-5 shadow-sm">
		<h3 class="mb-3 text-base font-semibold text-surface-900">Workspaces</h3>
		{#if workspaces.length === 0}
			<p class="text-sm text-surface-500">No workspace metadata recorded yet.</p>
		{:else}
			<ul class="space-y-3">
				{#each workspaces as workspace}
					<li class="rounded-lg border border-surface-200 bg-surface-50 px-3 py-2">
						<div class="flex items-center justify-between gap-2 text-sm">
							<div>
								<p class="font-medium text-surface-900">{workspace.name}</p>
								<p class="text-surface-500">{workspace.working_directory}</p>
							</div>
							<div class="text-right text-xs text-surface-500">
								<p>{workspace.is_active ? 'Active' : 'Idle'}</p>
								<p>{workspace.is_default ? 'Default' : 'Custom'}</p>
							</div>
						</div>
					</li>
				{/each}
			</ul>
		{/if}
	</section>

	<section class="rounded-xl border border-surface-200 bg-white p-5 shadow-sm">
		<h3 class="mb-3 text-base font-semibold text-surface-900">Plans</h3>
		{#if plans.length === 0}
			<p class="text-sm text-surface-500">No Terraform plans have been tracked for this project.</p>
		{:else}
			<div class="overflow-auto rounded-lg border border-surface-200">
				<table class="min-w-full divide-y divide-surface-200 text-sm">
					<thead class="bg-surface-100 text-xs font-semibold uppercase tracking-wide text-surface-500">
						<tr>
							<th class="px-4 py-2 text-left">Workspace</th>
							<th class="px-4 py-2 text-left">Type</th>
							<th class="px-4 py-2 text-left">Changes</th>
							<th class="px-4 py-2 text-left">Status</th>
							<th class="px-4 py-2 text-left">Created</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-surface-200 bg-white text-surface-800">
						{#each plans as plan}
							<tr>
								<td class="px-4 py-3 font-medium">{plan.workspace}</td>
								<td class="px-4 py-3 uppercase text-xs text-surface-500">{plan.plan_type}</td>
								<td class="px-4 py-3">
									<span class="rounded bg-surface-100 px-2 py-0.5 text-xs text-surface-700">
										+{plan.resources_to_add}/~{plan.resources_to_change}/-{plan.resources_to_destroy}
									</span>
								</td>
								<td class="px-4 py-3 capitalize">{plan.approval_status}</td>
								<td class="px-4 py-3 text-surface-500">{formatDate(plan.created_at)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</section>
</div>
