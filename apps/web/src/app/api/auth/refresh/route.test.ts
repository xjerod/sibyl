import { NextRequest } from 'next/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GET, POST } from './route';

describe('web auth refresh route', () => {
  beforeEach(() => {
    vi.stubEnv('SIBYL_API_URL', 'http://api.test/api');
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it('proxies POST refresh calls and preserves auth cookies', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => {
      const headers = new Headers({ 'content-type': 'application/json' });
      headers.append('set-cookie', 'sibyl_access_token=fresh; Path=/; HttpOnly');
      return new Response(JSON.stringify({ access_token: 'fresh' }), {
        status: 200,
        headers,
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const request = new NextRequest('http://web.test/api/auth/refresh', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        cookie: 'sibyl_refresh_token=refresh',
      },
    });

    const response = await POST(request);

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/auth/refresh',
      expect.objectContaining({
        method: 'POST',
        cache: 'no-store',
        redirect: 'manual',
        headers: expect.any(Headers),
      })
    );
    const forwarded = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((forwarded.headers as Headers).get('cookie')).toBe('sibyl_refresh_token=refresh');
    expect(response.status).toBe(200);
    expect(response.headers.get('set-cookie')).toContain('sibyl_access_token=fresh');
  });

  it('refreshes during a page redirect before returning to the page', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => {
      const headers = new Headers();
      headers.append('set-cookie', 'sibyl_access_token=fresh; Path=/; HttpOnly');
      return new Response('{}', { status: 200, headers });
    });
    vi.stubGlobal('fetch', fetchMock);

    const request = new NextRequest('http://web.test/api/auth/refresh?next=/projects');
    const response = await GET(request);

    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe('http://web.test/projects');
    expect(response.headers.get('set-cookie')).toContain('sibyl_access_token=fresh');
  });

  it('sends failed page refreshes back to login', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>(async () => new Response('nope', { status: 401 }))
    );

    const request = new NextRequest('http://web.test/api/auth/refresh?next=/entities');
    const response = await GET(request);

    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe(
      'http://web.test/login?next=%2Fentities&error=session_expired'
    );
  });
});
