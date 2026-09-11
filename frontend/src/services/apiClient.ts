/**
 * The single place that knows the backend exists.
 *
 * Components never call `fetch` and never see a URL: they call the functions in
 * `services/voices.ts` and `services/speech.ts`, which go through here. That is
 * what keeps `NEXT_PUBLIC_API_URL` out of the component tree and makes the whole
 * data layer trivial to mock in tests.
 */

import type { ApiErrorBody } from '@/types';

const DEFAULT_BASE_URL = 'http://localhost:8000';

export function apiBaseUrl(): string {
  return (process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_BASE_URL).replace(/\/+$/, '');
}

/** Turn a relative path from the API (e.g. `/api/v1/...`) into an absolute URL. */
export function absoluteUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${apiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** True for failures the user can fix by changing their input. */
  get isUserFixable(): boolean {
    return this.status >= 400 && this.status < 500;
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  let code = 'http_error';
  let message = `Request failed with status ${response.status}.`;
  let details: Record<string, unknown> | undefined;

  try {
    const body = (await response.json()) as Partial<ApiErrorBody>;
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      details = body.error.details;
    }
  } catch {
    // Non-JSON error body (a proxy 502, say). Keep the generic message.
  }

  if (response.status === 429) {
    const retryAfter = response.headers.get('retry-after');
    if (retryAfter) message = `${message} (retry in ${retryAfter}s)`;
  }
  return new ApiError(response.status, code, message, details);
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: BodyInit | null;
  /** Abort the request after this many ms. Generation gets a longer budget. */
  timeoutMs?: number;
}

async function request(path: string, options: RequestOptions = {}): Promise<Response> {
  const { timeoutMs = 30_000, signal, ...init } = options;

  // Chain the caller's signal with our timeout so either can abort.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(new Error('timeout')), timeoutMs);
  signal?.addEventListener('abort', () => controller.abort(signal.reason), { once: true });

  try {
    const response = await fetch(absoluteUrl(path), { ...init, signal: controller.signal });
    if (!response.ok) throw await toApiError(response);
    return response;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(0, 'timeout', 'The request took too long. Please try again.');
    }
    throw new ApiError(
      0,
      'network_error',
      'Could not reach the server. Check that the backend is running.',
    );
  } finally {
    clearTimeout(timer);
  }
}

export async function getJson<T>(path: string, options?: RequestOptions): Promise<T> {
  const response = await request(path, { ...options, method: 'GET' });
  return (await response.json()) as T;
}

export async function postJson<T>(
  path: string,
  payload: unknown,
  options?: RequestOptions,
): Promise<T> {
  const response = await request(path, {
    ...options,
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    body: JSON.stringify(payload),
  });
  return (await response.json()) as T;
}

export async function postForm<T>(
  path: string,
  form: FormData,
  options?: RequestOptions,
): Promise<T> {
  // No Content-Type header: the browser must set the multipart boundary itself.
  const response = await request(path, { ...options, method: 'POST', body: form });
  return (await response.json()) as T;
}

export async function del<T>(path: string, options?: RequestOptions): Promise<T> {
  const response = await request(path, { ...options, method: 'DELETE' });
  return (await response.json()) as T;
}
