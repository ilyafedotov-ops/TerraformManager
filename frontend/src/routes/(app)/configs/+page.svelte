<section class="space-y-8">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Review configs</p>
		<h2 class="text-3xl font-semibold text-white">Tune thresholds & waivers</h2>
		<p class="max-w-2xl text-sm text-slate-400">
			This screen will pull configuration documents from the FastAPI `/configs` endpoints and surface in-line editing,
			diff previews, and export options. Until the API layer is wired, we present a Notus-themed shell.
		</p>
	</header>

	<div class="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
		<section class="space-y-4 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40">
			<header class="flex items-center justify-between">
				<h3 class="text-lg font-semibold text-white">Saved configs</h3>
				<button class="rounded-xl bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200 hover:bg-sky-500/20">
					New config
				</button>
			</header>
			<ul class="space-y-3 text-sm text-slate-300">
				<li class="flex items-center justify-between rounded-2xl border border-white/5 bg-slate-900/70 px-4 py-3">
					<div>
						<p class="font-semibold text-white">production-gates</p>
						<p class="text-xs text-slate-400">Fails on High/Critical</p>
					</div>
					<div class="flex items-center gap-2 text-xs">
						<button class="rounded-xl border border-white/10 px-3 py-1 text-slate-300 hover:border-sky-400/30 hover:text-sky-200">
							Edit
						</button>
						<button class="rounded-xl border border-rose-500/30 px-3 py-1 text-rose-300 hover:bg-rose-500/10">Delete</button>
					</div>
				</li>
				<li class="flex items-center justify-between rounded-2xl border border-white/5 bg-slate-900/70 px-4 py-3">
					<div>
						<p class="font-semibold text-white">sandbox</p>
						<p class="text-xs text-slate-400">Waives select IAM wildcard rules</p>
					</div>
					<div class="flex items-center gap-2 text-xs">
						<button class="rounded-xl border border-white/10 px-3 py-1 text-slate-300 hover:border-sky-400/30 hover:text-sky-200">
							Edit
						</button>
						<button class="rounded-xl border border-rose-500/30 px-3 py-1 text-rose-300 hover:bg-rose-500/10">Delete</button>
					</div>
				</li>
			</ul>
		</section>

		<aside class="space-y-4 rounded-3xl border border-white/5 bg-slate-950/70 p-6">
			<h4 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">Preview</h4>
			<pre class="max-h-72 overflow-auto rounded-2xl bg-slate-900/80 p-4 text-xs text-slate-300">
# YAML preview will render here
thresholds:
  high: fail
  medium: warn
waivers:
  - rule: AWS.S3.Encryption
    reason: "Replication buckets"
			</pre>

			<button class="w-full rounded-2xl bg-slate-900/80 px-4 py-3 text-xs font-semibold text-slate-200 ring-1 ring-white/5 transition hover:text-white hover:ring-sky-400/40">
				Preview with latest report
			</button>
		</aside>
	</div>
</section>
