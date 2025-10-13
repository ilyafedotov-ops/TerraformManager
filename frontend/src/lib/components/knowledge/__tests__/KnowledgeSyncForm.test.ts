import { fireEvent, render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import KnowledgeSyncForm from '../KnowledgeSyncForm.svelte';
import type { KnowledgeSyncResult } from '$lib/api/client';

const buildSyncResult = (overrides: Partial<KnowledgeSyncResult> = {}): KnowledgeSyncResult => ({
	source: 'https://github.com/example/repo',
	dest_dir: 'knowledge/external/repo',
	files: ['README.md'],
	...overrides
});

describe('KnowledgeSyncForm', () => {
	it('renders status and results', () => {
		const results = [
			buildSyncResult({ source: 'https://github.com/a', files: ['doc.md', 'guide.md'] }),
			buildSyncResult({ source: 'https://github.com/b', files: ['readme.md'] })
		];

		const { getByText } = render(KnowledgeSyncForm, {
			props: {
				sources: 'https://github.com/a',
				isSyncing: false,
				status: 'Knowledge sync completed.',
				results,
				tokenPresent: true
			}
		});

		expect(getByText('Knowledge sync completed.')).toBeInTheDocument();
		expect(getByText('https://github.com/a')).toBeInTheDocument();
		expect(getByText('https://github.com/b')).toBeInTheDocument();
		expect(getByText('2 files')).toBeInTheDocument();
	});

	it('disables the button while syncing or without token', async () => {
		const { getByText, rerender } = render(KnowledgeSyncForm, {
			props: {
				sources: '',
				isSyncing: true,
				status: null,
				results: [],
				tokenPresent: true
			}
		});

		expect(getByText('Syncing…')).toBeDisabled();

		await rerender({ sources: '', isSyncing: false, status: null, results: [], tokenPresent: false });
		expect(getByText('Run sync')).toBeDisabled();
	});

	it('emits sync event when button is clicked', async () => {
		const handler = vi.fn();
		const { getByText } = render(KnowledgeSyncForm, {
			props: { sources: '', isSyncing: false, status: null, results: [], tokenPresent: true },
			events: { sync: handler }
		});

		await fireEvent.click(getByText('Run sync'));
		expect(handler).toHaveBeenCalledTimes(1);
	});
});
