<script lang="ts">
import ProjectReviewPanel from '$lib/components/projects/ProjectReviewPanel.svelte';
import type { ProjectSummary } from '$lib/api/client';
import type { PageData, PageProps } from './$types';

const { data, params } = $props<{ data: PageData; params: PageProps['params'] }>();
const token = data.token as string | null;
const project = data.project as ProjectSummary | null;
const projectId = (data.projectId as string | null) ?? project?.id ?? null;
const projectSlug = (data.projectSlug as string | null) ?? params.projectSlug ?? project?.slug ?? null;
</script>

<ProjectReviewPanel {token} {projectId} {projectSlug} />
