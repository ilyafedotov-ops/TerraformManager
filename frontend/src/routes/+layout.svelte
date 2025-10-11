<script>
	import '../app.css';
	const { children } = $props();
</script>

<div class="min-h-screen bg-slate-900 text-slate-100">
	{@render children?.()}
</div>
