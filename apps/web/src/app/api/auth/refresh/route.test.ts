import { NextRequest } from 'next/server';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { POST } from './route';

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
});
