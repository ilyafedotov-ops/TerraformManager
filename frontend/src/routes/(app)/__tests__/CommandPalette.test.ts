import { fireEvent, render, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import CommandPaletteHarness from './CommandPaletteHarness.svelte';
import { navigationSectionsStore, navigationState } from '$lib/stores/navigation';
import { projectState } from '$lib/stores/project';
import type { ProjectSummary } from '$lib/api/client';

const sections = [
	{
		title: 'Workbench',
		items: [
			{
				title: 'Dashboard',
				icon: 'grid',
		projectScoped: true,
		projectPath: '/projects/{projectSlug}/dashboard'
	},
			{
				title: 'Reports',
				icon: 'file',
		projectScoped: true,
		projectPath: '/projects/{projectSlug}/reports'
			},
			{ title: 'Knowledge', href: '/knowledge', icon: 'book' }
		]
	}
];

const demoProject: ProjectSummary = {
	id: 'proj-demo',
	name: 'Demo project',
	slug: 'demo-project',
	root_path: '.'
};

afterEach(() => {
	navigationState.reset();
	navigationSectionsStore.set(sections);
	projectState.reset();
});

describe('Command palette interactions', () => {
	it('opens with ctrl+k and focuses the search input', async () => {
		const { getByPlaceholderText, queryByTestId } = render(CommandPaletteHarness, {
			props: { sections }
		});

		expect(queryByTestId('command-palette')).toBeNull();

		await fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

		const input = await waitFor(() => getByPlaceholderText('Jump to a page…'));
		expect(queryByTestId('command-palette')).not.toBeNull();
		expect(document.activeElement).toBe(input);
	});

	it('filters results as the query changes', async () => {
		const { getByPlaceholderText, getByTestId, queryByText } = render(CommandPaletteHarness, {
			props: { sections, project: demoProject }
		});

		await fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

		const input = await waitFor(() => getByPlaceholderText('Jump to a page…'));
		expect(getByTestId('command-results')).toBeInTheDocument();

		await fireEvent.input(input, { target: { value: 'report' } });

		await waitFor(() => {
			expect(queryByText('Reports')).toBeInTheDocument();
			expect(queryByText('Dashboard')).not.toBeInTheDocument();
		});
	});

	it('selects the first result with Enter and closes the palette', async () => {
		const selectHandler = vi.fn();
		const { getByPlaceholderText, queryByTestId } = render(CommandPaletteHarness, {
			props: { sections, project: demoProject },
			events: { select: (event: CustomEvent<{ href: string }>) => selectHandler(event.detail.href) }
		});

		await fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

		const input = await waitFor(() => getByPlaceholderText('Jump to a page…'));
		await fireEvent.input(input, { target: { value: 'know' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		await waitFor(() => expect(selectHandler).toHaveBeenCalledWith('/knowledge'));
		await waitFor(() => expect(queryByTestId('command-palette')).toBeNull());
	});

	it('traps focus while the palette is open', async () => {
		const { getByPlaceholderText, getByRole, getAllByRole } = render(CommandPaletteHarness, {
			props: { sections, project: demoProject }
		});

		await fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

		const input = await waitFor(() => getByPlaceholderText('Jump to a page…'));
		const closeButton = getByRole('button', { name: 'Close' });
		const optionButtons = getAllByRole('button').filter((button) => button !== closeButton);
		const lastOption = optionButtons[optionButtons.length - 1];

		lastOption.focus();
		await fireEvent.keyDown(lastOption, { key: 'Tab' });
		expect(document.activeElement).toBe(closeButton);

		closeButton.focus();
		await fireEvent.keyDown(closeButton, { key: 'Tab', shiftKey: true });
		expect(document.activeElement).toBe(lastOption);

		input.focus();
	});

	it('restores focus to the previously active element on close', async () => {
		const toggle = document.createElement('button');
		toggle.type = 'button';
		toggle.textContent = 'Toggle palette';
		document.body.appendChild(toggle);

		try {
			toggle.focus();

			const { getByPlaceholderText, getByRole } = render(CommandPaletteHarness, {
				props: { sections, project: demoProject }
			});

			await fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

			await waitFor(() => getByPlaceholderText('Jump to a page…'));
			await fireEvent.click(getByRole('button', { name: 'Close' }));

			await waitFor(() => expect(document.activeElement).toBe(toggle));
		} finally {
			toggle.remove();
		}
	});
	it('falls back to /projects for project-scoped routes when no project is selected', async () => {
		const selectHandler = vi.fn();
		const { getByPlaceholderText } = render(CommandPaletteHarness, {
			props: { sections },
			events: { select: (event: CustomEvent<{ href: string }>) => selectHandler(event.detail.href) }
		});

		await fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

		const input = await waitFor(() => getByPlaceholderText('Jump to a page…'));
		await fireEvent.input(input, { target: { value: 'dash' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		await waitFor(() => expect(selectHandler).toHaveBeenCalledWith('/projects'));
	});

	it('injects the active project into project-scoped hrefs', async () => {
		const selectHandler = vi.fn();
		const { getByPlaceholderText } = render(CommandPaletteHarness, {
			props: { sections, project: demoProject },
			events: { select: (event: CustomEvent<{ href: string }>) => selectHandler(event.detail.href) }
		});

		await fireEvent.keyDown(window, { key: 'k', ctrlKey: true });

		const input = await waitFor(() => getByPlaceholderText('Jump to a page…'));
		await fireEvent.input(input, { target: { value: 'report' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

	await waitFor(() =>
		expect(selectHandler).toHaveBeenCalledWith(`/projects/${demoProject.slug}/reports`)
	);
	});
});
