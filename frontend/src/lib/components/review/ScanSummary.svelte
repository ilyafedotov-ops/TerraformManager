<script lang="ts">
	import ReportActions from '$lib/components/reports/ReportActions.svelte';

	/**
	 * Render the outcome of a reviewer scan with severity distribution and export links.
	 */
export let reportId: string | null = null;
export let summary: Record<string, unknown> | null = null;
export let report: Record<string, unknown> | null = null;
export let severityEntries: Array<[string, number]> = [];
export let apiBase: string;

const issuesFound = (summary as { issues_found?: number } | null)?.issues_found ?? 0;
const waivedCount = (report as { waived_findings?: unknown[] } | null)?.waived_findings?.length ?? 0;
const filesScanned = (summary as { files_scanned?: number } | null)?.files_scanned ?? 0;
const costSummary =
    (summary as { cost?: Record<string, unknown> } | null)?.cost ??
    ((report as { cost?: { summary?: Record<string, unknown> } } | null)?.cost?.summary ?? null);
const costDetails = (report as { cost?: Record<string, unknown> } | null)?.cost ?? null;
const costCurrency =
    (costSummary as { currency?: string | null } | null)?.currency ??
    (costDetails as { currency?: string | null } | null)?.currency ??
    null;
const costProjects = (costDetails as { projects?: Array<Record<string, unknown>> } | null)?.projects ?? [];
const costErrors = (costDetails as { errors?: string[] } | null)?.errors ?? [];
const hasCost = Boolean(costSummary || costProjects.length || costErrors.length);
const totalMonthlyCost = (costSummary as { total_monthly_cost?: number | null } | null)?.total_monthly_cost ?? null;
const diffMonthlyCost = (costSummary as { diff_monthly_cost?: number | null } | null)?.diff_monthly_cost ?? null;
const totalHourlyCost = (costSummary as { total_hourly_cost?: number | null } | null)?.total_hourly_cost ?? null;
const diffHourlyCost = (costSummary as { diff_hourly_cost?: number | null } | null)?.diff_hourly_cost ?? null;

const formatCurrency = (value: unknown) => {
    if (value === null || value === undefined) return '—';
    if (typeof value !== 'number') {
        const parsed = Number(value);
        if (Number.isNaN(parsed)) {
            return String(value);
        }
        value = parsed;
    }
    if (costCurrency) {
        try {
            return new Intl.NumberFormat(undefined, { style: 'currency', currency: costCurrency }).format(value as number);
        } catch (err) {
            return `${costCurrency} ${(value as number).toFixed(2)}`;
        }
    }
    return (value as number).toFixed(2);
};

const driftSummary =
    (summary as { drift?: Record<string, unknown> } | null)?.drift ??
    ((report as { drift?: Record<string, unknown> } | null)?.drift ?? null);
const driftCounts = (driftSummary as { counts?: Record<string, number> } | null)?.counts ?? {};
const driftCountEntries = Object.entries(driftCounts).filter(([, value]) => Number(value ?? 0) > 0);
const driftResourceChanges = (report as { drift?: { resource_changes?: Array<Record<string, unknown>> } } | null)?.drift
    ?.resource_changes ?? [];
const driftOutputChanges = (report as { drift?: { output_changes?: Array<Record<string, unknown>> } } | null)?.drift
    ?.output_changes ?? [];
const driftError = (report as { drift?: { error?: string | null } } | null)?.drift?.error ?? null;
const driftHasChanges = Boolean((driftSummary as { has_changes?: boolean } | null)?.has_changes);
</script>

<section class="space-y-4 rounded-3xl border border-blueGray-200 bg-white p-6 shadow-xl shadow-blueGray-300/40">
	<header class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">Scan summary</p>
			<h3 class="text-xl font-semibold text-blueGray-700">{reportId ?? 'Unsaved result'}</h3>
		</div>
		{#if reportId}
			<ReportActions
				id={reportId}
				apiBase={apiBase}
				compact
				showDelete={false}
				showCopyJson
			/>
		{/if}
	</header>

	<div class="grid gap-4 md:grid-cols-3">
		<div class="rounded-2xl border border-blueGray-200 bg-blueGray-50 p-4">
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">Issues found</p>
			<p class="mt-3 text-3xl font-semibold text-blueGray-700">{issuesFound}</p>
		</div>
		<div class="rounded-2xl border border-blueGray-200 bg-blueGray-50 p-4">
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">Waived</p>
			<p class="mt-3 text-3xl font-semibold text-blueGray-700">{waivedCount}</p>
		</div>
		<div class="rounded-2xl border border-blueGray-200 bg-blueGray-50 p-4">
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">Files scanned</p>
			<p class="mt-3 text-3xl font-semibold text-blueGray-700">{filesScanned}</p>
		</div>
	</div>

	<section class="space-y-2">
		<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">Severity distribution</h4>
		{#if severityEntries.length}
			<ul class="space-y-2 text-sm text-blueGray-600">
				{#each severityEntries as [severity, count]}
					<li class="flex items-center justify-between rounded-xl border border-blueGray-200 bg-blueGray-50 px-4 py-2">
						<span class="uppercase tracking-[0.2em] text-blueGray-500">{severity}</span>
						<span class="font-semibold">{count}</span>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="rounded-xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-500">
				No severity counts reported.
			</p>
		{/if}
	</section>

    {#if hasCost}
        <section class="space-y-3">
            <h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">Cost insights</h4>
            <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div class="rounded-2xl border border-blueGray-200 bg-lightBlue-50 p-4 text-blueGray-700">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-lightBlue-500">Total monthly</p>
                    <p class="mt-2 text-2xl font-semibold">{formatCurrency(totalMonthlyCost)}</p>
                </div>
                <div class="rounded-2xl border border-blueGray-200 bg-lightBlue-50 p-4 text-blueGray-700">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-lightBlue-500">Δ monthly</p>
                    <p class="mt-2 text-2xl font-semibold">{formatCurrency(diffMonthlyCost)}</p>
                </div>
                <div class="rounded-2xl border border-blueGray-200 bg-lightBlue-50 p-4 text-blueGray-700">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-lightBlue-500">Total hourly</p>
                    <p class="mt-2 text-2xl font-semibold">{formatCurrency(totalHourlyCost)}</p>
                </div>
                <div class="rounded-2xl border border-blueGray-200 bg-lightBlue-50 p-4 text-blueGray-700">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-lightBlue-500">Δ hourly</p>
                    <p class="mt-2 text-2xl font-semibold">{formatCurrency(diffHourlyCost)}</p>
                </div>
            </div>

            {#if costProjects.length}
                <div class="overflow-x-auto rounded-2xl border border-blueGray-200">
                    <table class="min-w-full divide-y divide-blueGray-100 text-sm text-blueGray-600">
                        <thead class="bg-blueGray-50 text-xs uppercase tracking-[0.25em] text-blueGray-400">
                            <tr>
                                <th class="px-4 py-3 text-left">Project</th>
                                <th class="px-4 py-3 text-left">Path</th>
                                <th class="px-4 py-3 text-right">Monthly</th>
                                <th class="px-4 py-3 text-right">Δ Monthly</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-blueGray-100">
                            {#each costProjects as project}
                                <tr class="bg-white">
                                    <td class="px-4 py-3">{project?.name ?? '—'}</td>
                                    <td class="px-4 py-3 text-xs text-blueGray-500">{project?.path ?? '—'}</td>
                                    <td class="px-4 py-3 text-right">{formatCurrency(project?.monthly_cost ?? project?.hourly_cost)}</td>
                                    <td class="px-4 py-3 text-right">{formatCurrency(project?.diff_monthly_cost ?? project?.diff_hourly_cost)}</td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
            {/if}

            {#if costErrors.length}
                <details class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
                    <summary class="cursor-pointer font-semibold">Infracost warnings</summary>
                    <ul class="mt-2 list-disc space-y-1 pl-5 text-xs">
                        {#each costErrors as message}
                            <li>{message}</li>
                        {/each}
                    </ul>
                </details>
            {/if}
        </section>
    {/if}

    {#if driftSummary}
        <section class="space-y-3">
            <h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">Plan drift</h4>
            {#if driftError}
                <div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                    {driftError}
                </div>
            {:else}
                <div class="flex flex-wrap gap-3 text-xs text-blueGray-500">
                    <span class="rounded-xl border border-blueGray-200 px-3 py-1">Total changes: <strong class="text-blueGray-600">{(driftSummary as { total_changes?: number } | null)?.total_changes ?? 0}</strong></span>
                    <span class="rounded-xl border border-blueGray-200 px-3 py-1">Status: <strong class="text-blueGray-600">{driftHasChanges ? 'Changes detected' : 'No drift'}</strong></span>
                </div>

                {#if driftCountEntries.length}
                    <ul class="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
                        {#each driftCountEntries as [action, value]}
                            <li class="rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-600">
                                <span class="block text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">{action}</span>
                                <span class="mt-2 text-xl font-semibold text-blueGray-700">{value}</span>
                            </li>
                        {/each}
                    </ul>
                {/if}

                {#if driftResourceChanges.length}
                    <details class="rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-600">
                        <summary class="cursor-pointer font-semibold">Resource changes ({driftResourceChanges.length})</summary>
                        <div class="mt-2 space-y-2 text-xs">
                            {#each driftResourceChanges as change}
                                <div class="rounded-xl border border-blueGray-200 bg-white px-3 py-2">
                                    <p class="font-semibold text-blueGray-700">{(change?.address as string) ?? 'Unknown resource'}</p>
                                    <p class="text-blueGray-500">Action: {(change?.action as string) ?? (change?.actions?.join(', ') ?? '—')}</p>
                                </div>
                            {/each}
                        </div>
                    </details>
                {/if}

                {#if driftOutputChanges.length}
                    <details class="rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-600">
                        <summary class="cursor-pointer font-semibold">Output changes ({driftOutputChanges.length})</summary>
                        <div class="mt-2 space-y-2 text-xs">
                            {#each driftOutputChanges as output}
                                <div class="rounded-xl border border-blueGray-200 bg-white px-3 py-2">
                                    <p class="font-semibold text-blueGray-700">{output?.name ?? 'output'}</p>
                                    <p class="text-blueGray-500">Actions: {(output?.actions as string[] | undefined)?.join(', ') ?? '—'}</p>
                                </div>
                            {/each}
                        </div>
                    </details>
                {/if}
            {/if}
        </section>
    {/if}

	<details class="rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3 text-sm text-blueGray-500">
		<summary class="cursor-pointer text-blueGray-600 focus:outline-none">Raw summary payload</summary>
		<pre class="mt-3 overflow-auto rounded-xl bg-white p-3 text-xs text-blueGray-600">{JSON.stringify(summary, null, 2)}</pre>
	</details>
</section>
