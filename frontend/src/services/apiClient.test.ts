import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, absoluteUrl, getJson, postForm, postJson } from '@/services/apiClient';

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

describe('absoluteUrl', () => {
  it('prefixes a relative path with the configured base', () => {
    expect(absoluteUrl('/api/v1/voices')).toBe('http://api.test/api/v1/voices');
  });

  it('leaves an absolute URL alone', () => {
    expect(absoluteUrl('https://cdn.example/x.wav')).toBe('https://cdn.example/x.wav');
  });
});

describe('request handling', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
  });

  afterEach(() => vi.unstubAllGlobals());

  it('returns the parsed body on success', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: 'voice_1' }));
    await expect(getJson('/api/v1/voices/x')).resolves.toEqual({ id: 'voice_1' });
  });

  it('sends JSON with the right content type', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await postJson('/api/v1/speech', { text: 'hi' });

    const [, init] = fetchMock.mock.calls[0]!;
    expect(init.method).toBe('POST');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.body).toBe('{"text":"hi"}');
  });

  it('does not set a content type for multipart, so the boundary is generated', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ ok: true }));
    await postForm('/api/v1/voices', new FormData());

    const [, init] = fetchMock.mock.calls[0]!;
    expect(init.headers).toBeUndefined();
  });

  it('unwraps the backend error envelope', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        { error: { code: 'consent_required', message: 'You must confirm consent.' } },
        { status: 403 },
      ),
    );

    const error = await getJson('/api/v1/voices').catch((cause: unknown) => cause);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe('consent_required');
    expect((error as ApiError).status).toBe(403);
    expect((error as ApiError).isUserFixable).toBe(true);
  });

  it('mentions the retry delay on a 429', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'rate_limited', message: 'Too many.' } }), {
        status: 429,
        headers: { 'Content-Type': 'application/json', 'Retry-After': '42' },
      }),
    );

    const error = (await getJson('/x').catch((cause) => cause)) as ApiError;
    expect(error.message).toContain('42');
  });

  it('survives a non-JSON error body', async () => {
    fetchMock.mockResolvedValue(new Response('<html>502</html>', { status: 502 }));
    const error = (await getJson('/x').catch((cause) => cause)) as ApiError;
    expect(error.status).toBe(502);
    expect(error.isUserFixable).toBe(false);
  });

  it('reports a network failure in plain language', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    const error = (await getJson('/x').catch((cause) => cause)) as ApiError;
    expect(error.code).toBe('network_error');
    expect(error.message).toMatch(/backend is running/i);
  });
});
