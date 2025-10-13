<script lang="ts">
	interface Segment {
		value: number;
		title: string;
		variant?: 'ok' | 'warning' | 'danger' | 'muted';
	}

	interface Props {
		segments: Segment[];
		total?: number;
	}

	const { segments, total = segments.reduce((sum, current) => sum + current.value, 0) }: Props = $props();

	const colors: Record<NonNullable<Segment['variant']>, string> = {
		ok: 'bg-emerald-400',
		warning: 'bg-amber-400',
		danger: 'bg-rose-500',
		muted: 'bg-slate-200'
	};
</script>

<div class="space-y-2">
	<div class="flex items-center justify-between text-xs uppercase tracking-[0.25em] text-slate-400">
		<span>Timeline</span>
		<span>Total {total}</span>
	</div>
	<div class="flex h-3 overflow-hidden rounded-full border border-slate-200 bg-slate-100">
		{#each segments as segment (segment.title)}
			<div
				class={`relative flex-1 ${colors[segment.variant ?? 'muted']}`}
				style={`width: ${(segment.value / total) * 100 || 0}%`}
				title={`${segment.title} (${segment.value})`}
			>
				<span class="sr-only">{segment.title}</span>
			</div>
		{/each}
	</div>
	<ul class="flex flex-wrap gap-4 text-[0.65rem] uppercase tracking-[0.2em] text-slate-400">
		{#each segments as segment (segment.title)}
			<li class="flex items-center gap-2">
				<span class={`h-2 w-2 rounded-full ${colors[segment.variant ?? 'muted']}`}></span>
				<span>{segment.title}</span>
			</li>
		{/each}
	</ul>
</div>
