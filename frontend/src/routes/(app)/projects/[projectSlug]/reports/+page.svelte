<script lang="ts">
import ProjectReportsPanel from '$lib/components/projects/ProjectReportsPanel.svelte';
import type { ProjectSummary, ReportListResponse } from '$lib/api/client';
import type { PageData, PageProps } from './$types';

const { data, params } = $props<{ data: PageData; params: PageProps['params'] }>();
const token = data.token as string | null;
const project = data.project as ProjectSummary | null;
const projectId = (data.projectId as string | null) ?? project?.id ?? null;
const projectSlug = (data.projectSlug as string | null) ?? params.projectSlug ?? project?.slug ?? null;
const initialReports = (data.reports ?? null) as ReportListResponse | null;
const initialError = data.error as string | undefined;
</script>

<ProjectReportsPanel
	{token}
	{projectId}
	{projectSlug}
	initialReports={initialReports}
	initialError={initialError}
/>
