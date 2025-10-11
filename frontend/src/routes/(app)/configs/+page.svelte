<script lang="ts">
    import {
        deleteReviewConfig,
        previewConfigApplication,
        saveReviewConfig,
        type ReviewConfigRecord
    } from '$lib/api/client';

    const { data } = $props();
    const token = data.token as string | null;
    let configs = $state<ReviewConfigRecord[]>(data.configs ?? []);
    let loadError = $state<string | null>(data.error ?? null);

    let selectedName = $state<string>('');
    let editorPayload = $state<string>('# thresholds:\n#   high: fail\n');
    let configKind = $state<string>('tfreview');

    let saveStatus = $state<string | null>(null);
    let previewStatus = $state<string | null>(null);
    let previewResult = $state<{ before: Record<string, unknown>; after: Record<string, unknown> } | null>(null);
    let reportId = $state('');
    let isSaving = $state(false);
    let isDeleting = $state(false);
    let isPreviewing = $state(false);

    const setActiveConfig = (name: string) => {
        const record = configs.find((cfg) => cfg.name === name);
        if (!record) return;
        selectedName = record.name;
        editorPayload = record.payload;
        configKind = record.kind ?? 'tfreview';
        saveStatus = null;
        previewStatus = null;
        previewResult = null;
    };

    const startNewConfig = () => {
        selectedName = '';
        editorPayload = '# thresholds:\n#   high: fail\n';
        configKind = 'tfreview';
        saveStatus = null;
        previewStatus = null;
        previewResult = null;
    };

    const handleSave = async () => {
        if (!token) {
            saveStatus = 'API token missing; configure authentication to save configs.';
            return;
        }
        if (!selectedName.trim()) {
            saveStatus = 'Config name is required.';
            return;
        }
        if (!editorPayload.trim()) {
            saveStatus = 'Config payload cannot be empty.';
            return;
        }
        isSaving = true;
        try {
            await saveReviewConfig(fetch, token, {
                name: selectedName.trim(),
                payload: editorPayload,
                kind: configKind
            });
            const updatedIndex = configs.findIndex((cfg) => cfg.name === selectedName);
            const record: ReviewConfigRecord = {
                name: selectedName.trim(),
                payload: editorPayload,
                kind: configKind
            };
            if (updatedIndex >= 0) {
                configs = [...configs.slice(0, updatedIndex), record, ...configs.slice(updatedIndex + 1)];
            } else {
                configs = [...configs, record];
            }
            saveStatus = 'Config saved successfully.';
        } catch (error) {
            saveStatus = error instanceof Error ? error.message : 'Failed to save config.';
        } finally {
            isSaving = false;
        }
    };

    const handleDelete = async (name: string) => {
        if (!token) {
            saveStatus = 'API token missing; cannot delete configs.';
            return;
        }
        isDeleting = true;
        try {
            await deleteReviewConfig(fetch, token, name);
            configs = configs.filter((cfg) => cfg.name !== name);
            if (selectedName === name) {
                startNewConfig();
            }
            saveStatus = 'Config deleted.';
        } catch (error) {
            saveStatus = error instanceof Error ? error.message : 'Failed to delete config.';
        } finally {
            isDeleting = false;
        }
    };

    const handlePreview = async () => {
        if (!token) {
            previewStatus = 'API token missing; cannot preview configs.';
            return;
        }
        if (!selectedName.trim() || !configs.find((cfg) => cfg.name === selectedName)) {
            previewStatus = 'Save the config before running a preview.';
            return;
        }
        isPreviewing = true;
        previewStatus = null;
        previewResult = null;
        try {
            const response = await previewConfigApplication(fetch, token, {
                config_name: selectedName.trim(),
                report_id: reportId.trim() || null,
                paths: null
            });
            previewResult = {
                before: response.summary.before,
                after: response.summary.after
            };
            previewStatus = 'Preview completed.';
        } catch (error) {
            previewStatus = error instanceof Error ? error.message : 'Failed to generate preview.';
        } finally {
            isPreviewing = false;
        }
    };

    $effect(() => {
        if (configs.length && !selectedName) {
            setActiveConfig(configs[0].name);
        }
    });
</script>

<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Review configs</p>
        <h2 class="text-3xl font-semibold text-white">Tune thresholds & waivers</h2>
        <p class="max-w-2xl text-sm text-slate-400">
            Manage stored `tfreview.yaml` profiles used to control severity gates and waivers. Save changes to persist in the
            SQLite store, then preview against existing reports using the reviewer backend.
        </p>
    </header>

    {#if loadError}
        <div class="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-xs text-rose-100">{loadError}</div>
    {/if}

    <div class="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <section class="space-y-4 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40">
            <header class="flex items-center justify-between">
                <h3 class="text-lg font-semibold text-white">Saved configs</h3>
                <button class="rounded-xl bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-500/20" type="button" onclick={startNewConfig}>
                    New config
                </button>
            </header>
            <ul class="space-y-3 text-sm text-slate-300">
                {#if configs.length === 0}
                    <li class="rounded-2xl border border-dashed border-white/10 bg-slate-900/60 px-4 py-3 text-xs text-slate-400">
                        No configs saved yet. Create one using the editor on the right.
                    </li>
                {:else}
                    {#each configs as cfg (cfg.name)}
                        <li class={`flex items-start justify-between gap-3 rounded-2xl border px-4 py-3 transition ${cfg.name === selectedName ? 'border-sky-400/40 bg-slate-900/70' : 'border-white/5 bg-slate-900/60 hover:border-sky-400/20'}`}>
                            <div class="space-y-1">
                                <button class="text-left text-sm font-semibold text-white" type="button" onclick={() => setActiveConfig(cfg.name)}>
                                    {cfg.name}
                                </button>
                                <p class="text-xs text-slate-400">{cfg.payload.split('\n', 1)[0] || 'Config payload'}</p>
                            </div>
                            <button
                                class="rounded-xl border border-rose-500/40 px-3 py-1 text-xs text-rose-200 transition hover:bg-rose-500/10 disabled:cursor-not-allowed disabled:opacity-60"
                                type="button"
                                onclick={() => handleDelete(cfg.name)}
                                disabled={isDeleting}
                            >
                                Delete
                            </button>
                        </li>
                    {/each}
                {/if}
            </ul>
        </section>

        <aside class="space-y-4 rounded-3xl border border-white/5 bg-slate-950/80 p-6">
            <div class="space-y-4">
                <label class="block space-y-2 text-sm font-medium text-slate-200">
                    <span>Config name</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        bind:value={selectedName}
                        placeholder="production-gates"
                    />
                </label>
                <label class="block space-y-2 text-sm font-medium text-slate-200">
                    <span>Kind</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        bind:value={configKind}
                        placeholder="tfreview"
                    />
                </label>
                <label class="block space-y-2 text-sm font-medium text-slate-200">
                    <span>YAML payload</span>
                    <textarea
                        class="h-64 w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        bind:value={editorPayload}
                        spellcheck={false}
                    ></textarea>
                </label>
            </div>

            <div class="flex flex-wrap gap-3">
                <button
                    class="rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-sky-900/40 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:cursor-not-allowed disabled:opacity-60"
                    type="button"
                    onclick={handleSave}
                    disabled={isSaving}
                >
                    {#if isSaving}
                        <span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                        Saving…
                    {:else}
                        Save config
                    {/if}
                </button>
                <input
                    class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-xs text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                    type="text"
                    placeholder="Report ID for preview (optional)"
                    bind:value={reportId}
                />
                <button
                    class="rounded-2xl border border-white/10 px-5 py-2 text-sm font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                    type="button"
                    onclick={handlePreview}
                    disabled={isPreviewing}
                >
                    {#if isPreviewing}
                        <span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                        Previewing…
                    {:else}
                        Preview config
                    {/if}
                </button>
            </div>

            {#if saveStatus}
                <div class="rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-2 text-xs text-slate-200">{saveStatus}</div>
            {/if}
            {#if previewStatus}
                <div class="rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-2 text-xs text-slate-200">{previewStatus}</div>
            {/if}

            {#if previewResult}
                <details class="rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-xs text-slate-200" open>
                    <summary class="cursor-pointer text-slate-100">Preview summary (after config application)</summary>
                    <pre class="mt-3 max-h-64 overflow-auto rounded-xl bg-slate-950/70 p-3">{JSON.stringify(previewResult.after, null, 2)}</pre>
                </details>
                <details class="rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-3 text-xs text-slate-200">
                    <summary class="cursor-pointer text-slate-100">Original summary (before config)</summary>
                    <pre class="mt-3 max-h-64 overflow-auto rounded-xl bg-slate-950/70 p-3">{JSON.stringify(previewResult.before, null, 2)}</pre>
                </details>
            {/if}
        </aside>
    </div>
</section>
