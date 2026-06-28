export const ACCESS_TOKEN_COOKIE = 'sibyl_access_token';
export const REFRESH_TOKEN_COOKIE = 'sibyl_refresh_token';

export function safeRelativePath(value: string | null | undefined, fallback = '/'): string {
  if (!value?.startsWith('/') || value.startsWith('//')) {
    return fallback;
  }
  return value;
}
