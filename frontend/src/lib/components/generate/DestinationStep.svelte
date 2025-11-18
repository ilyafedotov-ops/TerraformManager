<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import type { ProjectSummary } from '$lib/api/client';

    const dispatch = createEventDispatcher();

    export let projects: ProjectSummary[] = [];
    export let activeProjectId: string | null = null;
    export let autoSaveEnabled = true;
    export let assetName = '';
    export let assetDescription = '';
    export let assetTags = '';
    export let hasContext = false;
    export let error: string | null = null;
    export let saving = false;

    const emit = (event: string, detail?: Record<string, unknown>) => {
        dispatch(event, detail ?? {});
    };
</script>

<section class="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
    <header class="space-y-2">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-sky-500">Destination</p>
        <h3 class="text-xl font-semibold text-slate-700">Choose where the module is stored</h3>
        <p class="text-sm text-slate-500">
            Confirm the workspace, naming, and metadata before heading to the review step. Toggle auto-save off if you only
            need a one-off download.
        </p>
    </header>

    <div class="grid gap-4 md:grid-cols-2">
        <label class="space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
            <span>Workspace project</span>
            <select
                class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700"
                value={activeProjectId ?? ''}
                onchange={(event) => emit('projectChange', { id: (event.currentTarget as HTMLSelectElement).value })}
            >
                {#if !projects.length}
                    <option value="" disabled>Loading projects…</option>
                {:else}
                    {#each projects as projectOption}
                        <option value={projectOption.id}>{projectOption.name}</option>
                    {/each}
                {/if}
            </select>
        </label>
        <label class="space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
            <span>Auto-save to project library</span>
            <button
                type="button"
                class={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-sm font-semibold transition ${
                    autoSaveEnabled
                        ? 'border-emerald-300 bg-emerald-50 text-emerald-600'
                        : 'border-slate-200 bg-white text-slate-500'
                }`}
                onclick={() => emit('toggleAutoSave', { enabled: !autoSaveEnabled })}
            >
                <span>{autoSaveEnabled ? 'Enabled — runs are saved with validation summaries.' : 'Disabled — runs only render Terraform.'}</span>
                <span class={`h-3 w-3 rounded-full ${autoSaveEnabled ? 'bg-emerald-500' : 'bg-slate-300'}`}></span>
            </button>
        </label>
    </div>

    {#if autoSaveEnabled}
        {#if hasContext}
            <div class="grid gap-4 md:grid-cols-2">
                <label class="space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                    <span>Asset name</span>
                    <input
                        class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700"
                        type="text"
                        value={assetName}
                        oninput={(event) => emit('assetNameChange', { value: (event.currentTarget as HTMLInputElement).value })}
                        placeholder="My Terraform module"
                    />
                </label>
                <label class="space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                    <span>Tags (comma separated)</span>
                    <input
                        class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700"
                        type="text"
                        value={assetTags}
                        oninput={(event) => emit('assetTagsChange', { value: (event.currentTarget as HTMLInputElement).value })}
                        placeholder="prod,baseline"
                    />
                </label>
                <label class="md:col-span-2 space-y-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">
                    <span>Description</span>
                    <textarea
                        class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700"
                        rows={3}
                        value={assetDescription}
                        oninput={(event) => emit('assetDescriptionChange', { value: (event.currentTarget as HTMLTextAreaElement).value })}
                    ></textarea>
                </label>
            </div>
            {#if error}
                <p class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-600">{error}</p>
            {/if}
            <div class="flex flex-wrap items-center gap-3">
                <button
                    type="button"
                    class="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-sky-300/50 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
                    onclick={() => emit('save')}
                    disabled={saving}
                >
                    {saving ? 'Saving…' : 'Save destination updates'}
                </button>
                <button
                    class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-sky-300 hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    type="button"
                    onclick={() => emit('goToReview')}
                >
                    Continue to review
                </button>
                <button
                    class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-sky-300 hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    type="button"
                    onclick={() => emit('goToConfigure')}
                >
                    Back to inputs
                </button>
            </div>
        {:else}
            <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                Generate the module with auto-save enabled to edit destination metadata and quick links.
            </div>
            <div class="flex flex-wrap gap-3">
                <button
                    class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-sky-300 hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    type="button"
                    onclick={() => emit('goToConfigure')}
                >
                    Back to inputs
                </button>
            </div>
        {/if}
    {:else}
        <div class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            Auto-save is disabled. The generator will render Terraform for download/copy without creating project runs or
            library assets.
        </div>
        <div class="flex flex-wrap gap-3">
            <button
                class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-sky-300 hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
                type="button"
                onclick={() => emit('goToConfigure')}
            >
                Back to inputs
            </button>
            <button
                class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-600 transition hover:border-sky-300 hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
                type="button"
                onclick={() => emit('goToReview')}
            >
                Continue to review
            </button>
        </div>
    {/if}
</section>
