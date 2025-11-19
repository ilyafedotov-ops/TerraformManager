import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

const DEFAULT_BASE = 'http://localhost:8890';

const resolveBrowserBase = () => {
    if (!browser) return DEFAULT_BASE;
    const targetPort = env.PUBLIC_API_PORT || '8890';
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:${targetPort}`;
};

const resolvedBase = env.PUBLIC_API_BASE ?? resolveBrowserBase();
export const API_BASE = resolvedBase.replace(/\/$/, '');

type ProjectResolver = () => string | null;
let projectIdentifierResolver: ProjectResolver | null = null;

export const registerProjectIdentifierResolver = (resolver: ProjectResolver) => {
	projectIdentifierResolver = resolver;
};

const resolveProjectIdentifier = (projectId?: string | null): string => {
	if (projectId && projectId.trim().length > 0) {
		return projectId;
	}
	const resolved = projectIdentifierResolver?.() ?? null;
	if (resolved && resolved.trim().length > 0) {
		return resolved;
	}
	throw new Error('Project context is required. Pass projectId explicitly or set an active project.');
};

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface ApiRequestOptions<TBody = unknown> {
	method?: HttpMethod;
	token?: string | null;
	searchParams?: Record<string, string | number | boolean | undefined> | URLSearchParams;
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

export interface CostSummary {
	currency?: string | null;
	total_monthly_cost?: number | null;
	total_hourly_cost?: number | null;
	diff_monthly_cost?: number | null;
	diff_hourly_cost?: number | null;
}

export interface CostProject {
	name?: string | null;
	path?: string | null;
	monthly_cost?: number | null;
	diff_monthly_cost?: number | null;
	hourly_cost?: number | null;
	diff_hourly_cost?: number | null;
}

export interface CostReport {
	tool?: string;
	currency?: string | null;
	summary?: CostSummary | null;
	projects?: CostProject[] | null;
	errors?: string[] | null;
}

export interface DriftCounts {
	create?: number;
	update?: number;
	delete?: number;
	replace?: number;
	'no-op'?: number;
}

export interface DriftChange {
	address?: string | null;
	action?: string | null;
	actions?: string[] | null;
}

export interface DriftOutputChange {
	name?: string | null;
	actions?: string[] | null;
	before?: unknown;
	after?: unknown;
}

export interface DriftSummary {
	has_changes?: boolean;
	total_changes?: number;
	counts?: DriftCounts | null;
}

export interface DriftReport extends DriftSummary {
	source?: string | null;
	resource_changes?: DriftChange[] | null;
	output_changes?: DriftOutputChange[] | null;
	error?: string | null;
}

export interface ProjectListLatestRun {
	id: string;
	label: string;
	kind: string;
	status: string;
	created_at?: string | null;
	updated_at?: string | null;
	finished_at?: string | null;
}

export interface ProjectSummary {
	id: string;
	name: string;
	slug: string;
	root_path: string;
	description?: string | null;
	created_at?: string | null;
	updated_at?: string | null;
	last_activity_at?: string | null;
	run_count?: number;
	library_asset_count?: number;
	config_count?: number;
	artifact_count?: number;
	latest_run?: ProjectListLatestRun | null;
	metadata?: Record<string, unknown> | null;
}

export interface ProjectDetail extends ProjectSummary {
	metadata?: Record<string, unknown> | null;
}

export interface ProjectCreatePayload {
	name: string;
	description?: string;
	slug?: string;
	metadata?: Record<string, unknown>;
}

export interface ProjectRunSummary {
	id: string;
	project_id: string;
	label: string;
	kind: string;
	status: string;
	triggered_by?: string | null;
	parameters?: Record<string, unknown> | null;
	summary?: Record<string, unknown> | null;
	artifacts_path?: string | null;
	created_at?: string | null;
	updated_at?: string | null;
	started_at?: string | null;
	finished_at?: string | null;
	report_id?: string | null;
}

export interface ProjectRunCreatePayload {
	label: string;
	kind: string;
	parameters?: Record<string, unknown>;
	status?: string;
	triggered_by?: string | null;
	projects_root?: string | null;
	report_id?: string | null;
}

export interface ProjectUpdatePayload {
	name?: string;
	description?: string;
	metadata?: Record<string, unknown> | null;
}

export interface ProjectRunUpdatePayload {
	status?: string;
	summary?: Record<string, unknown> | null;
	started_at?: string;
	finished_at?: string;
	report_id?: string | null;
}

export interface PaginatedResult<T> {
	items: T[];
	nextCursor?: string | null;
	totalCount: number;
}

export interface ProjectOverviewMetrics {
	cost?: Record<string, unknown> | null;
	drift?: Record<string, unknown> | null;
	policy?: Record<string, unknown> | null;
}

export interface ProjectOverview {
	project: ProjectDetail;
	run_count: number;
	latest_run?: ProjectRunSummary | null;
	library_asset_count: number;
	config_count: number;
	default_config?: ProjectConfigRecord | null;
	artifact_count: number;
	recent_assets: GeneratedAssetSummary[];
	recent_artifacts: ProjectArtifactRecord[];
	metrics: ProjectOverviewMetrics;
	last_activity_at?: string | null;
}

export interface ArtifactEntry {
	name: string;
	path: string;
	is_dir: boolean;
	size?: number | null;
	modified_at?: string | null;
	artifact_id?: string | null;
	media_type?: string | null;
	tags?: string[] | null;
	metadata?: Record<string, unknown> | null;
}

export interface ProjectConfigRecord {
	id: string;
	project_id: string;
	name: string;
	slug: string;
	description?: string | null;
	config_name?: string | null;
	kind: string;
	payload?: string | null;
	tags: string[];
	metadata: Record<string, unknown>;
	is_default: boolean;
	created_at?: string | null;
	updated_at?: string | null;
}

export interface ProjectConfigCreatePayload {
	name: string;
	slug?: string | null;
	description?: string | null;
	config_name?: string | null;
	payload?: string | null;
	kind?: string;
	tags?: string[];
	metadata?: Record<string, unknown>;
	is_default?: boolean;
}

export interface ProjectConfigUpdatePayload {
	name?: string;
	description?: string | null;
	config_name?: string | null;
	payload?: string | null;
	kind?: string | null;
	tags?: string[] | null;
	metadata?: Record<string, unknown> | null;
	is_default?: boolean | null;
}

export interface ProjectArtifactRecord {
	id: string;
	project_id: string;
	run_id?: string | null;
	report_id?: string | null;
	name: string;
	relative_path: string;
	storage_path: string;
	media_type?: string | null;
	size_bytes?: number | null;
	checksum?: string | null;
	tags: string[];
	metadata: Record<string, unknown>;
	created_at?: string | null;
	updated_at?: string | null;
}

export interface ProjectArtifactUpdatePayload {
	tags?: string[];
	metadata?: Record<string, unknown>;
	media_type?: string | null;
}

export interface ProjectArtifactListResponse {
	items: ProjectArtifactRecord[];
	nextCursor?: string | null;
	totalCount: number;
}

export interface ProjectArtifactSyncResponse {
	added: number;
	updated: number;
	removed: number;
	files_indexed: number;
}

export interface GeneratedAssetVersionSummary {
	id: string;
	asset_id: string;
	project_id: string;
	run_id?: string | null;
	report_id?: string | null;
	storage_path: string;
	display_path: string;
	checksum?: string | null;
	size_bytes?: number | null;
	media_type?: string | null;
	notes?: string | null;
	created_at?: string | null;
	validation_summary?: Record<string, unknown> | null;
	metadata: Record<string, unknown>;
	payload_fingerprint?: string | null;
}

export interface GeneratedAssetSummary {
	id: string;
	project_id: string;
	name: string;
	description?: string | null;
	asset_type: string;
	tags: string[];
	metadata: Record<string, unknown>;
	latest_version_id?: string | null;
	created_at?: string | null;
	updated_at?: string | null;
	versions?: GeneratedAssetVersionSummary[] | null;
}

export interface GeneratedAssetRegisterResponse {
	asset: GeneratedAssetSummary;
	version: GeneratedAssetVersionSummary;
}

export interface GeneratedAssetDiffFileEntry {
	path: string;
	status: string;
	base?: {
		storage_path: string;
		checksum?: string | null;
		size_bytes?: number | null;
		media_type?: string | null;
	} | null;
	compare?: {
		storage_path: string;
		checksum?: string | null;
		size_bytes?: number | null;
		media_type?: string | null;
	} | null;
	diff?: string | null;
}

export interface GeneratedAssetDiffResponse {
	base: GeneratedAssetVersionSummary;
	compare: GeneratedAssetVersionSummary;
	diff: string;
	ignore_whitespace?: boolean;
	files?: GeneratedAssetDiffFileEntry[];
}

export interface GeneratedAssetVersionFile {
	id: string;
	version_id: string;
	project_id: string;
	path: string;
	storage_path: string;
	checksum?: string | null;
	size_bytes?: number | null;
	media_type?: string | null;
	created_at?: string | null;
}

export interface GeneratedAssetCreatePayload {
	name: string;
	asset_type: string;
	description?: string | null;
	tags?: string[];
	metadata?: Record<string, unknown>;
	run_id?: string | null;
	report_id?: string | null;
	artifact_path?: string | null;
	storage_filename?: string | null;
	media_type?: string | null;
	notes?: string | null;
	content_base64?: string | null;
}

export interface GeneratedAssetVersionCreatePayload {
	run_id?: string | null;
	report_id?: string | null;
	artifact_path?: string | null;
	storage_filename?: string | null;
	media_type?: string | null;
	notes?: string | null;
	content_base64?: string | null;
	promote_latest?: boolean;
}

export interface GeneratedAssetUpdatePayload {
	name?: string | null;
	asset_type?: string | null;
	description?: string | null;
	tags?: string[] | null;
	metadata?: Record<string, unknown> | null;
}

function buildUrl(path: string, searchParams?: ApiRequestOptions['searchParams']): string {
	const url = new URL(path.startsWith('/') ? path : `/${path}`, API_BASE);
	if (!searchParams) {
		return url.toString();
	}
	if (searchParams instanceof URLSearchParams) {
		for (const [key, value] of searchParams.entries()) {
			url.searchParams.append(key, value);
		}
		return url.toString();
	}
	for (const [key, value] of Object.entries(searchParams)) {
		if (value === undefined || value === null) continue;
		url.searchParams.set(key, String(value));
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

export interface RefreshSessionResponse {
	access_token: string;
	expires_in: number;
	refresh_token?: string | null;
	refresh_expires_in: number;
	anti_csrf_token?: string | null;
	session_id?: string | null;
}

export interface AuthSession {
	id: string;
	family_id?: string | null;
	created_at: string;
	last_used_at?: string | null;
	expires_at: string;
	ip_address?: string | null;
	user_agent?: string | null;
	scopes: string[];
	is_current: boolean;
}

export interface SessionListResponse {
	sessions: AuthSession[];
	current_session_id?: string | null;
}

export async function refreshSession(
	fetchFn: typeof fetch,
	csrfToken: string,
	cookieHeader?: string
): Promise<RefreshSessionResponse> {
	const headers = new Headers({
		'X-Refresh-Token-CSRF': csrfToken,
		Accept: 'application/json'
	});
	if (cookieHeader) {
		headers.set('cookie', cookieHeader);
	}

	const response = await fetchFn(`${API_BASE}/auth/refresh`, {
		method: 'POST',
		headers,
		credentials: 'include'
	});

	if (!response.ok) {
		let detail: unknown = null;
		try {
			const contentType = response.headers.get('content-type');
			detail = contentType && contentType.includes('application/json') ? await response.json() : await response.text();
		} catch {
			detail = null;
		}
		throw new ApiError(`Refresh failed with status ${response.status}`, response.status, detail);
	}

	const data = (await response.json()) as RefreshSessionResponse;
	const headerCsrf = response.headers.get('X-Refresh-Token-CSRF');
	if (headerCsrf) {
		data.anti_csrf_token = headerCsrf;
	}
	return data;
}

export async function listAuthSessions(fetchFn: typeof fetch, token: string): Promise<SessionListResponse> {
	return apiFetch<SessionListResponse>(fetchFn, '/auth/sessions', {
		token
	});
}

export async function revokeAuthSession(
	fetchFn: typeof fetch,
	token: string,
	sessionId: string
): Promise<{ status: string; session_id?: string; revoked_at?: string | null }> {
	return apiFetch(fetchFn, `/auth/sessions/${encodeURIComponent(sessionId)}`, {
		method: 'DELETE',
		token
	});
}

export async function getUserProfile(fetchFn: typeof fetch, token: string): Promise<UserProfileResponse> {
	return apiFetch<UserProfileResponse>(fetchFn, '/auth/me', {
		token
	});
}

export async function updateUserProfile(
	fetchFn: typeof fetch,
	token: string,
	payload: ProfileUpdatePayload
): Promise<UserProfileResponse> {
	return apiFetch<UserProfileResponse>(fetchFn, '/auth/me', {
		method: 'PUT',
		token,
		body: payload
	});
}

export async function changePassword(
	fetchFn: typeof fetch,
	token: string,
	payload: PasswordChangePayload
): Promise<{ status: string; revoked_sessions?: number }> {
	return apiFetch(fetchFn, '/auth/me/password', {
		method: 'POST',
		token,
		body: payload
	});
}

export interface AuthEvent {
	id: string;
	event: string;
	created_at: string;
	subject?: string | null;
	session_id?: string | null;
	ip_address?: string | null;
	user_agent?: string | null;
	scopes: string[];
	details: Record<string, unknown>;
}

export interface AuthEventListResponse {
	events: AuthEvent[];
}

export interface NotificationPreferences {
	email?: boolean;
	browser?: boolean;
	[key: string]: unknown;
}

export interface UserPreferences {
	notifications?: NotificationPreferences;
	[key: string]: unknown;
}

export interface UserProfileResponse {
	id: string;
	email: string;
	scopes: string[];
	expires_in: number;
	full_name?: string | null;
	job_title?: string | null;
	timezone?: string | null;
	avatar_url?: string | null;
	preferences?: UserPreferences | null;
	created_at?: string | null;
	updated_at?: string | null;
	last_login_at?: string | null;
}

export interface ProfileUpdatePayload {
	full_name?: string | null;
	job_title?: string | null;
	timezone?: string | null;
	avatar_url?: string | null;
	preferences?: UserPreferences | null;
}

export interface PasswordChangePayload {
	current_password: string;
	new_password: string;
	confirm_new_password: string;
}

export async function listAuthEvents(
	fetchFn: typeof fetch,
	token: string,
	limit = 25
): Promise<AuthEventListResponse> {
	return apiFetch<AuthEventListResponse>(fetchFn, '/auth/events', {
		token,
		searchParams: { limit }
	});
}

export interface ReportSummary {
	id: string;
	created_at?: string | null;
	updated_at?: string | null;
	review_status?: string | null;
	review_assignee?: string | null;
	review_due_at?: string | null;
	review_notes?: string | null;
	summary?: {
		issues_found?: number;
		severity_counts?: Record<string, number>;
		files_scanned?: number;
		cost?: CostSummary | null;
		drift?: DriftSummary | null;
	};
}

export interface ReportDetail {
	id?: string;
	review_status?: string | null;
	review_assignee?: string | null;
	review_due_at?: string | null;
	review_notes?: string | null;
	created_at?: string | null;
	updated_at?: string | null;
	summary?: ReportSummary['summary'] & {
		issues_found?: number;
		thresholds?: Record<string, unknown>;
		generated_at?: string;
		created_at?: string;
	};
	findings?: Array<Record<string, unknown>>;
	cost?: CostReport | null;
	drift?: DriftReport | null;
	waived_findings?: Array<Record<string, unknown>>;
	report?: Record<string, unknown>;
}

export interface ReportListAggregates {
	status_counts?: Record<string, number>;
	severity_counts?: Record<string, number>;
}

export interface ReportListResponse {
	items: ReportSummary[];
	total_count: number;
	limit: number;
	offset: number;
	next_offset?: number | null;
	has_more: boolean;
	aggregates?: ReportListAggregates;
}

export interface ListReportsParams {
	limit?: number;
	offset?: number;
	status?: string[] | string;
	assignee?: string;
	search?: string;
	created_after?: string;
	created_before?: string;
	order?: 'asc' | 'desc';
	project_id?: string;
	project_slug?: string;
}

export async function listReports(
	fetchFn: typeof fetch,
	token: string,
	params: ListReportsParams = {}
): Promise<ReportListResponse> {
	const searchParams = new URLSearchParams();
	const effectiveLimit = params.limit ?? 50;

	searchParams.set('limit', String(effectiveLimit));
	if (typeof params.offset === 'number' && params.offset >= 0) {
		searchParams.set('offset', String(params.offset));
	}
	if (params.assignee) {
		searchParams.set('assignee', params.assignee);
	}
	if (params.search) {
		searchParams.set('search', params.search);
	}
	if (params.created_after) {
		searchParams.set('created_after', params.created_after);
	}
	if (params.created_before) {
		searchParams.set('created_before', params.created_before);
	}
	if (params.order) {
		searchParams.set('order', params.order);
	}
	if (params.project_id) {
		searchParams.set('project_id', params.project_id);
	}
	if (params.project_slug) {
		searchParams.set('project_slug', params.project_slug);
	}
	if (params.status) {
		const statuses = Array.isArray(params.status) ? params.status : [params.status];
		for (const value of statuses) {
			searchParams.append('status', value);
		}
	}

	return apiFetch<ReportListResponse>(fetchFn, '/reports', {
		token,
		searchParams
	});
}

interface ReportRecordResponse {
    id: string;
    summary?: ReportSummary['summary'];
    report?: Record<string, unknown> | null;
    review_status?: string | null;
    review_assignee?: string | null;
    review_due_at?: string | null;
    review_notes?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
}

function mergeReportResponse(payload: ReportRecordResponse): ReportDetail {
    const base: ReportDetail = {
        id: payload.id,
        review_status: payload.review_status ?? null,
        review_assignee: payload.review_assignee ?? null,
        review_due_at: payload.review_due_at ?? null,
        review_notes: payload.review_notes ?? null,
        created_at: payload.created_at ?? null,
        updated_at: payload.updated_at ?? null,
        summary: payload.summary,
        report: payload.report ?? undefined,
        findings: undefined,
        cost: undefined,
        drift: undefined,
        waived_findings: undefined
    };

    if (payload.report && typeof payload.report === 'object') {
        const reportData = payload.report as Record<string, unknown>;

        if (reportData.summary && typeof reportData.summary === 'object') {
            base.summary = reportData.summary as ReportDetail['summary'];
        }

        if (Array.isArray(reportData.findings)) {
            base.findings = reportData.findings as ReportDetail['findings'];
        }

        if (reportData.cost) {
            base.cost = reportData.cost as ReportDetail['cost'];
        }

        if (reportData.drift) {
            base.drift = reportData.drift as ReportDetail['drift'];
        }

        if (Array.isArray(reportData.waived_findings)) {
            base.waived_findings = reportData.waived_findings as ReportDetail['waived_findings'];
        }
    }

    return base;
}

export async function getReport(fetchFn: typeof fetch, token: string, id: string): Promise<ReportDetail> {
    const payload = await apiFetch<ReportRecordResponse>(fetchFn, `/reports/${encodeURIComponent(id)}`, { token });
    return mergeReportResponse(payload);
}

export interface ReportReviewUpdatePayload {
	review_status?: string | null;
	review_assignee?: string | null;
	review_due_at?: string | null;
	review_notes?: string | null;
}

export interface ReportReviewMetadata {
	id: string;
	review_status?: string | null;
	review_assignee?: string | null;
	review_due_at?: string | null;
	review_notes?: string | null;
	updated_at?: string | null;
}

export interface ReportComment {
	id: string;
	report_id: string;
	body: string;
	author?: string | null;
	created_at?: string | null;
	updated_at?: string | null;
}

export async function updateReportReviewMetadata(
	fetchFn: typeof fetch,
	token: string,
	id: string,
	payload: ReportReviewUpdatePayload,
	options?: { projectId?: string | null; projectSlug?: string | null }
): Promise<ReportReviewMetadata> {
	const searchParams = new URLSearchParams();
	if (options?.projectId) {
		searchParams.set('project_id', options.projectId);
	}
	if (options?.projectSlug) {
		searchParams.set('project_slug', options.projectSlug);
	}
	return apiFetch<ReportReviewMetadata>(fetchFn, `/reports/${encodeURIComponent(id)}`, {
		method: 'PATCH',
		token,
		body: payload,
		searchParams: searchParams.size ? searchParams : undefined
	});
}

export async function listReportComments(
	fetchFn: typeof fetch,
	token: string,
	reportId: string,
	options?: { projectId?: string | null; projectSlug?: string | null }
): Promise<ReportComment[]> {
	const searchParams = new URLSearchParams();
	if (options?.projectId) {
		searchParams.set('project_id', options.projectId);
	}
	if (options?.projectSlug) {
		searchParams.set('project_slug', options.projectSlug);
	}
	const response = await apiFetch<{ items: ReportComment[] }>(
		fetchFn,
		`/reports/${encodeURIComponent(reportId)}/comments`,
		{
			token,
			searchParams: searchParams.size ? searchParams : undefined
		}
	);
	return response.items;
}

export async function createReportComment(
	fetchFn: typeof fetch,
	token: string,
	reportId: string,
	body: string,
	author?: string | null,
	options?: { projectId?: string | null; projectSlug?: string | null }
): Promise<ReportComment> {
	const searchParams = new URLSearchParams();
	if (options?.projectId) {
		searchParams.set('project_id', options.projectId);
	}
	if (options?.projectSlug) {
		searchParams.set('project_slug', options.projectSlug);
	}
	return apiFetch<ReportComment>(fetchFn, `/reports/${encodeURIComponent(reportId)}/comments`, {
		method: 'POST',
		token,
		searchParams: searchParams.size ? searchParams : undefined,
		body: {
			body,
			author: author ?? undefined
		}
	});
}

export async function deleteReportComment(
	fetchFn: typeof fetch,
	token: string,
	reportId: string,
	commentId: string,
	options?: { projectId?: string | null; projectSlug?: string | null }
): Promise<{ status: string; id: string }> {
	const searchParams = new URLSearchParams();
	if (options?.projectId) {
		searchParams.set('project_id', options.projectId);
	}
	if (options?.projectSlug) {
		searchParams.set('project_slug', options.projectSlug);
	}
	return apiFetch(fetchFn, `/reports/${encodeURIComponent(reportId)}/comments/${encodeURIComponent(commentId)}`, {
		method: 'DELETE',
		token,
		searchParams: searchParams.size ? searchParams : undefined
	});
}

export async function deleteReport(fetchFn: typeof fetch, token: string, id: string): Promise<{ status: string; id: string }> {
    return apiFetch(fetchFn, `/reports/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        token
    });
}

export interface KnowledgeItem {
    source: string;
    content: string;
    score: number;
}

export interface KnowledgeDocument {
    path: string;
    title: string;
    content: string;
}

export async function searchKnowledge(
	fetchFn: typeof fetch,
	query: string,
	topK = 3,
	provider?: string
): Promise<KnowledgeItem[]> {
	const searchParams: Record<string, string | number> = { q: query, top_k: topK };
	if (provider && provider.trim().length > 0) {
		searchParams.provider = provider;
	}
	const response = await apiFetch<{ items: KnowledgeItem[] }>(fetchFn, '/knowledge/search', {
		searchParams
	});
	return response.items;
}

export async function getKnowledgeDocument(fetchFn: typeof fetch, token: string, path: string): Promise<KnowledgeDocument> {
    return apiFetch(fetchFn, '/knowledge/doc', {
        token,
        searchParams: { path }
    });
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

export interface AzureFunctionAppGeneratorPayload {
    resource_group_name: string;
    function_app_name: string;
    storage_account_name: string;
    app_service_plan_name: string;
    location: string;
    environment: string;
    runtime: string;
    runtime_version: string;
    app_service_plan_sku: string;
    storage_replication: string;
    enable_vnet_integration: boolean;
    vnet_subnet_id?: string | null;
    enable_application_insights: boolean;
    application_insights_name: string;
    diagnostics?: {
        workspace_resource_id: string;
        log_categories?: string[];
        metric_categories?: string[];
    } | null;
    owner_tag: string;
    cost_center_tag: string;
}

export interface AzureApiManagementGeneratorPayload {
    resource_group_name: string;
    name: string;
    location: string;
    environment: string;
    publisher_name: string;
    publisher_email: string;
    sku_name: string;
    capacity?: number | null;
    zones: string[];
    virtual_network_type: string;
    subnet_id?: string | null;
    identity_type: string;
    custom_properties: Record<string, string>;
    diagnostics?: {
        workspace_resource_id: string;
        log_categories?: string[];
        metric_categories?: string[];
    } | null;
    owner_tag: string;
    cost_center_tag: string;
}

export async function generateAzureFunctionApp(
    fetchFn: typeof fetch,
    payload: AzureFunctionAppGeneratorPayload
): Promise<GeneratorResult> {
    return apiFetch(fetchFn, '/generators/azure/function-app', {
        method: 'POST',
        body: payload
    });
}

export async function generateAzureApiManagement(
	fetchFn: typeof fetch,
	payload: AzureApiManagementGeneratorPayload
): Promise<GeneratorResult> {
	return apiFetch(fetchFn, '/generators/azure/api-management', {
		method: 'POST',
		body: payload
	});
}

export interface ProjectGeneratorRunOptions {
	asset_name?: string | null;
	description?: string | null;
	tags?: string[];
	metadata?: Record<string, unknown>;
	notes?: string | null;
	run_label?: string | null;
	force_save?: boolean;
}

export interface ProjectGeneratorRunRequest {
	payload: Record<string, unknown>;
	options?: ProjectGeneratorRunOptions;
}

export interface ProjectGeneratorRunResponse {
	output: GeneratorResult;
	asset: GeneratedAssetSummary;
	version: GeneratedAssetVersionSummary;
	run: ProjectRunSummary;
}

export async function runProjectGenerator(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	slug: string,
	request: ProjectGeneratorRunRequest
): Promise<ProjectGeneratorRunResponse> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/generators/${slug}`, {
		method: 'POST',
		token,
		body: request
	});
}

export interface AzureServiceBusGeneratorPayload {
    resource_group_name: string;
    namespace_name: string;
    location: string;
    environment: string;
    sku: string;
    capacity?: number | null;
    zone_redundant: boolean;
    owner_tag: string;
    cost_center_tag: string;
    restrict_network: boolean;
    identity?: {
        type: string;
        user_assigned_identity_ids?: string[];
    };
    customer_managed_key?: {
        key_vault_key_id: string;
        user_assigned_identity_id?: string | null;
    } | null;
    private_endpoint?: {
        name: string;
        subnet_id: string;
        group_ids?: string[];
        private_dns_zone_ids?: string[];
    } | null;
    diagnostics?: {
        workspace_resource_id: string;
        log_categories?: string[];
        metric_categories?: string[];
    } | null;
    queues: Array<{
        name: string;
        enable_partitioning: boolean;
        lock_duration: string;
        max_delivery_count: number;
        requires_duplicate_detection: boolean;
        duplicate_detection_history_time_window: string;
    }>;
    topics: Array<{
        name: string;
        enable_partitioning: boolean;
        default_message_ttl: string;
        requires_duplicate_detection: boolean;
        duplicate_detection_history_time_window: string;
        subscriptions: Array<{
            name: string;
            requires_session: boolean;
            lock_duration: string;
            max_delivery_count: number;
            forward_to?: string | null;
        }>;
    }>;
    backend?: {
        resource_group: string;
        storage_account: string;
        container: string;
        key: string;
    } | null;
}

export async function generateAzureServiceBus(
    fetchFn: typeof fetch,
    payload: AzureServiceBusGeneratorPayload
): Promise<GeneratorResult> {
    return apiFetch(fetchFn, '/generators/azure/servicebus', {
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

export interface ListProjectsOptions {
	search?: string;
	includeMetadata?: boolean;
	limit?: number;
}

export async function listProjects(
	fetchFn: typeof fetch,
	token: string,
	options: ListProjectsOptions = {}
): Promise<ProjectSummary[]> {
	const searchParams: Record<string, string> = {};
	if (options.search) {
		searchParams.search = options.search;
	}
	if (typeof options.limit === 'number') {
		searchParams.limit = String(options.limit);
	}
	if (options.includeMetadata) {
		searchParams.include_metadata = 'true';
	}
	return apiFetch(fetchFn, '/projects', {
		token,
		searchParams: Object.keys(searchParams).length ? searchParams : undefined
	});
}

export async function createProject(
	fetchFn: typeof fetch,
	token: string,
	payload: ProjectCreatePayload
): Promise<ProjectDetail> {
	return apiFetch(fetchFn, '/projects', {
		method: 'POST',
		token,
		body: payload
	});
}

export async function updateProject(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	payload: ProjectUpdatePayload
): Promise<ProjectDetail> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}`, {
		method: 'PATCH',
		token,
		body: payload
	});
}

export async function getProject(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null
): Promise<ProjectDetail> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}`, {
		token
	});
}

export interface GetProjectOverviewOptions {
	recentAssets?: number;
	includeMetadata?: boolean;
}

export async function getProjectOverview(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	options: GetProjectOverviewOptions = {}
): Promise<ProjectOverview> {
	const identifier = resolveProjectIdentifier(projectId);
	const searchParams: Record<string, string> = {};
	if (typeof options.recentAssets === 'number') {
		searchParams.recent_assets = String(options.recentAssets);
	}
	if (options.includeMetadata === false) {
		searchParams.include_metadata = 'false';
	} else if (options.includeMetadata === true) {
		searchParams.include_metadata = 'true';
	}
	return apiFetch(fetchFn, `/projects/${identifier}/overview`, {
		token,
		searchParams: Object.keys(searchParams).length ? searchParams : undefined
	});
}

export async function deleteProject(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	removeFiles = false
): Promise<void> {
	const identifier = resolveProjectIdentifier(projectId);
	await apiFetch(fetchFn, `/projects/${identifier}`, {
		method: 'DELETE',
		token,
		searchParams: removeFiles ? { remove_files: 'true' } : undefined
	});
}

export interface ListProjectConfigsOptions {
	includePayload?: boolean;
}

export async function listProjectConfigs(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	options: ListProjectConfigsOptions = {}
): Promise<ProjectConfigRecord[]> {
	const identifier = resolveProjectIdentifier(projectId);
	const searchParams: Record<string, string> = {};
	if (options.includePayload) {
		searchParams.include_payload = 'true';
	}
	return apiFetch(fetchFn, `/projects/${identifier}/configs`, {
		token,
		searchParams: Object.keys(searchParams).length ? searchParams : undefined
	});
}

export async function createProjectConfig(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	payload: ProjectConfigCreatePayload
): Promise<ProjectConfigRecord> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/configs`, {
		method: 'POST',
		token,
		body: payload
	});
}

export async function updateProjectConfig(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	configId: string,
	payload: ProjectConfigUpdatePayload
): Promise<ProjectConfigRecord> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/configs/${configId}`, {
		method: 'PATCH',
		token,
		body: payload
	});
}

export async function deleteProjectConfig(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	configId: string
): Promise<void> {
	const identifier = resolveProjectIdentifier(projectId);
	await apiFetch(fetchFn, `/projects/${identifier}/configs/${configId}`, {
		method: 'DELETE',
		token
	});
}

export async function getProjectConfig(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	configId: string,
	options: { includePayload?: boolean } = {}
): Promise<ProjectConfigRecord> {
	const identifier = resolveProjectIdentifier(projectId);
	const searchParams: Record<string, string> = {};
	if (options.includePayload === false) {
		searchParams.include_payload = 'false';
	}
	return apiFetch(fetchFn, `/projects/${identifier}/configs/${configId}`, {
		token,
		searchParams: Object.keys(searchParams).length ? searchParams : undefined
	});
}

export interface ListProjectRunsOptions {
	limit?: number;
	cursor?: string;
}

interface ProjectRunListResponse {
	items: ProjectRunSummary[];
	next_cursor?: string | null;
	total_count?: number | null;
}

export async function listProjectRuns(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	options: ListProjectRunsOptions = {}
): Promise<PaginatedResult<ProjectRunSummary>> {
	const identifier = resolveProjectIdentifier(projectId);
	const searchParams: Record<string, string> = {};
	if (typeof options.limit === 'number') {
		searchParams.limit = String(options.limit);
	}
	if (options.cursor) {
		searchParams.cursor = options.cursor;
	}
	const response = await apiFetch<ProjectRunListResponse>(fetchFn, `/projects/${identifier}/runs`, {
		token,
		searchParams: Object.keys(searchParams).length ? searchParams : undefined
	});
	return {
		items: response.items,
		nextCursor: response.next_cursor ?? null,
		totalCount: response.total_count ?? response.items.length
	};
}

export async function createProjectRun(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	payload: ProjectRunCreatePayload
): Promise<ProjectRunSummary> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/runs`, {
		method: 'POST',
		token,
		body: payload
	});
}

export async function updateProjectRun(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	runId: string,
	payload: ProjectRunUpdatePayload
): Promise<ProjectRunSummary> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/runs/${runId}`, {
		method: 'PATCH',
		token,
		body: payload
	});
}

export async function listRunArtifacts(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	runId: string,
	path?: string
): Promise<ArtifactEntry[]> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/runs/${runId}/artifacts`, {
		token,
		searchParams: path ? { path } : undefined
	});
}

export async function uploadRunArtifact(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	runId: string,
	options: { path: string; file: File | Blob; filename?: string; overwrite?: boolean }
): Promise<ArtifactEntry> {
	const identifier = resolveProjectIdentifier(projectId);
	const formData = new FormData();
	formData.set('path', options.path);
	formData.set('overwrite', options.overwrite === false ? 'false' : 'true');
	const filename =
		options.filename ?? (typeof File !== 'undefined' && options.file instanceof File ? options.file.name : 'artifact');
	formData.set('file', options.file, filename);

	return apiFetch(fetchFn, `/projects/${identifier}/runs/${runId}/artifacts`, {
		method: 'POST',
		token,
		body: formData
	});
}

export async function deleteRunArtifact(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	runId: string,
	path: string
): Promise<void> {
	const identifier = resolveProjectIdentifier(projectId);
	await apiFetch(fetchFn, `/projects/${identifier}/runs/${runId}/artifacts`, {
		method: 'DELETE',
		token,
		searchParams: { path }
	});
}

export async function downloadRunArtifact(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	runId: string,
	path: string
): Promise<Response> {
	const identifier = resolveProjectIdentifier(projectId);
	const url = new URL(`/projects/${identifier}/runs/${runId}/artifacts/download`, API_BASE);
	url.searchParams.set('path', path);
	const response = await fetchFn(url.toString(), {
		method: 'GET',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});
	if (!response.ok) {
		const detail = await response.text();
		throw new ApiError(`Failed to download artifact (${response.status})`, response.status, detail);
	}
	return response;
}

export interface ListProjectArtifactsOptions {
	runId?: string;
	limit?: number;
	cursor?: string;
}

export async function listProjectArtifacts(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	options: ListProjectArtifactsOptions = {}
): Promise<ProjectArtifactListResponse> {
	const identifier = resolveProjectIdentifier(projectId);
	const searchParams: Record<string, string> = {};
	if (options.runId) {
		searchParams.run_id = options.runId;
	}
	if (typeof options.limit === 'number') {
		searchParams.limit = String(options.limit);
	}
	if (options.cursor) {
		searchParams.cursor = options.cursor;
	}
	const response = await apiFetch<{ items: ProjectArtifactRecord[]; next_cursor?: string | null; total_count: number }>(
		fetchFn,
		`/projects/${identifier}/artifacts`,
		{
			token,
			searchParams: Object.keys(searchParams).length ? searchParams : undefined
		}
	);
	return {
		items: response.items,
		nextCursor: response.next_cursor ?? null,
		totalCount: response.total_count
	};
}

export async function getProjectArtifact(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	artifactId: string
): Promise<ProjectArtifactRecord> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/artifacts/${artifactId}`, {
		token
	});
}

export async function updateProjectArtifact(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	artifactId: string,
	payload: ProjectArtifactUpdatePayload
): Promise<ProjectArtifactRecord> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/artifacts/${artifactId}`, {
		method: 'PATCH',
		token,
		body: payload
	});
}

export async function syncProjectRunArtifacts(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	runId: string,
	options: { pruneMissing?: boolean } = {}
): Promise<ProjectArtifactSyncResponse> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/runs/${runId}/artifacts/sync`, {
		method: 'POST',
		token,
		body: {
			prune_missing: options.pruneMissing !== false
		}
	});
}

export interface ListProjectLibraryOptions {
	includeVersions?: boolean;
	limit?: number;
	cursor?: string;
}

interface ProjectLibraryListResponse {
	items: GeneratedAssetSummary[];
	next_cursor?: string | null;
	total_count?: number | null;
}

export async function listProjectLibrary(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	options: ListProjectLibraryOptions = {}
): Promise<PaginatedResult<GeneratedAssetSummary>> {
	const identifier = resolveProjectIdentifier(projectId);
	const searchParams: Record<string, string> = {};
	if (options.includeVersions) {
		searchParams.include_versions = 'true';
	}
	if (typeof options.limit === 'number') {
		searchParams.limit = String(options.limit);
	}
	if (options.cursor) {
		searchParams.cursor = options.cursor;
	}
	const response = await apiFetch<ProjectLibraryListResponse>(fetchFn, `/projects/${identifier}/library`, {
		token,
		searchParams: Object.keys(searchParams).length ? searchParams : undefined
	});
	return {
		items: response.items,
		nextCursor: response.next_cursor ?? null,
		totalCount: response.total_count ?? response.items.length
	};
}

export async function getProjectLibraryAsset(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	assetId: string,
	includeVersions = true
): Promise<GeneratedAssetSummary> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/library/${assetId}`, {
		token,
		searchParams: includeVersions ? { include_versions: 'true' } : undefined
	});
}

export async function registerProjectLibraryAsset(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	payload: GeneratedAssetCreatePayload
): Promise<GeneratedAssetRegisterResponse> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/library`, {
		method: 'POST',
		token,
		body: payload
	});
}

export async function addProjectLibraryAssetVersion(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	assetId: string,
	payload: GeneratedAssetVersionCreatePayload
): Promise<GeneratedAssetRegisterResponse> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/library/${assetId}/versions`, {
		method: 'POST',
		token,
		body: payload
	});
}

export async function updateProjectLibraryAsset(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	assetId: string,
	payload: GeneratedAssetUpdatePayload
): Promise<GeneratedAssetSummary> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/library/${assetId}`, {
		method: 'PATCH',
		token,
		body: payload
	});
}

export async function deleteProjectLibraryAssetVersion(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	assetId: string,
	versionId: string,
	removeFiles = true
): Promise<void> {
	const identifier = resolveProjectIdentifier(projectId);
	await apiFetch(fetchFn, `/projects/${identifier}/library/${assetId}/versions/${versionId}`, {
		method: 'DELETE',
		token,
		searchParams: removeFiles ? { remove_files: 'true' } : undefined
	});
}

export async function deleteProjectLibraryAsset(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	assetId: string,
	removeFiles = false
): Promise<void> {
	const identifier = resolveProjectIdentifier(projectId);
	await apiFetch(fetchFn, `/projects/${identifier}/library/${assetId}`, {
		method: 'DELETE',
		token,
		searchParams: removeFiles ? { remove_files: 'true' } : undefined
	});
}

export async function downloadProjectLibraryAssetVersion(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	assetId: string,
	versionId: string
): Promise<Response> {
	const identifier = resolveProjectIdentifier(projectId);
	const url = new URL(`/projects/${identifier}/library/${assetId}/versions/${versionId}/download`, API_BASE);
	const response = await fetchFn(url.toString(), {
		method: 'GET',
		headers: {
			Authorization: `Bearer ${token}`
		}
	});
	if (!response.ok) {
		const detail = await response.text();
		throw new ApiError(`Failed to download library asset version (${response.status})`, response.status, detail);
	}
	return response;
}

export async function diffProjectLibraryAssetVersions(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	assetId: string,
	versionId: string,
	againstVersionId: string,
	options?: { ignoreWhitespace?: boolean }
): Promise<GeneratedAssetDiffResponse> {
	const identifier = resolveProjectIdentifier(projectId);
	const searchParams: Record<string, string> = { against: againstVersionId };
	if (options?.ignoreWhitespace) {
		searchParams.ignore_whitespace = 'true';
	}
	return apiFetch(fetchFn, `/projects/${identifier}/library/${assetId}/versions/${versionId}/diff`, {
		token,
		searchParams
	});
}

export async function listProjectLibraryVersionFiles(
	fetchFn: typeof fetch,
	token: string,
	projectId: string | null,
	assetId: string,
	versionId: string
): Promise<GeneratedAssetVersionFile[]> {
	const identifier = resolveProjectIdentifier(projectId);
	return apiFetch(fetchFn, `/projects/${identifier}/library/${assetId}/versions/${versionId}/files`, {
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
