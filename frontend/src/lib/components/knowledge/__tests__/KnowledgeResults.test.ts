import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import KnowledgeResults from '../KnowledgeResults.svelte';
import type { KnowledgeItem } from '$lib/api/client';

const buildItem = (overrides: Partial<KnowledgeItem> = {}): KnowledgeItem => ({
    source: 'docs/example.md',
    content: 'Example content',
    score: 0.9,
    ...overrides
});

describe('KnowledgeResults', () => {
    it('renders result entries', () => {
        const items = [
            buildItem({ source: 'docs/a.md', content: 'First snippet', score: 0.8 }),
            buildItem({ source: 'docs/b.md', content: 'Second snippet', score: 0.7 })
        ];

        const { getByText, getAllByText } = render(KnowledgeResults, {
            props: { items, error: null }
        });

        expect(getByText('docs/a.md')).toBeInTheDocument();
        expect(getByText('First snippet')).toBeInTheDocument();
        expect(getAllByText(/Open markdown/)).toHaveLength(2);
    });

    it('shows empty guidance when there are no items', () => {
        const { getByText } = render(KnowledgeResults, {
            props: { items: [], error: null }
        });

        expect(
            getByText(/No documents matched. Broaden the query or add new Markdown files under/)
        ).toBeInTheDocument();
    });

    it('renders errors when provided', () => {
        const { getByText } = render(KnowledgeResults, {
            props: { items: [], error: 'Search failed' }
        });

        expect(getByText('Search failed')).toBeInTheDocument();
    });
});
