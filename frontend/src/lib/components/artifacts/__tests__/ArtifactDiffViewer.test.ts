import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import ArtifactDiffViewer from '../ArtifactDiffViewer.svelte';

describe('ArtifactDiffViewer', () => {
	it('prompts to preview when current content missing', () => {
		const { getByText } = render(ArtifactDiffViewer, {
			props: { currentContent: null, previousContent: null }
		});
		expect(getByText('Preview the artifact to generate a diff.')).toBeInTheDocument();
	});

	it('renders diff content when both versions exist', () => {
		const { container } = render(ArtifactDiffViewer, {
			props: { currentContent: 'resource', previousContent: 'res' }
		});
		expect(container.querySelector('pre')).not.toBeNull();
	});
});
