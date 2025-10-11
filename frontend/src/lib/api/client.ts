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
