import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { svelteTesting } from '@testing-library/svelte/vite';

export default defineConfig({
	plugins: [sveltekit(), svelteTesting()],
	test: {
		globals: true,
		environment: 'jsdom',
		setupFiles: ['src/setupTests.ts'],
		include: ['src/**/*.{test,spec}.{js,ts}'],
		css: true
	}
});
