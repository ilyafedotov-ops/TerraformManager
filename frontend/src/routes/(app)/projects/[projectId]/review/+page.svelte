<script lang="ts">
    import { browser } from '$app/environment';
    import { API_BASE, updateProjectRun, type ProjectRunUpdatePayload, type ProjectSummary } from '$lib/api/client';
    import ScanForm, { type ScanFormData } from '$lib/components/review/ScanForm.svelte';
    import ScanSummary from '$lib/components/review/ScanSummary.svelte';
    import { activeProject, projectState } from '$lib/stores/project';
    import { notifyError, notifySuccess } from '$lib/stores/notifications';
    import { onDestroy } from 'svelte';
    import ProjectWorkspaceBanner from '$lib/components/projects/ProjectWorkspaceBanner.svelte';
    import type { PageData, PageParams } from './$types';

    const { data, params } = $props<{ data: PageData; params: PageParams }>();
    const token = data.token as string | null;
    const projectId = params.projectId ?? null;

    let files = $state<FileList | null>(null);
    let terraformValidate = $state(false);
    let saveReport = $state(true);
    let includeCost = $state(false);
    let usageFiles = $state<FileList | null>(null);
    let planFiles = $state<FileList | null>(null);
    let isSubmitting = $state(false);
    let error = $state<string | null>(null);
    let result = $state<{ id?: string | null; summary?: Record<string, unknown>; report?: Record<string, unknown> } | null>(null);
    let activeProjectValue = $state<ProjectSummary | null>(null);
    let missingProjectWarningShown = $state(false);
    let unsubscribeProject: (() => void) | null = null;

    if (browser) {
        unsubscribeProject = activeProject.subscribe((value) => {
            activeProjectValue = value;
            if (value) {
                missingProjectWarningShown = false;
            }
        });
    }

    onDestroy(() => {
        unsubscribeProject?.();
    });

    const toFileList = (file: File | null) => {
        if (!file) return null;
        if (typeof DataTransfer === 'undefined') return null;
        const dt = new DataTransfer();
        dt.items.add(file);
        return dt.files;
    };

    const submitScan = async (event?: Event, payload?: ScanFormData) => {
        event?.preventDefault();
        error = null;
        result = null;

        if (!token) {
            error = 'API token missing. Sign in to generate one or configure TFM_API_TOKEN on the server.';
            return;
        }
        const selectedFiles = payload?.files ?? files;
        const shouldValidate = payload?.terraformValidate ?? terraformValidate;
        const shouldSave = payload?.saveReport ?? saveReport;
        const includeCostFlag = payload?.includeCost ?? includeCost;
        const usageFile = payload?.usageFile ?? usageFiles?.item(0) ?? null;
        const planFile = payload?.planFile ?? planFiles?.item(0) ?? null;

        if (!selectedFiles || selectedFiles.length === 0) {
            error = 'Attach at least one .tf or .zip file to scan.';
            return;
        }

        const formData = new FormData();
        Array.from(selectedFiles).forEach((file) => formData.append('files', file));
        formData.append('terraform_validate', shouldValidate ? 'true' : 'false');
        formData.append('save', shouldSave ? 'true' : 'false');
        if (includeCostFlag) {
            formData.append('include_cost', 'true');
            if (usageFile) {
                formData.append('cost_usage_file', usageFile);
            }
        }
        if (planFile) {
            formData.append('plan_file', planFile);
        }

        files = selectedFiles;
        terraformValidate = shouldValidate;
        saveReport = shouldSave;
        includeCost = includeCostFlag;
        usageFiles = toFileList(usageFile);
        planFiles = toFileList(planFile);

        isSubmitting = true;
        try {
            const response = await fetch(`${API_BASE}/scan/upload`, {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${token}`
                },
                body: formData
            });
            if (!response.ok) {
                const detail = await response.text();
                throw new Error(detail || `Scan failed with status ${response.status}`);
            }
            const payload = await response.json();
            result = payload;
            void recordReviewRun(
                {
                    terraform_validate: shouldValidate,
                saved_report: shouldSave,
                include_cost: includeCostFlag,
                files: Array.from(selectedFiles).map((file) => file.name),
                cost_usage_file: usageFile?.name ?? null,
                plan_file: planFile?.name ?? null
                },
                payload
            );
        } catch (err) {
            error = err instanceof Error ? err.message : 'Unexpected error while running scan';
        } finally {
            isSubmitting = false;
        }
    };

    const severityEntries = () => {
        const summary = result?.summary as { severity_counts?: Record<string, number> } | undefined;
        const counts = summary?.severity_counts;
        if (!counts) return [] as Array<[string, number]>;
        return Object.entries(counts).map(([sev, count]) => [sev, Number(count ?? 0)] as [string, number]);
    };

    const getSteps = () => {
        const hasResult = Boolean(result);
        const hasReportId = Boolean(result?.id);
        const steps = [
            {
                title: 'Upload',
                description: 'Attach Terraform modules for scanning.',
                status: (hasResult ? 'completed' : 'current') as 'completed' | 'current' | 'upcoming'
            },
            {
                title: 'Review',
                description: 'Inspect findings and severity mix.',
                status: (hasResult ? 'current' : 'upcoming') as 'completed' | 'current' | 'upcoming'
            },
            {
                title: 'Export',
                description: 'Share JSON, CSV, or HTML artifacts.',
                status: (hasReportId ? 'current' : 'upcoming') as 'completed' | 'current' | 'upcoming'
            }
        ];
        return steps;
    };

	const buildRunSummary = (scanResult: Record<string, unknown> | null) => {
		if (!scanResult) return null;
		const summary = (scanResult.summary ?? null) as Record<string, unknown> | null;
		if (!summary) return null;
		const severity = summary?.severity_counts ?? null;
		const issues = summary?.issues_found ?? null;
		return {
			issues_found: issues,
			severity_counts: severity,
			saved_report_id: scanResult.id ?? null
		};
	};

	const recordReviewRun = async (
		parameters: Record<string, unknown>,
		scanResult: Record<string, unknown> | null
	) => {
		if (!browser) {
            return;
        }
        if (!activeProjectValue) {
            if (!missingProjectWarningShown) {
                notifyError('Select a project in the sidebar to log review runs.');
                missingProjectWarningShown = true;
            }
            return;
        }
        if (!token) {
            console.warn('Skipping project run logging because token is unavailable.');
            return;
        }
        try {
            const label = `Review • ${new Date().toLocaleString()}`;
            const savedReportId = (scanResult as { id?: string | null } | null)?.id ?? null;
            const run = await projectState.createRun(fetch, token, activeProjectValue.id, {
                label,
                kind: 'review',
                parameters,
				report_id: savedReportId ?? undefined
            });
            if (!run?.id) {
                return;
            }
            const summary = buildRunSummary(scanResult);
			const updatePayload: ProjectRunUpdatePayload = {
				status: 'completed',
				finished_at: new Date().toISOString(),
				summary: summary ?? undefined,
				report_id: savedReportId ?? undefined
			};
			try {
				const updated = await updateProjectRun(fetch, token, activeProjectValue.id, run.id, updatePayload);
				projectState.upsertRun(activeProjectValue.id, updated);
				notifySuccess('Review run recorded.');
			} catch (updateError) {
				console.warn('Failed to update review run status', updateError);
			}
		} catch (error) {
            console.warn('Unable to record review run', error);
        }
    };
</script>

<section class="space-y-8">
	<header class="space-y-3">
		<p class="text-xs font-semibold uppercase tracking-[0.35em] text-slate-400">Reviewer</p>
		<h2 class="text-3xl font-semibold text-slate-700">Upload Terraform for analysis</h2>
		<p class="max-w-3xl text-sm text-slate-500">
			Drop one or more Terraform modules (individual <code class="rounded bg-slate-50 px-1 py-0.5 text-xs text-slate-600">.tf</code> files or zipped directories).
			The backend will unpack archives, apply the configured review rules, and optionally persist the report for later lookup.
		</p>
	</header>

	<ProjectWorkspaceBanner context="Review runs are logged to your active workspace alongside generator history and artifacts." />

	<ScanForm
        steps={getSteps()}
        bind:files
        bind:terraformValidate
        bind:saveReport
        bind:includeCost
        bind:usageFiles
        bind:planFiles
        isSubmitting={isSubmitting}
        error={error}
        on:submit={(event) => submitScan(undefined, event.detail)}
    />

    {#if result}
        <ScanSummary
            reportId={result.id ?? null}
            summary={(result.summary ?? null) as Record<string, unknown> | null}
            report={(result.report ?? null) as Record<string, unknown> | null}
            severityEntries={severityEntries()}
            apiBase={API_BASE}
            projectId={projectId}
        />
    {/if}
</section>
