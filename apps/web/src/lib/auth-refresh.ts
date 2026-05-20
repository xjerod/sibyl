export const ACCESS_TOKEN_COOKIE = 'sibyl_access_token';
export const REFRESH_TOKEN_COOKIE = 'sibyl_refresh_token';

const REFRESH_SKEW_MS = 30_000;

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const [, payload] = token.split('.');
  if (!payload) return null;

  try {
    const normalized = payload.replaceAll('-', '+').replaceAll('_', '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    const decoded = atob(padded);
    const bytes = Uint8Array.from(decoded, char => char.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function isAccessTokenExpired(accessToken: string | undefined, nowMs = Date.now()): boolean {
  if (!accessToken) return true;

  const payload = decodeJwtPayload(accessToken);
  const rawExp = payload?.exp;
  const exp = typeof rawExp === 'number' ? rawExp : Number(rawExp);
  if (!Number.isFinite(exp)) return true;

  return exp * 1000 <= nowMs + REFRESH_SKEW_MS;
}

export function shouldRefreshAuthCookies({
  accessToken,
  refreshToken,
  nowMs = Date.now(),
}: {
  accessToken?: string;
  refreshToken?: string;
  nowMs?: number;
}): boolean {
  return Boolean(refreshToken) && isAccessTokenExpired(accessToken, nowMs);
}

export function safeRelativePath(value: string | null | undefined, fallback = '/'): string {
  if (!value?.startsWith('/') || value.startsWith('//')) {
    return fallback;
  }
  return value;
}
