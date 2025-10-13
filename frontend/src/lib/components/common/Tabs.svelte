<script lang="ts">
    import { createEventDispatcher } from 'svelte';
	interface TabItem {
		id: string;
		label: string;
	}

	interface Props {
		items: TabItem[];
		active: string;
	}

	const { items, active }: Props = $props();

    const dispatch = createEventDispatcher<{ change: { id: string } }>();

	const handleSelect = (id: string) => {
		if (id === active) return;
		dispatch('change', { id });
	};
</script>

<div class="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-1 text-sm font-semibold text-slate-500">
	{#each items as item (item.id)}
		<button
			type="button"
			class={`flex-1 rounded-xl px-4 py-2 transition ${
				item.id === active
					? 'bg-sky-500 text-white shadow-sm shadow-sky-300'
					: 'hover:bg-slate-50'
			}`}
			onclick={() => handleSelect(item.id)}
		>
			{item.label}
		</button>
	{/each}
</div>
