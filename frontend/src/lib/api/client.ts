import { env } from '$env/dynamic/public';

const DEFAULT_BASE = 'http://localhost:8787';
export const API_BASE = (env.PUBLIC_API_BASE ?? DEFAULT_BASE).replace(/\/$/, '');

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface ApiRequestOptions<TBody = unknown> {
	method?: HttpMethod;
	token?: string | null;
	searchParams?: Record<string, string | number | boolean | undefined>;
	body?: TBody;
	headers?: HeadersInit;
}

export class ApiError extends Error {
	status: number;
	detail: unknown;

	constructor(message: string, status: number, detail: unknown) {
		super(message);
		this.name = 'ApiError';
		this.status = status;
		this.detail = detail;
	}
}

function buildUrl(path: string, searchParams?: ApiRequestOptions['searchParams']): string {
    const url = new URL(path.startsWith('/') ? path : `/${path}`, API_BASE);
	if (searchParams) {
		for (const [key, value] of Object.entries(searchParams)) {
			if (value === undefined || value === null) continue;
			url.searchParams.set(key, String(value));
		}
	}
	return url.toString();
}

function normaliseBody(body: unknown): BodyInit | undefined {
	if (body instanceof FormData || body instanceof URLSearchParams || body instanceof Blob) {
		return body;
	}
	if (body === undefined || body === null) {
		return undefined;
	}
	return JSON.stringify(body);
}

function buildHeaders(token: string | null | undefined, extra?: HeadersInit, attachJsonContentType = false): Headers {
    const headers = new Headers(extra ?? undefined);
    if (attachJsonContentType && !headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json');
    }
    if (!attachJsonContentType && headers.get('Content-Type') === 'application/json') {
        headers.delete('Content-Type');
    }
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }
    return headers;
}

export async function apiFetch<TResponse, TBody = unknown>(
    fetchFn: typeof fetch,
    path: string,
    { method = 'GET', token, searchParams, body, headers }: ApiRequestOptions<TBody> = {}
): Promise<TResponse> {
    const url = buildUrl(path, searchParams);
    const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
    const isUrlParams = body instanceof URLSearchParams;
    const isBlob = typeof Blob !== 'undefined' && body instanceof Blob;
    const isStructuredBody = isFormData || isUrlParams || isBlob;
    const bodyInit = normaliseBody(body);

    const init: RequestInit = {
        method,
        headers: buildHeaders(token, headers, bodyInit !== undefined && !isStructuredBody),
        body: bodyInit
    };

    if (init.body === undefined && init.headers instanceof Headers) {
        init.headers.delete('Content-Type');
    }

	const response = await fetchFn(url, init);

	if (!response.ok) {
		let detail: unknown = null;
		try {
			const contentType = response.headers.get('content-type');
			detail = contentType && contentType.includes('application/json') ? await response.json() : await response.text();
		} catch {
			detail = null;
		}
		throw new ApiError(`Request failed with status ${response.status}`, response.status, detail);
	}

	if (response.status === 204) {
		return undefined as TResponse;
	}

	const contentType = response.headers.get('content-type');
	if (contentType && contentType.includes('application/json')) {
		return (await response.json()) as TResponse;
	}

	return (await response.text()) as TResponse;
}

export interface ReportSummary {
	id: string;
	created_at?: string;
	summary?: {
		issues_found?: number;
		severity_counts?: Record<string, number>;
	};
}

export interface ReportDetail {
    id?: string;
    summary?: ReportSummary['summary'] & {
        issues_found?: number;
        thresholds?: Record<string, unknown>;
        generated_at?: string;
        created_at?: string;
    };
    findings?: Array<Record<string, unknown>>;
}

export async function listReports(
    fetchFn: typeof fetch,
    token: string,
    limit = 20
): Promise<ReportSummary[]> {
    return apiFetch<ReportSummary[]>(fetchFn, '/reports', {
        token,
        searchParams: { limit }
    });
}

export async function getReport(fetchFn: typeof fetch, token: string, id: string): Promise<ReportDetail> {
    return apiFetch<ReportDetail>(fetchFn, `/reports/${id}`, { token });
}

export interface KnowledgeItem {
    source: string;
    content: string;
    score: number;
}

export async function searchKnowledge(
    fetchFn: typeof fetch,
    query: string,
    topK = 3
): Promise<KnowledgeItem[]> {
    const response = await apiFetch<{ items: KnowledgeItem[] }>(fetchFn, '/knowledge/search', {
        searchParams: { q: query, top_k: topK }
    });
    return response.items;
}

export interface LLMSettingsResponse {
    provider?: string;
    model?: string | null;
    enable_explanations?: boolean;
    enable_patches?: boolean;
    api_base?: string | null;
    api_version?: string | null;
    deployment_name?: string | null;
}

export async function getLLMSettings(fetchFn: typeof fetch, token: string): Promise<LLMSettingsResponse> {
    return apiFetch<LLMSettingsResponse>(fetchFn, '/settings/llm', { token });
}

export async function saveLLMSettings(
    fetchFn: typeof fetch,
    token: string,
    payload: LLMSettingsResponse
): Promise<{ status: string }> {
    return apiFetch(fetchFn, '/settings/llm', {
        method: 'POST',
        token,
        body: payload
    });
}

export interface LLMTestResult {
    ok: boolean;
    stage: string;
    provider?: string;
    model?: string;
    response?: unknown;
    error?: string;
}

export async function testLLMSettings(
    fetchFn: typeof fetch,
    token: string,
    live = false
): Promise<LLMTestResult> {
    return apiFetch(fetchFn, '/settings/llm/test', {
        method: 'POST',
        token,
        body: { live }
    });
}

export interface AwsS3GeneratorPayload {
    bucket_name: string;
    region: string;
    environment: string;
    owner_tag: string;
    cost_center_tag: string;
    force_destroy: boolean;
    versioning: boolean;
    enforce_secure_transport: boolean;
    kms_key_id?: string | null;
    backend?: {
        bucket: string;
        key: string;
        region: string;
        dynamodb_table: string;
    } | null;
}

export interface GeneratorResult {
    filename: string;
    content: string;
}

export async function generateAwsS3(
    fetchFn: typeof fetch,
    payload: AwsS3GeneratorPayload
): Promise<GeneratorResult> {
    return apiFetch(fetchFn, '/generators/aws/s3', {
        method: 'POST',
        body: payload
    });
}

export interface AzureStorageGeneratorPayload {
    resource_group_name: string;
    storage_account_name: string;
    location: string;
    environment: string;
    replication: string;
    versioning: boolean;
    owner_tag: string;
    cost_center_tag: string;
    restrict_network: boolean;
    allowed_ips: string[];
    private_endpoint?: {
        name: string;
        connection_name: string;
        subnet_id: string;
        private_dns_zone_id?: string | null;
        dns_zone_group_name?: string | null;
    } | null;
    backend?: {
        resource_group: string;
        storage_account: string;
        container: string;
        key: string;
    } | null;
}

export async function generateAzureStorageAccount(
    fetchFn: typeof fetch,
    payload: AzureStorageGeneratorPayload
): Promise<GeneratorResult> {
    return apiFetch(fetchFn, '/generators/azure/storage-account', {
        method: 'POST',
        body: payload
    });
}

export interface KnowledgeSyncResult {
    source: string;
    dest_dir: string;
    files: string[];
    note?: string | null;
}

export async function syncKnowledge(
    fetchFn: typeof fetch,
    token: string,
    sources: string[]
): Promise<KnowledgeSyncResult[]> {
    const response = await apiFetch<{ synced: KnowledgeSyncResult[] }>(fetchFn, '/knowledge/sync', {
        method: 'POST',
        token,
        body: { sources }
    });
    return response.synced;
}

export interface ReviewConfigRecord {
    name: string;
    payload: string;
    kind?: string;
    updated_at?: string;
}

export async function listReviewConfigs(fetchFn: typeof fetch, token: string): Promise<ReviewConfigRecord[]> {
    return apiFetch(fetchFn, '/configs', { token });
}

export async function saveReviewConfig(
    fetchFn: typeof fetch,
    token: string,
    config: { name: string; payload: string; kind?: string }
): Promise<{ status: string; name: string }> {
    return apiFetch(fetchFn, '/configs', {
        method: 'POST',
        token,
        body: {
            name: config.name,
            payload: config.payload,
            kind: config.kind ?? 'tfreview'
        }
    });
}

export async function deleteReviewConfig(fetchFn: typeof fetch, token: string, name: string): Promise<{ status: string; name: string }> {
    return apiFetch(fetchFn, `/configs/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        token
    });
}

export interface ConfigPreviewPayload {
    config_name: string;
    report_id?: string | null;
    paths?: string[] | null;
}

export interface ConfigPreviewResponse {
    summary: {
        before: Record<string, unknown>;
        after: Record<string, unknown>;
    };
    waived: Array<Record<string, unknown>>;
    active: Array<Record<string, unknown>>;
}

export async function previewConfigApplication(
    fetchFn: typeof fetch,
    token: string,
    payload: ConfigPreviewPayload
): Promise<ConfigPreviewResponse> {
    return apiFetch(fetchFn, '/preview/config-application', {
        method: 'POST',
        token,
        body: payload
    });
}
