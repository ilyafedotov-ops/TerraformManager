import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import ArtifactPreviewPane from '../ArtifactPreviewPane.svelte';

describe('ArtifactPreviewPane', () => {
	it('shows placeholder when no content is provided', () => {
		const { getByText } = render(ArtifactPreviewPane, { props: { label: 'Preview' } });
		expect(getByText('No preview available. Select a file to load its contents.')).toBeInTheDocument();
	});

	it('renders provided content', () => {
		const { getByText } = render(ArtifactPreviewPane, {
			props: { content: 'variable "example" {}' }
		});
		expect(getByText('variable "example" {}')).toBeInTheDocument();
	});

	it('shows error messages', () => {
		const { getByText } = render(ArtifactPreviewPane, {
			props: { error: 'Preview failed.' }
		});
		expect(getByText('Preview failed.')).toBeInTheDocument();
	});
});
