<script lang="ts">
    import { saveLLMSettings, testLLMSettings, type LLMSettingsResponse } from '$lib/api/client';
    import LLMSettingsForm, { type LLMTestStatus } from '$lib/components/settings/LLMSettingsForm.svelte';

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
    let testStatus = $state<LLMTestStatus>(null);

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

</script>

<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-blueGray-400">Settings</p>
        <h2 class="text-3xl font-semibold text-blueGray-700">LLM assistance</h2>
        <p class="max-w-2xl text-sm text-blueGray-500">
            Configure optional AI explanations and patch suggestions. The backend stores these preferences in SQLite via
            `/settings/llm` and validates credentials with `/settings/llm/test`.
        </p>
    </header>

    <LLMSettingsForm
        providers={providers}
        bind:provider
        bind:model
        bind:enableExplanations
        bind:enablePatches
        bind:apiBase
        bind:apiVersion
        bind:deploymentName
        saveStatus={saveStatus}
        testStatus={testStatus}
        loadError={loadError}
        tokenPresent={Boolean(token)}
        isSaving={saveBusy}
        isTesting={testing}
        on:change={resetFeedback}
        on:save={handleSave}
        on:test={(event: CustomEvent<{ live: boolean }>) => handleTest(event.detail.live)}
    />
</section>
