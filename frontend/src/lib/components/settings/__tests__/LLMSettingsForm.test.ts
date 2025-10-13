import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import LLMSettingsForm from '../LLMSettingsForm.svelte';

const providerOptions = [
    { label: 'Off', value: 'off' },
    { label: 'OpenAI', value: 'openai' },
    { label: 'Azure OpenAI', value: 'azure' }
];

describe('LLMSettingsForm', () => {
    it('renders provider options and status messages', () => {
        const { getByText, getByDisplayValue } = render(LLMSettingsForm, {
            props: {
                providers: providerOptions,
                provider: 'openai',
                model: 'gpt-4.1-mini',
                enableExplanations: true,
                enablePatches: false,
                apiBase: 'https://api.openai.com/v1',
                apiVersion: '',
                deploymentName: '',
                saveStatus: 'Saved!',
                testStatus: { ok: true, stage: 'ping', message: 'OK' },
                tokenPresent: true,
                isSaving: false,
                isTesting: false
            }
        });

        expect(getByDisplayValue('gpt-4.1-mini')).toBeInTheDocument();
        expect(getByText('Saved!')).toBeInTheDocument();
        expect(getByText((_, el) => el?.textContent === 'Stage ping: OK')).toBeInTheDocument();
    });

    it('emits save and test events', async () => {
        const saveHandler = vi.fn();
        const testHandler = vi.fn();
        const { getByText } = render(LLMSettingsForm, {
            props: {
                providers: providerOptions,
                provider: 'off',
                model: '',
                enableExplanations: false,
                enablePatches: false,
                apiBase: '',
                apiVersion: '',
                deploymentName: '',
                saveStatus: null,
                testStatus: null,
                tokenPresent: true,
                isSaving: false,
                isTesting: false
            },
            events: { save: saveHandler, test: testHandler }
        });

        await fireEvent.click(getByText('Save settings'));
        expect(saveHandler).toHaveBeenCalledTimes(1);

        await fireEvent.click(getByText('Live ping'));
        expect(testHandler).toHaveBeenCalledWith(expect.objectContaining({ detail: { live: true } }));
    });

    it('disables actions when busy', async () => {
        const { getByText, rerender } = render(LLMSettingsForm, {
            props: {
                providers: providerOptions,
                provider: 'off',
                model: '',
                enableExplanations: false,
                enablePatches: false,
                apiBase: '',
                apiVersion: '',
                deploymentName: '',
                saveStatus: null,
                testStatus: null,
                tokenPresent: true,
                isSaving: true,
                isTesting: false
            }
        });

        expect(getByText('Saving…')).toBeDisabled();

        await rerender({
            providers: providerOptions,
            provider: 'off',
            model: '',
            enableExplanations: false,
            enablePatches: false,
            apiBase: '',
            apiVersion: '',
            deploymentName: '',
            saveStatus: null,
            testStatus: null,
            tokenPresent: true,
            isSaving: false,
            isTesting: true
        });

        expect(getByText('Validate configuration')).toBeDisabled();
        expect(getByText('Live ping')).toBeDisabled();
    });
});
