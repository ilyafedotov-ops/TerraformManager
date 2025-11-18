<script lang="ts">
	import ReportActions from '$lib/components/reports/ReportActions.svelte';
	import { API_BASE } from '$lib/api/client';
	import { notifyError, notifySuccess } from '$lib/stores/notifications';

	/**
	 * Render the outcome of a reviewer scan with severity distribution and export links.
	 */
export let reportId: string | null = null;
export let summary: Record<string, unknown> | null = null;
export let report: Record<string, unknown> | null = null;
export let severityEntries: Array<[string, number]> = [];
export let apiBase: string = API_BASE;
export let projectId: string | null = null;

	const summaryValue = (key: string): unknown => {
		if (!summary || typeof summary !== 'object') return null;
		return (summary as Record<string, unknown>)[key];
	};

	let assetId: string | null = null;
	$: assetId = (() => {
		const value = summaryValue('asset_id');
		return typeof value === 'string' ? value : null;
	})();

	let versionId: string | null = null;
	$: versionId = (() => {
		const value = summaryValue('version_id');
		return typeof value === 'string' ? value : null;
	})();

	let assetName: string | null = null;
	$: assetName = (() => {
		const value = summaryValue('asset_name');
		return typeof value === 'string' ? value : null;
	})();

	let assetType: string | null = null;
	$: assetType = (() => {
		const value = summaryValue('asset_type');
		return typeof value === 'string' ? value : null;
	})();

	let artifactPaths: string[] = [];
	$: artifactPaths = (() => {
		const value = summaryValue('artifacts');
		if (!value) return [];
		if (Array.isArray(value)) {
			return value.filter((entry): entry is string => typeof entry === 'string');
		}
		return [];
	})();

	let hasLibraryMetadata = false;
	$: hasLibraryMetadata = Boolean(assetId || versionId || artifactPaths.length);

	const copyValue = async (value: string, label: string) => {
		if (!value) return;
		if (typeof navigator === 'undefined' || !navigator.clipboard) {
			notifyError('Clipboard unavailable in this environment.');
			return;
		}
		try {
			await navigator.clipboard.writeText(value);
			notifySuccess(`${label} copied to clipboard.`, { duration: 2500 });
		} catch (error) {
			console.warn('Failed to copy value', error);
			notifyError(`Unable to copy ${label.toLowerCase()}.`);
		}
	};

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
		} catch (_error) {
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

<section class="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
	<header class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
		<div>
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Scan summary</p>
			<h3 class="text-xl font-semibold text-slate-700">{reportId ?? 'Unsaved result'}</h3>
		</div>
		{#if reportId}
			<ReportActions
				id={reportId}
				apiBase={apiBase}
				projectId={projectId ?? null}
				compact
				showDelete={false}
				showCopyJson
			/>
		{/if}
	</header>

	{#if hasLibraryMetadata}
		<section class="space-y-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
			<div class="flex flex-wrap items-center justify-between gap-4">
				<div class="space-y-1">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-emerald-500">Library asset</p>
					<p class="text-lg font-semibold text-emerald-900">{assetName ?? assetId ?? '—'}</p>
					<p class="text-xs text-emerald-700">
						{assetType ?? 'scan_report'} · version {versionId ?? 'latest'}
					</p>
				</div>
				<div class="flex flex-wrap gap-2 text-xs font-semibold">
					{#if assetId}
						<button
							type="button"
							class="rounded-xl border border-emerald-300 bg-white/70 px-3 py-1 text-emerald-700 transition hover:bg-white"
							on:click={() => copyValue(assetId ?? '', 'Asset ID')}
						>
							Copy asset id
						</button>
					{/if}
					{#if versionId}
						<button
							type="button"
							class="rounded-xl border border-emerald-300 bg-white/70 px-3 py-1 text-emerald-700 transition hover:bg-white"
							on:click={() => copyValue(versionId ?? '', 'Version ID')}
						>
							Copy version id
						</button>
					{/if}
				</div>
			</div>
			{#if artifactPaths.length}
				<div class="rounded-2xl border border-emerald-200/70 bg-white/80 px-4 py-3 text-xs text-emerald-800">
					<p class="text-[0.7rem] font-semibold uppercase tracking-[0.3em] text-emerald-500">Artifacts saved</p>
					<ul class="mt-2 space-y-1">
						{#each artifactPaths as artifact}
							<li class="flex items-center justify-between gap-3">
								<span class="truncate text-emerald-900">{artifact}</span>
								<button
									type="button"
									class="rounded-lg border border-emerald-200 px-2 py-1 text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-emerald-600"
									on:click={() => copyValue(artifact, 'Artifact path')}
								>
									Copy
								</button>
							</li>
						{/each}
					</ul>
				</div>
			{/if}
		</section>
	{/if}

	<div class="grid gap-4 md:grid-cols-3">
		<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Issues found</p>
			<p class="mt-3 text-3xl font-semibold text-slate-700">{issuesFound}</p>
		</div>
		<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Waived</p>
			<p class="mt-3 text-3xl font-semibold text-slate-700">{waivedCount}</p>
		</div>
		<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Files scanned</p>
			<p class="mt-3 text-3xl font-semibold text-slate-700">{filesScanned}</p>
		</div>
	</div>

	<section class="space-y-2">
		<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Severity distribution</h4>
		{#if severityEntries.length}
			<ul class="space-y-2 text-sm text-slate-600">
				{#each severityEntries as [severity, count]}
					<li class="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-2">
						<span class="uppercase tracking-[0.2em] text-slate-500">{severity}</span>
						<span class="font-semibold">{count}</span>
					</li>
				{/each}
			</ul>
		{:else}
			<p class="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
				No severity counts reported.
			</p>
		{/if}
	</section>

    {#if hasCost}
        <section class="space-y-3">
            <h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Cost insights</h4>
            <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Total monthly</p>
                    <p class="mt-2 text-2xl font-semibold">{formatCurrency(totalMonthlyCost)}</p>
                </div>
                <div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Δ monthly</p>
                    <p class="mt-2 text-2xl font-semibold">{formatCurrency(diffMonthlyCost)}</p>
                </div>
                <div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Total hourly</p>
                    <p class="mt-2 text-2xl font-semibold">{formatCurrency(totalHourlyCost)}</p>
                </div>
                <div class="rounded-2xl border border-slate-200 bg-sky-50 p-4 text-slate-700">
                    <p class="text-xs font-semibold uppercase tracking-[0.3em] text-sky-500">Δ hourly</p>
                    <p class="mt-2 text-2xl font-semibold">{formatCurrency(diffHourlyCost)}</p>
                </div>
            </div>

            {#if costProjects.length}
                <div class="overflow-x-auto rounded-2xl border border-slate-200">
                    <table class="min-w-full divide-y divide-slate-100 text-sm text-slate-600">
                        <thead class="bg-slate-50 text-xs uppercase tracking-[0.25em] text-slate-400">
                            <tr>
                                <th class="px-4 py-3 text-left">Project</th>
                                <th class="px-4 py-3 text-left">Path</th>
                                <th class="px-4 py-3 text-right">Monthly</th>
                                <th class="px-4 py-3 text-right">Δ Monthly</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100">
                            {#each costProjects as project}
                                <tr class="bg-white">
                                    <td class="px-4 py-3">{project?.name ?? '—'}</td>
                                    <td class="px-4 py-3 text-xs text-slate-500">{project?.path ?? '—'}</td>
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
            <h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Plan drift</h4>
            {#if driftError}
                <div class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                    {driftError}
                </div>
            {:else}
                <div class="flex flex-wrap gap-3 text-xs text-slate-500">
                    <span class="rounded-xl border border-slate-200 px-3 py-1">Total changes: <strong class="text-slate-600">{(driftSummary as { total_changes?: number } | null)?.total_changes ?? 0}</strong></span>
                    <span class="rounded-xl border border-slate-200 px-3 py-1">Status: <strong class="text-slate-600">{driftHasChanges ? 'Changes detected' : 'No drift'}</strong></span>
                </div>

                {#if driftCountEntries.length}
                    <ul class="grid gap-2 md:grid-cols-2 lg:grid-cols-4">
                        {#each driftCountEntries as [action, value]}
                            <li class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                                <span class="block text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">{action}</span>
                                <span class="mt-2 text-xl font-semibold text-slate-700">{value}</span>
                            </li>
                        {/each}
                    </ul>
                {/if}

                {#if driftResourceChanges.length}
                    <details class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                        <summary class="cursor-pointer font-semibold">Resource changes ({driftResourceChanges.length})</summary>
                        <div class="mt-2 space-y-2 text-xs">
                            {#each driftResourceChanges as change}
                                <div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
                                    <p class="font-semibold text-slate-700">{(change?.address as string) ?? 'Unknown resource'}</p>
                                    <p class="text-slate-500">
                                        Action:
                                        {change?.action ??
                                        (Array.isArray(change?.actions) ? change.actions.join(', ') : '—')}
                                    </p>
                                </div>
                            {/each}
                        </div>
                    </details>
                {/if}

                {#if driftOutputChanges.length}
                    <details class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                        <summary class="cursor-pointer font-semibold">Output changes ({driftOutputChanges.length})</summary>
                        <div class="mt-2 space-y-2 text-xs">
                            {#each driftOutputChanges as output}
                                <div class="rounded-xl border border-slate-200 bg-white px-3 py-2">
                                    <p class="font-semibold text-slate-700">{output?.name ?? 'output'}</p>
                                    <p class="text-slate-500">Actions: {(output?.actions as string[] | undefined)?.join(', ') ?? '—'}</p>
                                </div>
                            {/each}
                        </div>
                    </details>
                {/if}
            {/if}
        </section>
    {/if}

	<details class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
		<summary class="cursor-pointer text-slate-600 focus:outline-none">Raw summary payload</summary>
		<pre class="mt-3 overflow-auto rounded-xl bg-white p-3 text-xs text-slate-600">{JSON.stringify(summary, null, 2)}</pre>
	</details>
</section>
