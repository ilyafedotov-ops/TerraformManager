<script lang="ts">
	import '../app.css';
	import { onDestroy } from 'svelte';
	import { notifications, dismissNotification, type Notification } from '$lib/stores/notifications';

	const { children } = $props();

	let toasts = $state<Notification[]>([]);

	const unsubscribe = notifications.subscribe((items) => {
		toasts = items;
	});

	onDestroy(() => {
		unsubscribe();
	});

	const variantClass = (variant: Notification['variant']) => {
		switch (variant) {
			case 'success':
				return 'border-emerald-300 bg-emerald-50 text-emerald-700';
			case 'error':
				return 'border-rose-300 bg-rose-50 text-rose-700';
			default:
				return 'border-blueGray-200 bg-white text-blueGray-700';
		}
	};
	const handleDismiss = (id: number) => dismissNotification(id);
</script>

<div class="min-h-screen bg-blueGray-100 text-blueGray-700">
	{@render children?.()}

	{#if toasts.length}
		<div class="pointer-events-none fixed bottom-6 right-6 z-50 flex max-w-sm flex-col gap-4">
			{#each toasts as toast (toast.id)}
				<div
					class={`pointer-events-auto flex items-start gap-3 rounded-2xl border px-4 py-3 shadow-lg shadow-blueGray-300/30 transition ${variantClass(toast.variant)}`}
				>
					<div class="flex-1 text-sm">{toast.message}</div>
					<button
						type="button"
						class="rounded-full border border-blueGray-200 px-2 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-blueGray-500 hover:border-blueGray-300 hover:text-blueGray-700"
						onclick={() => handleDismiss(toast.id)}
					>
						Close
					</button>
				</div>
			{/each}
		</div>
	{/if}
</div>
