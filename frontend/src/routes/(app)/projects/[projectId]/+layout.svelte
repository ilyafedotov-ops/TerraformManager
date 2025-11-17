<script lang="ts">
import { projectState } from '$lib/stores/project';

const { children, data } = $props();

const project = data.project as { id: string } | null;

$effect(() => {
	if (project) {
		projectState.upsertProject(project);
		projectState.setActiveProject(project.id);
	}
});
</script>

{@render children?.()}
