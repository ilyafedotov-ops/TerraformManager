<script lang="ts">
    import {
        saveLLMSettings,
        testLLMSettings,
        type LLMSettingsResponse
    } from '$lib/api/client';

    const { data } = $props();
    const token = data.token as string | null;
    const initial = data.settings as LLMSettingsResponse | null;
    const loadError = data.error as string | undefined;

    const providers = [
        { label: 'Off', value: 'off' },
        { label: 'OpenAI', value: 'openai' },
        { label: 'Azure OpenAI', value: 'azure' }
    ];

    let provider = $state(initial?.provider ?? 'off');
    let model = $state(initial?.model ?? '');
    let enableExplanations = $state(Boolean(initial?.enable_explanations));
    let enablePatches = $state(Boolean(initial?.enable_patches));
    let apiBase = $state(initial?.api_base ?? '');
    let apiVersion = $state(initial?.api_version ?? '');
    let deploymentName = $state(initial?.deployment_name ?? '');

    let saveStatus = $state<string | null>(null);
    let saveBusy = $state(false);
    let testing = $state(false);
    let testStatus = $state<{ ok: boolean; stage: string; message: string } | null>(null);

    const resetFeedback = () => {
        saveStatus = null;
        testStatus = null;
    };

    const handleSave = async () => {
        resetFeedback();
        if (!token) {
            saveStatus = 'Provide an API token before saving settings.';
            return;
        }
        saveBusy = true;
        try {
            await saveLLMSettings(fetch, token, {
                provider,
                model,
                enable_explanations: enableExplanations,
                enable_patches: enablePatches,
                api_base: apiBase || null,
                api_version: apiVersion || null,
                deployment_name: deploymentName || null
            });
            saveStatus = 'Settings saved successfully.';
        } catch (error) {
            saveStatus = error instanceof Error ? error.message : 'Failed to save settings.';
        } finally {
            saveBusy = false;
        }
    };

    const handleTest = async (live: boolean) => {
        resetFeedback();
        if (!token) {
            testStatus = { ok: false, stage: 'client', message: 'Provide an API token before testing settings.' };
            return;
        }
        testing = true;
        try {
            const result = await testLLMSettings(fetch, token, live);
            testStatus = {
                ok: result.ok,
                stage: result.stage,
                message: result.ok
                    ? live
                        ? 'Live ping succeeded.'
                        : 'Settings validated successfully.'
                    : result.error || 'LLM validation failed.'
            };
        } catch (error) {
            testStatus = {
                ok: false,
                stage: 'client',
                message: error instanceof Error ? error.message : 'Unexpected error while testing settings.'
            };
        } finally {
            testing = false;
        }
    };

    const isAzure = () => provider === 'azure';
    const isOpenAI = () => provider === 'openai';
</script>

<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-500">Settings</p>
        <h2 class="text-3xl font-semibold text-white">LLM assistance</h2>
        <p class="max-w-2xl text-sm text-slate-400">
            Configure optional AI explanations and patch suggestions. The backend stores these preferences in SQLite via
            `/settings/llm` and validates credentials with `/settings/llm/test`.
        </p>
    </header>

    <form class="space-y-6 rounded-3xl border border-white/5 bg-slate-950/80 p-6 shadow-xl shadow-slate-950/40" oninput={resetFeedback}>
        {#if loadError}
            <div class="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-xs text-rose-100">{loadError}</div>
        {/if}
        {#if !token}
            <div class="rounded-2xl border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-xs text-amber-100">
                No API token detected. Save/test actions require authenticated API access.
            </div>
        {/if}

        <label class="block space-y-2 text-sm font-medium text-slate-200">
            <span>Provider</span>
            <select
                class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                bind:value={provider}
            >
                {#each providers as option}
                    <option value={option.value}>{option.label}</option>
                {/each}
            </select>
        </label>

        <label class="block space-y-2 text-sm font-medium text-slate-200">
            <span>Model / deployment</span>
            <input
                class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:cursor-not-allowed disabled:border-slate-800 disabled:bg-slate-900/40 disabled:text-slate-600"
                type="text"
                bind:value={model}
                placeholder={provider === 'azure' ? 'azure-deployment-name' : 'gpt-4.1-mini'}
                disabled={provider === 'off'}
            />
        </label>

        <div class="grid gap-4 md:grid-cols-2">
            <label class="flex items-center gap-3 rounded-2xl border border-white/5 bg-slate-900/70 px-4 py-3 text-sm text-slate-200">
                <input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={enableExplanations} />
                <span class="flex-1">
                    <span class="font-semibold text-white">Enable AI explanations</span>
                    <p class="text-xs text-slate-400">Show LLM-authored rationale next to reviewer findings.</p>
                </span>
            </label>
            <label class="flex items-center gap-3 rounded-2xl border border-white/5 bg-slate-900/70 px-4 py-3 text-sm text-slate-200">
                <input class="h-4 w-4 rounded border-slate-700 text-sky-400 focus:ring-sky-400/50" type="checkbox" bind:checked={enablePatches} />
                <span class="flex-1">
                    <span class="font-semibold text-white">Enable AI patch suggestions</span>
                    <p class="text-xs text-slate-400">Experimental diff guidance that supplements deterministic rules.</p>
                </span>
            </label>
        </div>

        {#if isOpenAI()}
            <label class="block space-y-2 text-sm font-medium text-slate-200">
                <span>OpenAI API base (optional)</span>
                <input
                    class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                    type="text"
                    placeholder="https://api.openai.com/v1"
                    bind:value={apiBase}
                />
            </label>
        {/if}

        {#if isAzure()}
            <div class="grid gap-4 md:grid-cols-3">
                <label class="space-y-2 text-sm font-medium text-slate-200">
                    <span>Azure resource URL</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        placeholder="https://&#123;resource&#125;.openai.azure.com"
                        bind:value={apiBase}
                    />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-200">
                    <span>API version</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        placeholder="2024-02-15"
                        bind:value={apiVersion}
                    />
                </label>
                <label class="space-y-2 text-sm font-medium text-slate-200">
                    <span>Deployment name</span>
                    <input
                        class="w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-white shadow-inner shadow-slate-950/60 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                        type="text"
                        placeholder="gpt-4o-mini"
                        bind:value={deploymentName}
                    />
                </label>
            </div>
        {/if}

        <div class="flex flex-wrap gap-3">
            <button
                class="rounded-2xl bg-gradient-to-r from-sky-500 via-indigo-500 to-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-sky-900/40 transition hover:from-sky-400 hover:via-indigo-400 hover:to-blue-500 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onclick={handleSave}
                disabled={saveBusy}
            >
                {#if saveBusy}
                    <span class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                    Saving…
                {:else}
                    Save settings
                {/if}
            </button>
            <button
                class="rounded-2xl border border-white/10 px-5 py-2 text-sm font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onclick={() => handleTest(false)}
                disabled={testing}
            >
                Validate configuration
            </button>
            <button
                class="rounded-2xl border border-white/10 px-5 py-2 text-sm font-semibold text-slate-200 transition hover:border-sky-400/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onclick={() => handleTest(true)}
                disabled={testing}
            >
                Live ping
            </button>
        </div>

        {#if saveStatus}
            <div class="rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-2 text-xs text-slate-200">{saveStatus}</div>
        {/if}
        {#if testStatus}
            <div class="rounded-2xl border border-white/10 bg-slate-900/60 px-4 py-2 text-xs text-slate-200">
                Stage <strong>{testStatus.stage}</strong>: {testStatus.message}
            </div>
        {/if}

        <div class="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4 text-xs text-sky-100">
            <p class="font-semibold uppercase tracking-[0.3em] text-sky-300">Operational tips</p>
            <p class="mt-2">
                Ensure the backend environment exposes the required API keys (OpenAI) or Azure credentials before enabling AI
                assistance. Deterministic findings remain unaffected when the provider is set to <em>Off</em>.
            </p>
        </div>
    </form>
</section>
