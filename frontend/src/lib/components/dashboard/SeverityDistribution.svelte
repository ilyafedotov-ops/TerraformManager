<script lang="ts">
import Tabs from '$lib/components/common/Tabs.svelte';
import TrackerStrip from '$lib/components/dashboard/TrackerStrip.svelte';
import type { DashboardStats } from '$lib/types/dashboard';

/**
 * Display dashboard severity trends with tabbed time ranges and a proportional strip chart.
 */
interface Props {
    stats: DashboardStats | null;
    recentLimit?: number;
}

const props: Props = $props();

type TabDescriptor = { id: 'recent' | 'all'; label: string };
type TrackerSegment = { title: string; value: number; variant: 'danger' | 'warning' | 'ok' | 'muted' };

let severityEntries = $state<[string, number][]>([]);
let recentSeverityEntries = $state<[string, number][]>([]);
let severityTabs = $state<TabDescriptor[]>([{ id: 'all', label: 'All reports' }]);
let selectedTab = $state<TabDescriptor['id']>('all');

$effect(() => {
	const stats = props.stats ?? null;
	const limit = props.recentLimit ?? 5;

	if (!stats) {
		severityEntries = [];
		recentSeverityEntries = [];
		severityTabs = [{ id: 'all', label: 'All reports' }];
		if (selectedTab !== 'all') {
			selectedTab = 'all';
		}
		return;
	}

	const allEntries = Object.entries(stats.severityCounts ?? {})
		.map(([severity, value]) => [severity, Number(value ?? 0)] as [string, number])
		.sort((a, b) => b[1] - a[1]);

	const recentEntries = Object.entries(stats.recentSeverityCounts ?? {})
		.map(([severity, value]) => [severity, Number(value ?? 0)] as [string, number])
		.sort((a, b) => b[1] - a[1]);

	severityEntries = allEntries;
	recentSeverityEntries = recentEntries;

	const nextTabs: TabDescriptor[] = recentEntries.length
		? [
				{ id: 'recent', label: `Last ${Math.min(limit, stats.reports)} reports` },
				{ id: 'all', label: 'All reports' }
			]
		: [{ id: 'all', label: 'All reports' }];

	const tabsEqual =
		nextTabs.length === severityTabs.length &&
		nextTabs.every((tab, index) => tab.id === severityTabs[index]?.id && tab.label === severityTabs[index]?.label);

	if (!tabsEqual) {
		severityTabs = nextTabs;
	}

	if (!nextTabs.some((tab) => tab.id === selectedTab)) {
		selectedTab = nextTabs[0]?.id ?? 'all';
	}
});

$effect(() => {
	const stats = props.stats ?? null;
	const limit = props.recentLimit ?? 5;

});

const displayedEntries = $derived(
	(() =>
		selectedTab === 'recent' && recentSeverityEntries.length
			? recentSeverityEntries
			: severityEntries)()
);

const topSeverityCount = $derived(
	(() => (displayedEntries.length ? Math.max(displayedEntries[0][1], 1) : 1))()
);

const aggregatedLabel = $derived(
	(() => {
		const stats = props.stats ?? null;
		if (!stats) return '';
		const limit = props.recentLimit ?? 5;
		const aggregatedCount =
			selectedTab === 'recent' ? Math.min(stats.reports, limit) : stats.reports;
		return aggregatedCount
			? `Aggregated across ${aggregatedCount} report${aggregatedCount === 1 ? '' : 's'}.`
			: '';
	})()
);

const trackerSegments = $derived(
	(() => {
		if (!displayedEntries.length) {
			return [{ title: 'Idle', value: 1, variant: 'muted' }] as TrackerSegment[];
		}

		return displayedEntries.slice(0, 4).map(([severity, value]) => {
			const lower = severity.toLowerCase();
			const variant: TrackerSegment['variant'] =
				lower === 'critical' ? 'danger' : lower === 'high' ? 'warning' : 'ok';
			return { title: severity, value, variant } satisfies TrackerSegment;
		});
	})()
);

const trackerTotal = $derived(trackerSegments.reduce((sum, segment) => sum + segment.value, 0));
const trackerTitle = $derived(selectedTab === 'recent' ? 'Recent severity mix' : 'Overall severity mix');

const widthPercent = (count: number) => Math.min(100, (count / topSeverityCount) * 100);
</script>

<section class="space-y-4">
	<header class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
		<div>
			<h3 class="text-sm font-semibold uppercase tracking-[0.3em] text-blueGray-400">Severity distribution</h3>
			{#if aggregatedLabel}
				<p class="text-xs text-blueGray-500">{aggregatedLabel}</p>
			{/if}
		</div>
		{#if severityTabs.length > 1}
			<Tabs
				items={severityTabs}
				active={selectedTab}
				on:change={(event) => (selectedTab = event.detail.id as TabDescriptor['id'])}
			/>
		{/if}
	</header>

	{#if displayedEntries.length}
		<div class="space-y-3" data-testid="severity-entries">
			{#each displayedEntries as [severity, count]}
				<div class="flex items-center gap-4 rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-3">
					<div class="w-32 text-xs font-semibold uppercase tracking-[0.25em] text-blueGray-500">{severity}</div>
					<div class="relative h-2 flex-1 overflow-hidden rounded-full bg-blueGray-200">
						<div
							class="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600"
							style={`width: ${widthPercent(count)}%`}
						></div>
					</div>
					<div class="w-12 text-right font-semibold text-blueGray-600">{count}</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="rounded-3xl border border-blueGray-200 bg-blueGray-50 px-6 py-6 text-sm text-blueGray-500">
			Run your first scan to populate severity trends.
		</div>
	{/if}

	<div class="rounded-3xl border border-blueGray-200 bg-white p-6 shadow-xl shadow-blueGray-300/40">
		<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">{trackerTitle}</h4>
		<div class="mt-4">
			<TrackerStrip segments={trackerSegments} total={trackerTotal} />
		</div>
	</div>
</section>
