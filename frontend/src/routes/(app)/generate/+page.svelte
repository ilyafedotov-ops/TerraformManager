<script lang="ts">
	const categories = [
		{
			name: 'AWS',
			items: ['S3 baseline', 'VPC networking', 'ALB + WAF', 'RDS multi-region', 'EKS cluster']
		},
		{
			name: 'Azure',
			items: ['Key Vault secure defaults', 'Diagnostics baseline', 'AKS cluster']
		},
		{
			name: 'Kubernetes / On-Prem',
			items: ['Namespace hardening', 'Deployment baseline', 'Pod security admission']
		}
	];
</script>

<section class="space-y-10">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Blueprint Studio</p>
		<h2 class="text-3xl font-semibold text-white">Generate hardened Terraform modules</h2>
		<p class="max-w-2xl text-sm text-slate-400">
			Streamlit-era forms captured all generator inputs on the server. This SvelteKit view will progressively enhance
			the experience and call new FastAPI generator endpoints as they come online.
		</p>
	</header>

	<div class="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
		<article class="space-y-6 rounded-3xl border border-white/5 bg-slate-900/70 p-6 shadow-xl shadow-slate-950/40">
			<h3 class="text-lg font-semibold text-white">Selector preview</h3>
			<p class="text-sm text-slate-400">
				Each generator will map 1:1 with the existing backend Jinja templates. Expect nested field groups, provider
				defaults, and validation borrowed from Streamlit widgets.
			</p>
			<div class="grid gap-4 md:grid-cols-2">
				{#each categories as category}
					<section class="space-y-2 rounded-2xl border border-white/5 bg-slate-950/80 p-4">
						<h4 class="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">{category.name}</h4>
						<ul class="space-y-2 text-sm text-slate-300">
							{#each category.items as item}
								<li class="flex items-center gap-2 rounded-xl bg-slate-900/60 px-3 py-2">
									<span class="h-2.5 w-2.5 rounded-full bg-sky-400/60"></span>
									{item}
								</li>
							{/each}
						</ul>
					</section>
				{/each}
			</div>
		</article>

		<aside class="space-y-4 rounded-3xl border border-white/5 bg-slate-950/80 p-6">
			<h4 class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-500">Coming soon</h4>
			<ul class="space-y-3 text-xs text-slate-400">
				<li>• Multi-step wizards with Notus tabs</li>
				<li>• Terraform backend (remote state) toggles</li>
				<li>• Download-ready archives immediately after generation</li>
				<li>• AI explanation toggles wired to backend LLM settings</li>
			</ul>
		</aside>
	</div>
</section>
