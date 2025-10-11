<section class="space-y-10">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Reviewer</p>
		<h2 class="text-3xl font-semibold text-white">Upload Terraform for analysis</h2>
		<p class="max-w-2xl text-sm text-slate-400">
			This screen will replicate the Streamlit upload experience (multi-file drag-and-drop, zip extraction, optional
			terraform validate) and post to the FastAPI reviewer endpoints. For now, it outlines the planned layout.
		</p>
	</header>

	<div class="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
		<article class="space-y-6 rounded-3xl border border-dashed border-sky-500/30 bg-slate-900/60 p-10 text-center">
			<div class="mx-auto flex h-20 w-20 items-center justify-center rounded-3xl bg-sky-500/10 text-4xl text-sky-300">
				⇪
			</div>
			<h3 class="text-2xl font-semibold text-white">Drop Terraform files or archives</h3>
			<p class="text-sm text-slate-400">
				Support for drag-and-drop, paste, and file picker will land here. CLI parity (`python -m backend.cli scan`)
				remains available during the migration.
			</p>
			<div class="flex flex-wrap items-center justify-center gap-4 text-xs text-slate-400">
				<span class="rounded-full border border-white/10 px-3 py-1">.tf modules</span>
				<span class="rounded-full border border-white/10 px-3 py-1">.zip archives</span>
				<span class="rounded-full border border-white/10 px-3 py-1">terraform validate toggle</span>
				<span class="rounded-full border border-white/10 px-3 py-1">AI assistance (optional)</span>
			</div>
		</article>

		<aside class="space-y-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6">
			<section>
				<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Scan options</h4>
				<ul class="mt-3 space-y-3 text-sm text-slate-300">
					<li class="rounded-2xl bg-slate-900/60 px-4 py-3">
						<span class="font-semibold text-white">Terraform validate</span>
						<p class="text-xs text-slate-400">Runs when terraform binary is present on the host.</p>
					</li>
					<li class="rounded-2xl bg-slate-900/60 px-4 py-3">
						<span class="font-semibold text-white">AI explanations</span>
						<p class="text-xs text-slate-400">Surfaces LLM-generated guidance alongside deterministic findings.</p>
					</li>
					<li class="rounded-2xl bg-slate-900/60 px-4 py-3">
						<span class="font-semibold text-white">Patch export</span>
						<p class="text-xs text-slate-400">Download JSON or diff artifacts post-scan.</p>
					</li>
				</ul>
			</section>

			<section class="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4 text-xs text-sky-100">
				<p class="font-semibold uppercase tracking-[0.3em] text-sky-300">Heads up</p>
				<p class="mt-2">
					We will reuse the FastAPI `/scan` endpoint to maintain feature parity. The uploader will prepare the same
					payloads Streamlit emitted today.
				</p>
			</section>
		</aside>
	</div>
</section>
