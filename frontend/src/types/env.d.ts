declare module '$env/dynamic/public' {
	export const env: Record<string, string | undefined>;
}

declare module '$env/static/public' {
	export const PUBLIC_API_BASE: string;
}
