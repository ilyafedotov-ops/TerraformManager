<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { ProjectDetail, ProjectSummary } from '$lib/api/client';

	const {
		open = false,
		project = null,
		limit = 4
	}: {
		open?: boolean;
		project?: ProjectSummary | ProjectDetail | null;
		limit?: number;
	} = $props();

	const dispatch = createEventDispatcher<{ close: void }>();

	const projectId = $derived(project?.id ?? 'PROJECT_ID');
	const projectSlug = $derived(project?.slug ?? 'PROJECT_SLUG');
	const projectName = $derived(project?.name ?? 'Workspace');

	type CliCommand = { id: string; label: string; command: string };

	const cliCommands = $derived<CliCommand[]>(
		(() => {
			const slugLabel = projectSlug || 'PROJECT_SLUG';
			const idLabel = projectId || 'PROJECT_ID';
			return [
				{
					id: 'scan',
					label: 'Scan Terraform sample & log run',
					command: `python -m backend.cli scan sample --out tmp/${slugLabel}-report.json --save --project-slug ${slugLabel}`
				},
				{
					id: 'runs',
					label: 'List recorded project runs',
					command: `python -m backend.cli project runs --project-id ${idLabel} --limit 10`
				},
				{
					id: 'artifacts',
					label: 'Inspect run artifacts directory',
					command: `python -m backend.cli project artifacts --project-id ${idLabel} --run-id RUN_ID --path reports/`
				},
				{
					id: 'generator',
					label: 'Render generator via API bridge',
					command: `python -m backend.cli project generator --project-id ${idLabel} --slug aws/s3-secure-bucket --payload payloads/aws_s3.json --out tmp/aws_s3.tf`
				}
			].slice(0, limit);
		})()
	);

	const checklistItems = [
		{
			id: 'workspace',
			label: 'Terraform files stay under data/projects/<slug>/ to avoid leaking secrets.'
		},
		{
			id: 'evidence',
			label: 'Attach rendered HTML/JSON reports when sharing review artefacts.'
		},
		{
			id: 'docs',
			label: 'Reference knowledge/cli-workspace-workflows.md for onboarding + CLI hand-offs.'
		}
	];

	let checklistState = $state<Record<string, boolean>>({});

	const toggleChecklist = (id: string) => {
		checklistState = { ...checklistState, [id]: !checklistState[id] };
	};

	const handleBackdropClick = (event: MouseEvent) => {
		if (event.target === event.currentTarget) {
			dispatch('close');
		}
	};

	const handleBackdropKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Escape') {
			event.stopPropagation();
			event.preventDefault();
			dispatch('close');
		}
	};

	const close = () => dispatch('close');
</script>

{#if open}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 px-4 py-6"
		role="dialog"
		aria-modal="true"
		aria-label="Workspace guidance"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={handleBackdropKeyDown}
	>
		<div class="relative w-full max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl shadow-slate-900/20">
			<header class="mb-4 space-y-2">
				<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Workspace guidance</p>
				<h2 class="text-2xl font-semibold text-slate-800">CLI & verification tips for {projectName}</h2>
				<p class="text-sm text-slate-500">
					Run these commands from the repo root with your virtualenv active. They mirror the actions available in the SvelteKit UI so you can automate reviews and generator workflows.
				</p>
				<button
					type="button"
					class="absolute right-4 top-4 rounded-full border border-slate-200 p-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 transition hover:border-slate-300 hover:text-slate-700"
					onclick={close}
				>
					Close
				</button>
			</header>

			<section class="space-y-3">
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">CLI shortcuts</p>
				<ul class="space-y-3">
					{#each cliCommands as command (command.id)}
						<li class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
							<p class="text-sm font-semibold text-slate-700">{command.label}</p>
							<pre class="mt-2 overflow-auto rounded-xl bg-slate-900/95 p-3 text-xs text-slate-100">{command.command}</pre>
						</li>
					{/each}
				</ul>
			</section>

			<section class="mt-5 space-y-3">
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Manual checks</p>
				<ul class="space-y-2">
					{#each checklistItems as item}
						<li class="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-3">
							<input
								type="checkbox"
								class="mt-1 h-4 w-4 rounded border-slate-300 text-sky-500 focus:ring-sky-200"
								checked={Boolean(checklistState[item.id])}
								onchange={() => toggleChecklist(item.id)}
							/>
							<span class="text-sm text-slate-600">
								{item.label}
								{#if item.id === 'docs'}
									<a
										class="ml-1 text-sky-600 underline decoration-dotted hover:text-sky-500"
										href="/knowledge/cli-workspace-workflows"
										target="_blank"
										rel="noreferrer"
									>
										View doc
									</a>
								{/if}
							</span>
						</li>
					{/each}
				</ul>
			</section>
		</div>
	</div>
{/if}
