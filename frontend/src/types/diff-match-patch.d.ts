declare module 'diff-match-patch' {
	export type Diff = [number, string];

	export default class DiffMatchPatch {
		diff_main(text1: string, text2: string, cursorPos?: number): Diff[];
		diff_cleanupSemantic(diffs: Diff[]): void;
		diff_cleanupEfficiency(diffs: Diff[]): void;
	}
}
