<script lang="ts">
	const { params } = $props();
</script>

<section class="space-y-6">
	<header class="space-y-2">
		<a class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500 hover:text-sky-300" href="/reports">
			← Back to reports
		</a>
		<h2 class="text-3xl font-semibold text-white">Report {params.id}</h2>
		<p class="max-w-2xl text-sm text-slate-400">
			This view will embed the familiar HTML report and table viewer once the API wiring is complete. We&rsquo;ll also
			surface JSON/CSV download actions here.
		</p>
	</header>

	<div class="space-y-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40">
		<div class="grid gap-4 md:grid-cols-3">
			<div class="rounded-2xl border border-white/5 bg-slate-900/80 p-4">
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Issues found</p>
				<p class="mt-3 text-4xl font-semibold text-white">0</p>
			</div>
			<div class="rounded-2xl border border-white/5 bg-slate-900/80 p-4">
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Severity breakdown</p>
				<p class="mt-3 text-sm text-slate-300">awaiting data</p>
			</div>
			<div class="rounded-2xl border border-white/5 bg-slate-900/80 p-4">
				<p class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Generated</p>
				<p class="mt-3 text-sm text-slate-300">pending API response</p>
			</div>
		</div>

		<div class="rounded-2xl border border-dashed border-slate-700/60 bg-slate-900/50 p-6 text-sm text-slate-400">
			<p class="font-medium text-slate-200">Finding timeline</p>
			<p class="mt-2">
				The interactive findings table and diff preview will render here. The new frontend will reuse the FastAPI JSON
				and HTML endpoints to ensure full parity with the Streamlit/Jinja experiences.
			</p>
		</div>
	</div>
</section>
