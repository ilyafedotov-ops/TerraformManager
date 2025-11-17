<script lang="ts">
	import { page } from '$app/stores';
	import { projectState } from '$lib/stores/project';
	import type { ProjectDetail, ProjectSummary } from '$lib/api/client';

	const { children, data } = $props();

	const project = data.project as ProjectSummary | ProjectDetail | null;
	const projectId = data.projectId as string;

	$effect(() => {
		if (project) {
			projectState.upsertProject(project);
			projectState.setActiveProject(project.id);
		}
	});

	const tabs = [
		{ id: 'dashboard', label: 'Overview', href: `/projects/${projectId}/dashboard`, match: /\/dashboard/ },
		{ id: 'generate', label: 'Generate', href: `/projects/${projectId}/generate`, match: /\/generate/ },
		{ id: 'review', label: 'Review', href: `/projects/${projectId}/review`, match: /\/review/ },
		{ id: 'reports', label: 'Reports', href: `/projects/${projectId}/reports`, match: /\/reports/ }
	];

	const activeTabId = $derived(
		tabs.find((entry) => entry.match.test($page.url.pathname))?.id ?? 'dashboard'
	);
</script>

<section class="space-y-6">
	<header class="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
		<div class="flex flex-col gap-2">
			<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">
				Project workspace
			</p>
			<h2 class="text-3xl font-semibold text-slate-700">{project?.name ?? 'Project'}</h2>
			{#if project?.description}
				<p class="text-sm text-slate-500">{project.description}</p>
			{/if}
		</div>
		<nav class="mt-6 flex flex-wrap gap-3 text-sm font-semibold text-slate-500">
			{#each tabs as tab}
				<a
					class={`rounded-2xl border px-4 py-2 transition ${
						activeTabId === tab.id
							? 'border-sky-300 bg-sky-50 text-sky-600'
							: 'border-slate-200 bg-white hover:border-sky-200 hover:text-sky-600'
					}`}
					href={tab.href}
				>
					{tab.label}
				</a>
			{/each}
		</nav>
	</header>

	<div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/30">
		{@render children?.()}
	</div>
</section>
