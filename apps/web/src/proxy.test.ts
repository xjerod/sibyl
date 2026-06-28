import { NextRequest } from 'next/server';
import { describe, expect, it } from 'vitest';
import { proxy } from './proxy';

describe('proxy auth refresh', () => {
  it('allows protected page loads when only the refresh cookie is usable', () => {
    const request = new NextRequest('http://web.test/projects?view=active', {
      headers: {
        cookie: 'sibyl_refresh_token=refresh',
      },
    });

    const response = proxy(request);

    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });

  it('redirects protected page loads without auth cookies to login', () => {
    const request = new NextRequest('http://web.test/projects?view=active');

    const response = proxy(request);

    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe(
      'http://web.test/login?next=%2Fprojects%3Fview%3Dactive'
    );
  });

  it('does not refresh public login traffic', () => {
    const request = new NextRequest('http://web.test/login', {
      headers: { cookie: 'sibyl_refresh_token=refresh' },
    });

    const response = proxy(request);

    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });

  it('allows password reset links without auth cookies', () => {
    const request = new NextRequest('http://web.test/reset-password?token=reset-token');

    const response = proxy(request);

    expect(response.status).toBe(200);
    expect(response.headers.get('location')).toBeNull();
  });
});
