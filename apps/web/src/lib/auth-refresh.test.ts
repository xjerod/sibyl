import { describe, expect, it } from 'vitest';
import { safeRelativePath } from './auth-refresh';

describe('auth refresh helpers', () => {
  it('keeps redirect targets same-origin relative', () => {
    expect(safeRelativePath('/projects?view=active')).toBe('/projects?view=active');
    expect(safeRelativePath('https://evil.example')).toBe('/');
    expect(safeRelativePath('//evil.example/path')).toBe('/');
    expect(safeRelativePath(null, '/fallback')).toBe('/fallback');
  });
});
