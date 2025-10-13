import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as notifications from '$lib/stores/notifications';
import ReportActions from '../ReportActions.svelte';

const apiBase = 'https://api.terraform-manager.dev';
const reportId = 'rpt-12345';

const setClipboard = (impl: (text: string) => Promise<void>) => {
	Object.defineProperty(navigator, 'clipboard', {
		value: { writeText: impl },
		configurable: true
	});
};

const clearClipboard = () => {
	Reflect.deleteProperty(navigator as unknown as Record<string, unknown>, 'clipboard');
};

describe('ReportActions', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
		clearClipboard();
		vi.spyOn(console, 'warn').mockImplementation(() => {});
	});

	afterEach(() => {
		clearClipboard();
	});

	it('renders action links with expected destinations', () => {
		const { getByText } = render(ReportActions, {
			props: { id: reportId, apiBase }
		});

		expect(getByText('View')).toHaveAttribute('href', `/reports/${reportId}`);
		expect(getByText('JSON')).toHaveAttribute('href', `${apiBase}/reports/${reportId}`);
		expect(getByText('CSV')).toHaveAttribute('href', `${apiBase}/reports/${reportId}/csv`);
		expect(getByText('HTML')).toHaveAttribute('href', `${apiBase}/reports/${reportId}/html`);
	});

	it('emits a delete event when delete is clicked', async () => {
		const handler = vi.fn();
		const { getByText } = render(ReportActions, {
			props: { id: reportId, apiBase },
			events: { delete: handler }
		});

		await fireEvent.click(getByText('Delete'));

		expect(handler).toHaveBeenCalledTimes(1);
	});

	it('copies the JSON link to the clipboard and shows a success toast', async () => {
		const writeText = vi.fn().mockResolvedValue(undefined);
		setClipboard(writeText);
		const successSpy = vi.spyOn(notifications, 'notifySuccess');
		const errorSpy = vi.spyOn(notifications, 'notifyError');

		const { getByText } = render(ReportActions, {
			props: { id: reportId, apiBase }
		});

		await fireEvent.click(getByText('Copy JSON link'));

		await waitFor(() => expect(writeText).toHaveBeenCalledWith(`${apiBase}/reports/${reportId}`));
		await waitFor(() =>
			expect(successSpy).toHaveBeenCalledWith('Report JSON link copied to clipboard.', { duration: 2500 })
		);
		expect(errorSpy).not.toHaveBeenCalled();
	});

	it('surfaces an error toast when clipboard access fails', async () => {
		const writeText = vi.fn().mockRejectedValue(new Error('permission denied'));
		setClipboard(writeText);
		const errorSpy = vi.spyOn(notifications, 'notifyError');
		const successSpy = vi.spyOn(notifications, 'notifySuccess');

		const { getByText } = render(ReportActions, {
			props: { id: reportId, apiBase }
		});

		await fireEvent.click(getByText('Copy JSON link'));

		await waitFor(() => expect(errorSpy).toHaveBeenCalledWith('Unable to copy JSON link.'));
		expect(successSpy).not.toHaveBeenCalled();
	});
});
