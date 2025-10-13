<script lang="ts">
	const { children } = $props();
</script>

<div class="flex min-h-screen flex-col bg-slate-100 text-slate-700 lg:flex-row">
	<div class="relative hidden flex-1 flex-col justify-between overflow-hidden bg-gradient-to-br from-sky-500 via-indigo-500 to-blue-900 p-12 text-white lg:flex">
		<div class="relative z-10 flex items-center gap-3 text-lg font-semibold tracking-wide uppercase text-white/90">
			<span class="flex h-10 w-10 items-center justify-center rounded-xl bg-white/20 text-2xl leading-none">TF</span>
			Terraform Manager
		</div>
		<div class="relative z-10 mt-auto space-y-6">
			<h1 class="text-4xl font-semibold leading-tight text-white lg:text-5xl">
				Deploy secure infrastructure faster.
			</h1>
			<p class="max-w-xl text-lg text-white/80">
				Generate hardened Terraform baselines, review existing stacks, and surface remediation guidance from your
				internal knowledge base&mdash;all from one unified console.
			</p>
		</div>
		<div class="pointer-events-none absolute inset-0">
			<div class="blur-3xl absolute -top-24 -right-24 h-72 w-72 rounded-full bg-white/15"></div>
			<div class="blur-3xl absolute bottom-[-6rem] left-[-4rem] h-80 w-80 rounded-full bg-sky-300/20"></div>
		</div>
	</div>

	<div class="flex flex-1 items-center justify-center px-6 py-12 sm:px-12 lg:px-16">
		<div class="w-full max-w-lg space-y-10">
			<div class="flex items-center gap-3 text-slate-400 lg:hidden">
				<span class="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-100 text-2xl leading-none text-sky-500">
					TF
				</span>
				<div>
					<p class="text-sm font-semibold uppercase tracking-[0.3em] text-slate-400">Terraform Manager</p>
					<p class="text-lg font-semibold text-slate-700">Sign in to continue</p>
				</div>
			</div>
			<div class="rounded-3xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-200/50">
				{@render children?.()}
			</div>
		</div>
	</div>
</div>
