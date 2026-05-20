import { describe, expect, it } from 'vitest';
import { isAccessTokenExpired, safeRelativePath, shouldRefreshAuthCookies } from './auth-refresh';

function tokenWithExp(exp: number): string {
  const payload = Buffer.from(JSON.stringify({ exp }), 'utf8').toString('base64url');
  return `header.${payload}.signature`;
}

describe('auth refresh helpers', () => {
  it('treats fresh access tokens as usable', () => {
    const now = Date.UTC(2026, 4, 20, 12, 0, 0);
    const token = tokenWithExp(Math.floor((now + 120_000) / 1000));

    expect(isAccessTokenExpired(token, now)).toBe(false);
    expect(
      shouldRefreshAuthCookies({
        accessToken: token,
        refreshToken: 'refresh-token',
        nowMs: now,
      })
    ).toBe(false);
  });

  it('refreshes missing, malformed, expired, or nearly expired access tokens', () => {
    const now = Date.UTC(2026, 4, 20, 12, 0, 0);
    const expired = tokenWithExp(Math.floor((now - 1_000) / 1000));
    const almostExpired = tokenWithExp(Math.floor((now + 10_000) / 1000));

    expect(shouldRefreshAuthCookies({ refreshToken: 'refresh-token', nowMs: now })).toBe(true);
    expect(
      shouldRefreshAuthCookies({
        accessToken: 'not-a-jwt',
        refreshToken: 'refresh-token',
        nowMs: now,
      })
    ).toBe(true);
    expect(
      shouldRefreshAuthCookies({
        accessToken: expired,
        refreshToken: 'refresh-token',
        nowMs: now,
      })
    ).toBe(true);
    expect(
      shouldRefreshAuthCookies({
        accessToken: almostExpired,
        refreshToken: 'refresh-token',
        nowMs: now,
      })
    ).toBe(true);
  });

  it('does not refresh when no refresh token exists', () => {
    expect(
      shouldRefreshAuthCookies({
        accessToken: 'not-a-jwt',
        nowMs: Date.UTC(2026, 4, 20, 12, 0, 0),
      })
    ).toBe(false);
  });

  it('keeps redirect targets same-origin relative', () => {
    expect(safeRelativePath('/projects?view=active')).toBe('/projects?view=active');
    expect(safeRelativePath('https://evil.example')).toBe('/');
    expect(safeRelativePath('//evil.example/path')).toBe('/');
    expect(safeRelativePath(null, '/fallback')).toBe('/fallback');
  });
});
