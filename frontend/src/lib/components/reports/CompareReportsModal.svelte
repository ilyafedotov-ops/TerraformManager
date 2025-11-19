<script lang="ts">
import { createEventDispatcher } from 'svelte';
import ReportComparison from './ReportComparison.svelte';

interface Props {
	token?: string | null;
	projectId?: string | null;
	projectSlug?: string | null;
	isOpen?: boolean;
}

const {
	token = null,
	projectId = null,
	projectSlug = null,
	isOpen = false
}: Props = $props();

const dispatch = createEventDispatcher<{ close: void }>();

let compareBaseReportId = $state<string | null>(null);
let compareTargetReportId = $state<string | null>(null);

const handleClose = () => {
	compareBaseReportId = null;
	compareTargetReportId = null;
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
				<div class="pointer-events-auto w-screen max-w-7xl transform transition-transform">
					<div class="flex h-full flex-col overflow-y-scroll bg-slate-50 shadow-2xl">
						<div class="sticky top-0 z-10 border-b border-slate-200 bg-white px-6 py-4">
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-3">
									<button
										type="button"
										class="rounded-xl p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
										onclick={handleClose}
										aria-label="Close comparison modal"
									>
										<svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
										</svg>
									</button>
									<div>
										<h2 class="text-xl font-semibold text-slate-700">Compare Reports</h2>
										<p class="text-sm text-slate-500">Analyze differences between two scan reports</p>
									</div>
								</div>
								<button
									type="button"
									class="rounded-xl bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-200"
									onclick={handleClose}
								>
									Close
								</button>
							</div>
						</div>

						<div class="flex-1 space-y-6 px-6 py-6">
							<div class="rounded-2xl border border-sky-200 bg-sky-50 p-4">
								<p class="text-sm text-sky-700">
									<strong>Compare Mode:</strong> Enter the report IDs below to compare their findings side by side.
								</p>
							</div>

							<div class="grid gap-4 sm:grid-cols-2">
								<div>
									<label class="mb-2 block text-xs font-semibold uppercase tracking-[0.3em] text-slate-400" for="base-report-id">
										Base Report ID
									</label>
									<input
										id="base-report-id"
										type="text"
										class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 font-mono text-sm text-slate-700 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
										placeholder="Enter base report ID"
										bind:value={compareBaseReportId}
									/>
								</div>

								<div>
									<label class="mb-2 block text-xs font-semibold uppercase tracking-[0.3em] text-slate-400" for="compare-report-id">
										Compare Report ID
									</label>
									<input
										id="compare-report-id"
										type="text"
										class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 font-mono text-sm text-slate-700 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
										placeholder="Enter compare report ID"
										bind:value={compareTargetReportId}
									/>
								</div>
							</div>

							{#if compareBaseReportId && compareTargetReportId}
								<div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-lg">
									<ReportComparison
										{token}
										baseReportId={compareBaseReportId}
										compareReportId={compareTargetReportId}
									/>
								</div>
							{:else}
								<div class="rounded-3xl border border-slate-200 bg-white p-12 text-center">
									<svg class="mx-auto h-12 w-12 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
									</svg>
									<h3 class="mt-4 text-sm font-medium text-slate-700">Enter report IDs to compare</h3>
									<p class="mt-2 text-xs text-slate-500">Provide both base and target report IDs above to see the comparison</p>
								</div>
							{/if}
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
