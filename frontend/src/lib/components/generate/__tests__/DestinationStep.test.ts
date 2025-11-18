import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import DestinationHost from './DestinationHost.svelte';
import DestinationStep from '../DestinationStep.svelte';

const baseProjects = [
    { id: 'project-1', name: 'Primary', slug: 'primary', root_path: '/tmp' },
    { id: 'project-2', name: 'Secondary', slug: 'secondary', root_path: '/tmp' },
] as any;

describe('DestinationStep', () => {
    it('emits events for project selection, auto-save, and metadata updates', async () => {
        const received: Record<string, unknown>[] = [];
        const result = render(DestinationHost, {
            props: {
                props: {
                    projects: baseProjects,
                    activeProjectId: 'project-1',
                    autoSaveEnabled: true,
                    assetName: 'Baseline',
                    assetDescription: 'Demo',
                    assetTags: 'prod,baseline',
                    hasContext: true,
                    error: null,
                    saving: false,
                },
                onEvent: (payload: { type: string; detail?: Record<string, unknown> }) => received.push(payload),
            },
        });

        const projectSelect = result.getByDisplayValue('Primary') as HTMLSelectElement;
        await fireEvent.change(projectSelect, { target: { value: 'project-2' } });

        const toggleButton = result.getByText('Enabled — runs are saved with validation summaries.');
        await fireEvent.click(toggleButton);

        const nameInput = result.getByDisplayValue('Baseline');
        await fireEvent.input(nameInput, { target: { value: 'New Baseline' } });

        const descriptionInput = result.getByDisplayValue('Demo');
        await fireEvent.input(descriptionInput, { target: { value: 'Updated description' } });

        const tagsInput = result.getByDisplayValue('prod,baseline');
        await fireEvent.input(tagsInput, { target: { value: 'prod,weekly' } });

        await fireEvent.click(result.getByText('Save destination updates'));
        await fireEvent.click(result.getByText('Continue to review'));
        await fireEvent.click(result.getByText('Back to inputs'));

        expect(received).toEqual([
            { type: 'projectChange', detail: { id: 'project-2' } },
            { type: 'toggleAutoSave', detail: { enabled: false } },
            { type: 'assetNameChange', detail: { value: 'New Baseline' } },
            { type: 'assetDescriptionChange', detail: { value: 'Updated description' } },
            { type: 'assetTagsChange', detail: { value: 'prod,weekly' } },
            { type: 'save', detail: {} },
            { type: 'goToReview', detail: {} },
            { type: 'goToConfigure', detail: {} },
        ]);
    });

    it('shows helper when auto-save is disabled or context missing', () => {
        const { getByText } = render(DestinationStep, {
            props: {
                projects: baseProjects,
                activeProjectId: 'project-1',
                autoSaveEnabled: false,
                assetName: '',
                assetDescription: '',
                assetTags: '',
                hasContext: false,
                error: null,
                saving: false,
            },
        });

        expect(
            getByText((content) =>
                content.includes('Auto-save is disabled. The generator will render Terraform for download/copy without creating project runs')
            )
        ).toBeInTheDocument();
        expect(getByText('Continue to review')).toBeInTheDocument();
        expect(getByText('Back to inputs')).toBeInTheDocument();
    });
});
