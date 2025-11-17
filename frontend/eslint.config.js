import js from "@eslint/js";
import tseslint from "typescript-eslint";
import svelte from "eslint-plugin-svelte";
import svelteParser from "svelte-eslint-parser";
import globals from "globals";

const sharedRules = {
	"no-console": ["warn", { allow: ["warn", "error"] }],
	"no-self-assign": "warn",
	"@typescript-eslint/no-unused-vars": [
		"warn",
		{
			varsIgnorePattern: "^_",
			argsIgnorePattern: "^_",
			caughtErrorsIgnorePattern: "^_"
		}
	],
	"@typescript-eslint/no-explicit-any": "warn"
};

export default [
	{
		ignores: [
			"build",
			".svelte-kit",
			"dist",
			"node_modules",
			"eslint.config.js",
			"postcss.config.js",
			"svelte.config.js",
			"tailwind.config.cjs",
			"vite.config.js"
		]
	},
	...svelte.configs["flat/base"],
	js.configs.recommended,
	...tseslint.configs.recommended,
	{
		files: ["**/*.{ts,js}"],
		languageOptions: {
			parserOptions: {
				ecmaVersion: "latest",
				sourceType: "module"
			},
			globals: {
				...globals.browser,
				...globals.node
			}
		},
		rules: sharedRules
	},
	{
		files: ["**/*.svelte"],
		languageOptions: {
			parser: svelteParser,
			parserOptions: {
				extraFileExtensions: [".svelte"],
				parser: tseslint.parser
			},
			globals: {
				...globals.browser
			}
		},
		rules: sharedRules
	}
];
