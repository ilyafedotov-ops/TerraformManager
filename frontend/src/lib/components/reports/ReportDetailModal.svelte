<script lang="ts">
import { createEventDispatcher } from 'svelte';
import ReportDetailView from './ReportDetailView.svelte';
import type { ReportDetail } from '$lib/api/client';

interface Props {
	token?: string | null;
	projectId?: string | null;
	projectSlug?: string | null;
	report?: ReportDetail | null;
	reportId?: string | null;
	error?: string | null;
	isOpen?: boolean;
}

const {
	token = null,
	projectId = null,
	projectSlug = null,
	report = null,
	reportId = null,
	error = null,
	isOpen = false
}: Props = $props();

const dispatch = createEventDispatcher<{ close: void }>();

const handleClose = () => {
	dispatch('close');
};

const handleBackdropClick = (event: MouseEvent) => {
	if (event.target === event.currentTarget) {
		handleClose();
	}
};
</script>

{#if isOpen}
	<div
		class="fixed inset-0 z-50 overflow-hidden"
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={(e) => e.key === 'Escape' && handleClose()}
	>
		<div class="absolute inset-0 overflow-hidden">
			<div class="absolute inset-0 bg-slate-900/20 backdrop-blur-sm transition-opacity" aria-hidden="true"></div>

			<div class="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
				<div class="pointer-events-auto w-screen max-w-6xl transform transition-transform">
					<div class="flex h-full flex-col overflow-y-scroll bg-slate-50 shadow-2xl">
						<div class="sticky top-0 z-10 border-b border-slate-200 bg-white px-6 py-4">
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-3">
									<button
										type="button"
										class="rounded-xl p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
										onclick={handleClose}
										aria-label="Close report details"
									>
										<svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
										</svg>
									</button>
									<div>
										<h2 class="text-xl font-semibold text-slate-700">Report Details</h2>
										{#if reportId}
											<p class="text-sm text-slate-500">ID: {reportId}</p>
										{/if}
									</div>
								</div>
								<div class="flex items-center gap-2">
									<button
										type="button"
										class="rounded-xl bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-200"
										onclick={handleClose}
									>
										Close
									</button>
								</div>
							</div>
						</div>

						<div class="flex-1 px-6 py-6">
							<ReportDetailView
								{token}
								{projectId}
								{projectSlug}
								{report}
								{reportId}
								{error}
								showWorkspaceBanner={false}
								backHref={null}
							/>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
