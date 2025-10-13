<script lang="ts">
	/** A step within the guided reviewer workflow timeline. */
	interface Step {
		title: string;
		description?: string;
		status?: 'completed' | 'current' | 'upcoming';
	}

interface Props {
	steps: readonly Step[];
}

const { steps }: Props = $props();
</script>

<nav aria-label="Workflow" class="space-y-3">
	<ul class="flex flex-col gap-3 md:flex-row md:items-start md:gap-6">
		{#each steps as step, index (step.title)}
			<li class="flex items-start gap-3">
				<div
					class={`flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-semibold ${
						step.status === 'completed'
							? 'border-emerald-400 bg-emerald-400 text-white'
							: step.status === 'current'
								? 'border-lightBlue-500 bg-lightBlue-500 text-white'
								: 'border-blueGray-200 bg-white text-blueGray-400'
					}`}
				>
					{index + 1}
				</div>
				<div class="flex-1">
					<p class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">{step.title}</p>
					{#if step.description}
						<p class="mt-1 text-xs text-blueGray-500">{step.description}</p>
					{/if}
				</div>
			</li>
		{/each}
	</ul>
</nav>
