<script lang="ts">
    /**
     * Present a single dashboard metric with optional accent colouring for emphasis.
     */
    interface Props {
        title: string;
        value: string | number;
        description?: string;
        accent?: 'default' | 'success' | 'warning' | 'danger';
    }

	const { title, value, description, accent = 'default' }: Props = $props();
	let accentClass = $state('border-blueGray-200 bg-blueGray-50 shadow-blueGray-300/40');

	$effect(() => {
		accentClass =
			accent === 'success'
				? 'border-emerald-200 bg-emerald-50 shadow-emerald-200/40'
				: accent === 'warning'
					? 'border-amber-200 bg-amber-50 shadow-amber-200/40'
					: accent === 'danger'
						? 'border-rose-200 bg-rose-50 shadow-rose-200/40'
						: 'border-blueGray-200 bg-blueGray-50 shadow-blueGray-300/40';
	});
</script>

<article class={`rounded-3xl border p-6 shadow-lg transition ${accentClass}`}>
	<p class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400">{title}</p>
	<p class="mt-4 text-4xl font-semibold text-blueGray-700">{value}</p>
	{#if description}
		<p class="mt-2 text-sm text-blueGray-500">{description}</p>
	{/if}
</article>
