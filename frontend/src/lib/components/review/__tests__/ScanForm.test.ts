import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import ScanForm from '../ScanForm.svelte';

const steps = [
    { title: 'Upload', status: 'current' as const },
    { title: 'Review', status: 'upcoming' as const },
    { title: 'Export', status: 'upcoming' as const }
];

describe('ScanForm', () => {
    it('emits submit with current state', async () => {
        const submit = vi.fn();
        const { getByLabelText, getByText, component } = render(ScanForm, {
            props: { steps, files: null, terraformValidate: false, saveReport: true, isSubmitting: false, error: null },
            events: { submit }
        });

        const fileInput = getByLabelText('Terraform files or zip archives') as HTMLInputElement;
        const mockFile = new File(['data'], 'main.tf', { type: 'text/plain' });
        await fireEvent.change(fileInput, { target: { files: [mockFile] } });

        await fireEvent.click(getByText('Run scan'));

		expect(submit).toHaveBeenCalledWith(
			expect.objectContaining({
				detail: expect.objectContaining({
					terraformValidate: false,
					saveReport: true,
					includeCost: false,
					usageFile: null,
					planFile: null
				})
			})
		);
    });

    it('shows error message when provided', () => {
        const { getByText } = render(ScanForm, {
            props: { steps, files: null, terraformValidate: false, saveReport: true, isSubmitting: false, error: 'Missing token' }
        });

        expect(getByText('Missing token')).toBeInTheDocument();
    });
});
