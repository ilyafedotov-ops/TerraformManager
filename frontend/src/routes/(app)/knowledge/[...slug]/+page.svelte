<script lang="ts">
	const { data, params } = $props();
	const doc = data.doc as { path: string; title: string; content: string } | null;
	const error = data.error as string | null;

	const sourcePath = params.slug
		.split('/')
		.map((segment) => decodeURIComponent(segment))
		.join('/');

	let copyStatus = $state<string | null>(null);

	const copyContent = async () => {
		if (!doc) return;
		copyStatus = null;
		try {
			await navigator.clipboard.writeText(doc.content);
			copyStatus = 'Copied to clipboard.';
		} catch (err) {
			copyStatus = err instanceof Error ? err.message : 'Unable to copy content.';
		}
	};
</script>

<section class="space-y-6">
	<header class="space-y-2">
		<a class="text-xs font-semibold uppercase tracking-[0.3em] text-blueGray-400 hover:text-lightBlue-500" href="/knowledge">
			← Back to knowledge search
		</a>
		<h2 class="text-3xl font-semibold text-blueGray-700">{doc?.title ?? 'Knowledge document'}</h2>
		<p class="text-sm text-blueGray-500">
			Source path:
			<code class="rounded bg-blueGray-50 px-1 py-0.5 text-xs text-blueGray-600">{sourcePath}</code>
		</p>
	</header>

	{#if error}
		<div class="rounded-3xl border border-rose-300 bg-rose-50 px-6 py-4 text-sm text-rose-700">
			<strong class="font-semibold">Unable to load document.</strong>
			<span class="ml-2 text-rose-600">{error}</span>
		</div>
	{/if}

	{#if doc}
		<div class="space-y-4 rounded-3xl border border-blueGray-200 bg-white p-6 shadow-xl shadow-blueGray-300/40">
			<div class="flex flex-wrap items-center justify-between gap-3">
				<h3 class="text-base font-semibold text-blueGray-700">{doc.title}</h3>
				<button
					class="inline-flex items-center gap-2 rounded-2xl border border-blueGray-200 px-4 py-2 text-xs font-semibold text-blueGray-600 transition hover:bg-lightBlue-500 hover:text-white"
					type="button"
					onclick={copyContent}
				>
					Copy content
				</button>
			</div>
			<article class="prose max-w-none whitespace-pre-wrap rounded-2xl bg-blueGray-50 p-4 text-sm text-blueGray-700">
				{doc.content}
			</article>
			{#if copyStatus}
				<div class="rounded-2xl border border-blueGray-200 bg-blueGray-50 px-4 py-2 text-xs text-blueGray-600">{copyStatus}</div>
			{/if}
		</div>
	{:else if !error}
		<div class="rounded-3xl border border-blueGray-200 bg-white px-6 py-6 text-sm text-blueGray-500">
			Loading document...
		</div>
	{/if}
</section>
