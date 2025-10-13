<script lang="ts">
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { activeProject, projectState } from '$lib/stores/project';

	interface Props {
		context?: string;
		showManageLink?: boolean;
	}

	let { context = 'Runs and artifacts from this page will be linked to your active workspace.', showManageLink = true }: Props =
		$props();

	const projects = $derived($projectState.projects);
	const activeProjectId = $derived($activeProject?.id ?? '');
	const activeProjectName = $derived($activeProject?.name ?? null);
	const activeProjectSlug = $derived($activeProject?.slug ?? null);
	const projectCount = $derived(projects.length);

	const handleChange = (event: Event) => {
		const select = event.target as HTMLSelectElement;
		const value = select.value || null;
		projectState.setActiveProject(value);
	};

	const handleManageClick = async (event: MouseEvent) => {
		if (event.defaultPrevented) return;
		if (!browser) return;
		event.preventDefault();
		await goto('/projects');
	};
</script>

<section class="rounded-3xl border border-slate-200 bg-white px-6 py-5 shadow-sm shadow-slate-200">
	<div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
		<div class="space-y-1">
			<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Workspace</p>
			{#if projectCount}
				<p class="text-sm text-slate-500">{context}</p>
			{:else}
				<p class="text-sm text-slate-500">
					Create a project workspace to start tracking generator and review runs.
				</p>
			{/if}
		</div>
		<div class="flex flex-col gap-3 md:flex-row md:items-center">
			{#if projectCount}
				<div class="space-y-1 text-sm text-slate-600">
					<label
						class="block text-xs font-semibold uppercase tracking-[0.25em] text-slate-400"
						for="workspace-selector"
					>
						Active project
					</label>
					<select
						id="workspace-selector"
						class="w-64 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
						onchange={handleChange}
						value={activeProjectId}
					>
						<option value="">Select a project…</option>
						{#each projects as project (project.id)}
							<option value={project.id}>
								{project.name}
							</option>
						{/each}
					</select>
					{#if activeProjectName}
						<p class="text-xs text-slate-400">
							<span class="font-semibold text-slate-500">{activeProjectName}</span>
							{#if activeProjectSlug}
								<span class="ml-2 rounded-full border border-slate-200 bg-slate-50 px-2 py-[1px] text-[0.6rem] font-semibold uppercase tracking-[0.3em] text-slate-400">
									{activeProjectSlug}
								</span>
							{/if}
						</p>
					{/if}
				</div>
			{:else}
				<p class="text-sm text-slate-500">No projects found yet.</p>
			{/if}
			{#if showManageLink}
				<a
					class="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
					href="/projects"
					onclick={handleManageClick}
				>
					Manage projects
				</a>
			{/if}
		</div>
	</div>
</section>
