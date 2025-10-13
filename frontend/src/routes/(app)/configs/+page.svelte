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
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Review configs</p>
        <h2 class="text-3xl font-semibold text-slate-700">Tune thresholds & waivers</h2>
        <p class="max-w-2xl text-sm text-slate-500">
            Manage stored `tfreview.yaml` profiles used to control severity gates and waivers. Save changes to persist in the
            SQLite store, then preview against existing reports using the reviewer backend.
        </p>
    </header>

    {#if loadError}
        <div class="rounded-2xl border border-rose-300 bg-rose-50 px-4 py-2 text-xs text-rose-700">{loadError}</div>
    {/if}

    <div class="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <section class="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-300/40">
            <header class="flex items-center justify-between">
                <h3 class="text-lg font-semibold text-slate-700">Saved configs</h3>
                <button class="rounded-xl border border-sky-200 bg-white px-3 py-2 text-xs font-semibold text-sky-600 transition hover:bg-sky-500 hover:text-white" type="button" onclick={startNewConfig}>
                    New config
                </button>
            </header>
            <ul class="space-y-3 text-sm text-slate-500">
                {#if configs.length === 0}
                    <li class="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
                        No configs saved yet. Create one using the editor on the right.
                    </li>
                {:else}
                    {#each configs as cfg (cfg.name)}
                        <li class={`flex items-start justify-between gap-3 rounded-2xl border px-4 py-3 transition ${cfg.name === selectedName ? 'border-sky-400 bg-white shadow-sm shadow-sky-200/70' : 'border-slate-200 bg-slate-50 hover:border-sky-300'}`}>
                            <div class="space-y-1">
                                <button class="text-left text-sm font-semibold text-slate-700" type="button" onclick={() => setActiveConfig(cfg.name)}>
                                    {cfg.name}
                                </button>
                                <p class="text-xs text-slate-500">{cfg.payload.split('\n', 1)[0] || 'Config payload'}</p>
                            </div>
                            <button
                                class="rounded-xl border border-rose-200 px-3 py-1 text-xs font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
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

        <aside class="space-y-4 rounded-3xl border border-slate-200 bg-white p-6">
            <div class="space-y-4">
                <label class="block space-y-2 text-sm font-medium text-slate-600">
                    <span>Config name</span>
                    <input
                        class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                        type="text"
                        bind:value={selectedName}
                        placeholder="production-gates"
                    />
                </label>
                <label class="block space-y-2 text-sm font-medium text-slate-600">
                    <span>Kind</span>
                    <input
                        class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                        type="text"
                        bind:value={configKind}
                        placeholder="tfreview"
                    />
                </label>
                <label class="block space-y-2 text-sm font-medium text-slate-600">
                    <span>YAML payload</span>
                    <textarea
                        class="h-64 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                        bind:value={editorPayload}
                        spellcheck={false}
                    ></textarea>
                </label>
            </div>

            <div class="flex flex-wrap gap-3">
                <button
                    class="rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-sky-300/50 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-200 disabled:cursor-not-allowed disabled:opacity-60"
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
                    class="w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-xs text-slate-600 shadow-inner shadow-slate-200 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
                    type="text"
                    placeholder="Report ID for preview (optional)"
                    bind:value={reportId}
                />
                <button
                    class="rounded-2xl border border-slate-200 px-5 py-2 text-sm font-semibold text-slate-600 transition hover:bg-sky-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
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
                <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-600">{saveStatus}</div>
            {/if}
            {#if previewStatus}
                <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs text-slate-600">{previewStatus}</div>
            {/if}

            {#if previewResult}
                <details class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600" open>
                    <summary class="cursor-pointer text-slate-700">Preview summary (after config application)</summary>
                    <pre class="mt-3 max-h-64 overflow-auto rounded-xl bg-slate-50 p-3">{JSON.stringify(previewResult.after, null, 2)}</pre>
                </details>
                <details class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
                    <summary class="cursor-pointer text-slate-700">Original summary (before config)</summary>
                    <pre class="mt-3 max-h-64 overflow-auto rounded-xl bg-slate-50 p-3">{JSON.stringify(previewResult.before, null, 2)}</pre>
                </details>
            {/if}
        </aside>
    </div>
</section>
