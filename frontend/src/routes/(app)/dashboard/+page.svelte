<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { projectState } from '$lib/stores/project';
	import type { ProjectSummary } from '$lib/api/client';
	import Icon from '$lib/components/navigation/Icon.svelte';

	const { data } = $props();
	const token = data.token as string | null;

	let projects = $state<ProjectSummary[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let selectedTimeRange = $state<'7d' | '30d' | '90d' | 'all'>('30d');
	let animateMetrics = $state(false);

	const totalProjects = $derived(projects.length);
	const totalRuns = $derived(projects.reduce((sum, p) => sum + (p.run_count ?? 0), 0));
	const totalAssets = $derived(projects.reduce((sum, p) => sum + (p.library_asset_count ?? 0), 0));
	const totalConfigs = $derived(projects.reduce((sum, p) => sum + (p.config_count ?? 0), 0));
	const totalArtifacts = $derived(projects.reduce((sum, p) => sum + (p.artifact_count ?? 0), 0));

	const activeProjects = $derived(projects.filter((p) => (p.run_count ?? 0) > 0));
	const inactiveProjects = $derived(projects.filter((p) => (p.run_count ?? 0) === 0));
	const projectsWithAssets = $derived(projects.filter((p) => (p.library_asset_count ?? 0) > 0));
	const projectsWithLatestRun = $derived(projects.filter((p) => p.latest_run));

	const recentProjects = $derived(
		[...projects]
			.filter((p) => p.last_activity_at)
			.sort((a, b) => {
				const dateA = a.last_activity_at ? new Date(a.last_activity_at).getTime() : 0;
				const dateB = b.last_activity_at ? new Date(b.last_activity_at).getTime() : 0;
				return dateB - dateA;
			})
			.slice(0, 8)
	);

	const topProjectsByRuns = $derived(
		[...projects]
			.sort((a, b) => (b.run_count ?? 0) - (a.run_count ?? 0))
			.slice(0, 5)
	);

	const topProjectsByAssets = $derived(
		[...projects]
			.sort((a, b) => (b.library_asset_count ?? 0) - (a.library_asset_count ?? 0))
			.slice(0, 5)
	);

	const activityTimeline = $derived.by(() => {
		const timeline = projects
			.filter((p) => p.latest_run)
			.map((p) => ({
				project: p,
				run: p.latest_run!,
				timestamp: new Date(p.latest_run!.created_at ?? p.last_activity_at ?? '').getTime()
			}))
			.sort((a, b) => b.timestamp - a.timestamp)
			.slice(0, 10);
		return timeline;
	});

	const statusDistribution = $derived.by(() => {
		const statuses: Record<string, number> = {};
		projects.forEach((p) => {
			if (p.latest_run?.status) {
				statuses[p.latest_run.status] = (statuses[p.latest_run.status] || 0) + 1;
			}
		});
		return statuses;
	});

	const healthScore = $derived.by(() => {
		if (totalProjects === 0) return 0;
		const score =
			(activeProjects.length / totalProjects) * 40 +
			(projectsWithAssets.length / totalProjects) * 30 +
			(projectsWithLatestRun.length / totalProjects) * 30;
		return Math.round(score);
	});

	const avgRunsPerProject = $derived(totalProjects > 0 ? totalRuns / totalProjects : 0);
	const avgAssetsPerProject = $derived(totalProjects > 0 ? totalAssets / totalProjects : 0);
	const avgConfigsPerProject = $derived(totalProjects > 0 ? totalConfigs / totalProjects : 0);

	onMount(async () => {
		if (!token) {
			error = 'Authentication required';
			loading = false;
			return;
		}

		try {
			await projectState.loadProjects(fetch, token);
			projects = $projectState.projects;
			await tick();
			animateMetrics = true;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load projects';
		} finally {
			loading = false;
		}
	});

	const handleProjectClick = async (slug: string) => {
		await goto(`/projects?project=${slug}&tab=overview`);
	};

	const formatDate = (dateStr: string | null | undefined) => {
		if (!dateStr) return 'Never';
		const date = new Date(dateStr);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / 60000);
		const diffHours = Math.floor(diffMs / 3600000);
		const diffDays = Math.floor(diffMs / 86400000);

		if (diffMins < 1) return 'Just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffHours < 24) return `${diffHours}h ago`;
		if (diffDays < 7) return `${diffDays}d ago`;
		return date.toLocaleDateString();
	};

	const formatDateTime = (dateStr: string | null | undefined) => {
		if (!dateStr) return 'Unknown';
		const date = new Date(dateStr);
		return date.toLocaleString('en-US', {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	};



	const getHealthColorClasses = (score: number) => {
		if (score >= 80) return {
			text: 'text-emerald-600',
			bg: 'bg-emerald-100',
			circle: 'text-emerald-500'
		};
		if (score >= 60) return {
			text: 'text-sky-600',
			bg: 'bg-sky-100',
			circle: 'text-sky-500'
		};
		if (score >= 40) return {
			text: 'text-amber-600',
			bg: 'bg-amber-100',
			circle: 'text-amber-500'
		};
		return {
			text: 'text-red-600',
			bg: 'bg-red-100',
			circle: 'text-red-500'
		};
	};

	const getStatusColorClasses = (status: string) => {
		const statusLower = status.toLowerCase();
		if (statusLower === 'success' || statusLower === 'completed') {
			return {
				dot: 'bg-emerald-500',
				bg: 'bg-emerald-100',
				text: 'text-emerald-700',
				bar: 'bg-emerald-500',
				ring: 'bg-emerald-100',
				border: 'border-emerald-300',
				hover: 'hover:bg-emerald-50',
				icon: 'text-emerald-500'
			};
		}
		if (statusLower === 'failed' || statusLower === 'error') {
			return {
				dot: 'bg-red-500',
				bg: 'bg-red-100',
				text: 'text-red-700',
				bar: 'bg-red-500',
				ring: 'bg-red-100',
				border: 'border-red-300',
				hover: 'hover:bg-red-50',
				icon: 'text-red-500'
			};
		}
		if (statusLower === 'running') {
			return {
				dot: 'bg-blue-500',
				bg: 'bg-blue-100',
				text: 'text-blue-700',
				bar: 'bg-blue-500',
				ring: 'bg-blue-100',
				border: 'border-blue-300',
				hover: 'hover:bg-blue-50',
				icon: 'text-blue-500'
			};
		}
		if (statusLower === 'pending') {
			return {
				dot: 'bg-amber-500',
				bg: 'bg-amber-100',
				text: 'text-amber-700',
				bar: 'bg-amber-500',
				ring: 'bg-amber-100',
				border: 'border-amber-300',
				hover: 'hover:bg-amber-50',
				icon: 'text-amber-500'
			};
		}
		return {
			dot: 'bg-slate-500',
			bg: 'bg-slate-100',
			text: 'text-slate-700',
			bar: 'bg-slate-500',
			ring: 'bg-slate-100',
			border: 'border-slate-300',
			hover: 'hover:bg-slate-50',
			icon: 'text-slate-500'
		};
	};
</script>

<div class="space-y-6">
	<div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
		<div>
			<h1 class="text-4xl font-bold tracking-tight text-slate-900">Global Dashboard</h1>
			<p class="mt-2 text-base text-slate-600">System-wide analytics and project insights</p>
		</div>
		<div class="flex flex-wrap items-center gap-3">
			<div class="flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-1">
				{#each (['7d', '30d', '90d', 'all'] as const) as range}
					<button
						type="button"
						class="rounded-lg px-4 py-2 text-xs font-semibold uppercase tracking-[0.15em] transition {selectedTimeRange === range ? 'bg-sky-500 text-white shadow-md' : 'text-slate-500 hover:bg-slate-100'}"
						onclick={() => (selectedTimeRange = range)}
					>
						{range === 'all' ? 'All Time' : range}
					</button>
				{/each}
			</div>
			<button
				type="button"
				class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-sky-50 hover:border-sky-300 hover:text-sky-700"
				onclick={() => goto('/projects')}
			>
				<Icon name="folder-tree" size={16} />
				Manage Projects
			</button>
		</div>
	</div>

	{#if loading}
		<div class="rounded-2xl border border-slate-200 bg-white p-12 text-center">
			<div class="inline-flex h-8 w-8 animate-spin items-center justify-center rounded-full border-4 border-slate-200 border-t-sky-500"></div>
			<p class="mt-4 text-sm text-slate-500">Loading dashboard...</p>
		</div>
	{:else if error}
		<div class="rounded-2xl border border-red-200 bg-red-50 p-6">
			<p class="text-sm font-semibold text-red-700">{error}</p>
		</div>
	{:else}
		<div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-sky-50 to-white p-6 shadow-sm transition hover:shadow-md">
				<div class="flex items-center justify-between">
					<div>
						<p class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">Projects</p>
						<p class="mt-2 text-3xl font-bold text-sky-700">{totalProjects}</p>
					</div>
					<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-sky-500 text-white shadow-lg shadow-sky-200">
						<Icon name="folder-tree" size={24} />
					</div>
				</div>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-purple-50 to-white p-6 shadow-sm transition hover:shadow-md">
				<div class="flex items-center justify-between">
					<div>
						<p class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">Total Runs</p>
						<p class="mt-2 text-3xl font-bold text-purple-700">{totalRuns}</p>
					</div>
					<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-purple-500 text-white shadow-lg shadow-purple-200">
						<Icon name="zap" size={24} />
					</div>
				</div>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-emerald-50 to-white p-6 shadow-sm transition hover:shadow-md">
				<div class="flex items-center justify-between">
					<div>
						<p class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">Assets</p>
						<p class="mt-2 text-3xl font-bold text-emerald-700">{totalAssets}</p>
					</div>
					<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-lg shadow-emerald-200">
						<Icon name="package" size={24} />
					</div>
				</div>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-amber-50 to-white p-6 shadow-sm transition hover:shadow-md">
				<div class="flex items-center justify-between">
					<div>
						<p class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">Configs</p>
						<p class="mt-2 text-3xl font-bold text-amber-700">{totalConfigs}</p>
					</div>
					<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500 text-white shadow-lg shadow-amber-200">
						<Icon name="settings" size={24} />
					</div>
				</div>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-rose-50 to-white p-6 shadow-sm transition hover:shadow-md">
				<div class="flex items-center justify-between">
					<div>
						<p class="text-xs font-semibold uppercase tracking-[0.25em] text-slate-500">Artifacts</p>
						<p class="mt-2 text-3xl font-bold text-rose-700">{totalArtifacts}</p>
					</div>
					<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-rose-500 text-white shadow-lg shadow-rose-200">
						<Icon name="file-text" size={24} />
					</div>
				</div>
			</div>
		</div>

		<!-- Health Score & Status Distribution -->
		<div class="grid gap-6 lg:grid-cols-3">
			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-6 shadow-sm">
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-lg font-bold text-slate-800">System Health</h3>
					<div class={`flex h-8 w-8 items-center justify-center rounded-lg ${getHealthColorClasses(healthScore).bg}`}>
						<Icon name="activity" size={16} class={getHealthColorClasses(healthScore).text} />
					</div>
				</div>
				<div class="relative">
					<div class="flex items-center justify-center">
						<div class="relative h-40 w-40">
							<svg class="h-full w-full -rotate-90 transform">
								<circle
									cx="80"
									cy="80"
									r="70"
									stroke="currentColor"
									stroke-width="12"
									fill="transparent"
									class="text-slate-200"
								/>
								<circle
									cx="80"
									cy="80"
									r="70"
									stroke="currentColor"
									stroke-width="12"
									fill="transparent"
									stroke-dasharray={2 * Math.PI * 70}
									stroke-dashoffset={2 * Math.PI * 70 * (1 - healthScore / 100)}
									class={`${getHealthColorClasses(healthScore).circle} transition-all duration-1000`}
									stroke-linecap="round"
								/>
							</svg>
							<div class="absolute inset-0 flex flex-col items-center justify-center">
								<span class="text-4xl font-bold {getHealthColorClasses(healthScore).text}">{healthScore}</span>
								<span class="text-xs font-semibold uppercase tracking-wider text-slate-500">Score</span>
							</div>
						</div>
					</div>
					<div class="mt-4 grid grid-cols-3 gap-2 text-center">
						<div class="rounded-lg bg-slate-50 p-2">
							<p class="text-xs text-slate-500">Active</p>
							<p class="text-sm font-bold text-slate-700">{activeProjects.length}</p>
						</div>
						<div class="rounded-lg bg-slate-50 p-2">
							<p class="text-xs text-slate-500">w/ Assets</p>
							<p class="text-sm font-bold text-slate-700">{projectsWithAssets.length}</p>
						</div>
						<div class="rounded-lg bg-slate-50 p-2">
							<p class="text-xs text-slate-500">Recent</p>
							<p class="text-sm font-bold text-slate-700">{projectsWithLatestRun.length}</p>
						</div>
					</div>
				</div>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-lg font-bold text-slate-800">Run Status Distribution</h3>
					<span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
						Latest Runs
					</span>
				</div>
				{#if Object.keys(statusDistribution).length === 0}
					<div class="flex h-48 items-center justify-center">
						<p class="text-sm text-slate-400">No run data available</p>
					</div>
				{:else}
					<div class="space-y-3">
						{#each Object.entries(statusDistribution) as [status, count]}
							{@const percentage = (count / projectsWithLatestRun.length) * 100}
							{@const colorClasses = getStatusColorClasses(status)}
							<div class="space-y-2">
								<div class="flex items-center justify-between">
									<div class="flex items-center gap-2">
										<div class="h-3 w-3 rounded-full {colorClasses.dot}"></div>
										<span class="text-sm font-semibold capitalize text-slate-700">{status}</span>
									</div>
									<div class="flex items-center gap-3">
										<span class="text-sm font-bold text-slate-600">{count}</span>
										<span class="w-12 text-right text-xs text-slate-500">{percentage.toFixed(0)}%</span>
									</div>
								</div>
								<div class="h-2 w-full overflow-hidden rounded-full bg-slate-100">
									<div
										class="h-full rounded-full {colorClasses.bar} transition-all duration-700"
										style="width: {percentage}%"
									></div>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>

		<!-- Top Projects & Activity Timeline -->
		<div class="grid gap-6 lg:grid-cols-2">
			<div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-lg font-bold text-slate-800">Top Projects by Runs</h3>
					<Icon name="trending-up" size={18} class="text-purple-500" />
				</div>
				{#if topProjectsByRuns.length === 0}
					<p class="py-8 text-center text-sm text-slate-400">No projects with runs</p>
				{:else}
					<div class="space-y-3">
						{#each topProjectsByRuns as project, index (project.id)}
							{@const maxRuns = topProjectsByRuns[0]?.run_count ?? 1}
							{@const percentage = ((project.run_count ?? 0) / maxRuns) * 100}
							<button
								type="button"
								class="group w-full text-left transition"
								onclick={() => handleProjectClick(project.slug)}
							>
								<div class="flex items-center gap-3">
									<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-purple-500 to-purple-600 text-xs font-bold text-white shadow-md">
										#{index + 1}
									</div>
									<div class="min-w-0 flex-1">
										<div class="mb-1 flex items-center justify-between">
											<p class="truncate font-semibold text-slate-700 group-hover:text-purple-600">{project.name}</p>
											<span class="ml-2 shrink-0 text-sm font-bold text-purple-600">{project.run_count ?? 0}</span>
										</div>
										<div class="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
											<div
												class="h-full rounded-full bg-gradient-to-r from-purple-500 to-purple-600 transition-all duration-700"
												style="width: {percentage}%"
											></div>
										</div>
									</div>
								</div>
							</button>
						{/each}
					</div>
				{/if}
			</div>

			<div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-lg font-bold text-slate-800">Top Projects by Assets</h3>
					<Icon name="package" size={18} class="text-emerald-500" />
				</div>
				{#if topProjectsByAssets.length === 0}
					<p class="py-8 text-center text-sm text-slate-400">No projects with assets</p>
				{:else}
					<div class="space-y-3">
						{#each topProjectsByAssets as project, index (project.id)}
							{@const maxAssets = topProjectsByAssets[0]?.library_asset_count ?? 1}
							{@const percentage = ((project.library_asset_count ?? 0) / maxAssets) * 100}
							<button
								type="button"
								class="group w-full text-left transition"
								onclick={() => handleProjectClick(project.slug)}
							>
								<div class="flex items-center gap-3">
									<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 text-xs font-bold text-white shadow-md">
										#{index + 1}
									</div>
									<div class="min-w-0 flex-1">
										<div class="mb-1 flex items-center justify-between">
											<p class="truncate font-semibold text-slate-700 group-hover:text-emerald-600">{project.name}</p>
											<span class="ml-2 shrink-0 text-sm font-bold text-emerald-600">{project.library_asset_count ?? 0}</span>
										</div>
										<div class="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
											<div
												class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-emerald-600 transition-all duration-700"
												style="width: {percentage}%"
											></div>
										</div>
									</div>
								</div>
							</button>
						{/each}
					</div>
				{/if}
			</div>
		</div>

		<!-- Recent Activity Timeline -->
		<div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
			<div class="mb-4 flex items-center justify-between">
				<h3 class="text-lg font-bold text-slate-800">Activity Timeline</h3>
				<span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
					Recent 10
				</span>
			</div>
			{#if activityTimeline.length === 0}
				<p class="py-8 text-center text-sm text-slate-400">No recent activity</p>
			{:else}
				<div class="space-y-4">
					{#each activityTimeline as item (item.run.id)}
						{@const colorClasses = getStatusColorClasses(item.run.status ?? 'unknown')}
						<div class="group relative flex gap-4">
							<div class="flex flex-col items-center">
								<div class="flex h-10 w-10 items-center justify-center rounded-full {colorClasses.ring} ring-4 ring-white">
									<div class="h-3 w-3 rounded-full {colorClasses.dot}"></div>
								</div>
								<div class="h-full w-0.5 bg-slate-200 group-last:bg-transparent"></div>
							</div>
							<button
								type="button"
								class="flex-1 rounded-xl border border-slate-200 bg-slate-50 p-4 text-left transition {colorClasses.hover} {colorClasses.border}"
								onclick={() => handleProjectClick(item.project.slug)}
							>
								<div class="flex items-start justify-between gap-4">
									<div class="min-w-0 flex-1">
										<div class="flex items-center gap-2">
											<p class="font-semibold text-slate-800">{item.project.name}</p>
											<span class="rounded-full {colorClasses.bg} px-2 py-0.5 text-xs font-semibold capitalize {colorClasses.text}">
												{item.run.status}
											</span>
										</div>
										<p class="mt-1 text-sm text-slate-600">
											Run #{item.run.id} • scan
										</p>
										<p class="mt-1 text-xs text-slate-500">{formatDateTime(item.run.created_at)}</p>
									</div>
									<Icon name="chevron-right" size={16} class="shrink-0 text-slate-400 transition group-hover:{colorClasses.icon}" />
								</div>
							</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Quick Stats Grid -->
		<div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-6 shadow-sm">
				<div class="flex items-center gap-3">
					<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-sky-100">
						<Icon name="bar-chart-3" size={24} class="text-sky-600" />
					</div>
					<div>
						<p class="text-xs font-semibold uppercase tracking-wider text-slate-500">Avg Runs</p>
						<p class="text-2xl font-bold text-slate-800">{avgRunsPerProject.toFixed(1)}</p>
					</div>
				</div>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-6 shadow-sm">
				<div class="flex items-center gap-3">
					<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-100">
						<Icon name="layers" size={24} class="text-emerald-600" />
					</div>
					<div>
						<p class="text-xs font-semibold uppercase tracking-wider text-slate-500">Avg Assets</p>
						<p class="text-2xl font-bold text-slate-800">{avgAssetsPerProject.toFixed(1)}</p>
					</div>
				</div>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-6 shadow-sm">
				<div class="flex items-center gap-3">
					<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-100">
						<Icon name="sliders" size={24} class="text-amber-600" />
					</div>
					<div>
						<p class="text-xs font-semibold uppercase tracking-wider text-slate-500">Avg Configs</p>
						<p class="text-2xl font-bold text-slate-800">{avgConfigsPerProject.toFixed(1)}</p>
					</div>
				</div>
			</div>

			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-6 shadow-sm">
				<div class="flex items-center gap-3">
					<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-purple-100">
						<Icon name="check-circle" size={24} class="text-purple-600" />
					</div>
					<div>
						<p class="text-xs font-semibold uppercase tracking-wider text-slate-500">Active Rate</p>
						<p class="text-2xl font-bold text-slate-800">
							{totalProjects > 0 ? ((activeProjects.length / totalProjects) * 100).toFixed(0) : 0}%
						</p>
					</div>
				</div>
			</div>
		</div>

		{#if totalProjects === 0}
			<div class="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-12 text-center">
				<div class="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
					<Icon name="folder-tree" size={40} />
				</div>
				<h3 class="mt-6 text-xl font-bold text-slate-700">No Projects Yet</h3>
				<p class="mt-2 text-sm text-slate-500">Get started by creating your first project workspace</p>
				<button
					type="button"
					class="mt-6 inline-flex items-center gap-2 rounded-xl bg-sky-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-200 transition hover:bg-sky-600"
					onclick={() => goto('/projects')}
				>
					<Icon name="plus" size={16} />
					Create Project
				</button>
			</div>
		{/if}
	{/if}
</div>
