<script lang="ts">
    import { API_BASE } from '$lib/api/client';
    import ScanForm, { type ScanFormData } from '$lib/components/review/ScanForm.svelte';
    import ScanSummary from '$lib/components/review/ScanSummary.svelte';

    const { data } = $props();
    const token = data.token as string | null;

    let files = $state<FileList | null>(null);
    let terraformValidate = $state(false);
    let saveReport = $state(true);
    let includeCost = $state(false);
    let usageFiles = $state<FileList | null>(null);
    let planFiles = $state<FileList | null>(null);
    let isSubmitting = $state(false);
    let error = $state<string | null>(null);
    let result = $state<{ id?: string | null; summary?: Record<string, unknown>; report?: Record<string, unknown> } | null>(null);

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
            result = await response.json();
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
</script>

<section class="space-y-8">
    <header class="space-y-3">
        <p class="text-xs font-semibold uppercase tracking-[0.35em] text-blueGray-400">Reviewer</p>
        <h2 class="text-3xl font-semibold text-blueGray-700">Upload Terraform for analysis</h2>
        <p class="max-w-3xl text-sm text-blueGray-500">
            Drop one or more Terraform modules (individual <code class="rounded bg-blueGray-50 px-1 py-0.5 text-xs text-blueGray-600">.tf</code> files or zipped directories).
            The backend will unpack archives, apply the configured review rules, and optionally persist the report for later lookup.
        </p>
    </header>

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
        />
    {/if}
</section>
