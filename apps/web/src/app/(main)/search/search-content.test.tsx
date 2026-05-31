import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@/test/utils';
import { SearchContent } from './search-content';

const hooks = vi.hoisted(() => ({
  useSearch: vi.fn(() => ({ data: undefined, isLoading: false, error: null })),
}));

vi.mock('@/lib/hooks', () => ({
  useCodeExamples: () => ({ data: undefined, isLoading: false, error: null }),
  useRAGHybridSearch: () => ({ data: undefined, isLoading: false, error: null }),
  useSearch: hooks.useSearch,
  useSources: () => ({ data: { entities: [] } }),
  useStats: () => ({
    data: {
      entity_counts: {
        pattern: 3,
        procedure: 2,
        rule: 1,
        template: 1,
        task: 4,
        episode: 5,
        topic: 1,
      },
    },
  }),
}));

describe('SearchContent', () => {
  beforeEach(() => {
    hooks.useSearch.mockClear();
  });

  it('keeps document search out of knowledge type filters', () => {
    render(<SearchContent initialQuery="" />);

    expect(screen.getByRole('tab', { name: /docs/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /document/i })).not.toBeInTheDocument();
  });

  it('uses unified search for all mode', () => {
    render(<SearchContent initialQuery="surreal" />);

    expect(hooks.useSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        query: 'surreal',
        include_documents: true,
        include_graph: true,
        include_raw_memory: true,
        memory_scope: 'private',
      }),
      expect.objectContaining({ enabled: true })
    );
  });

  it('renders memory facets in all mode', () => {
    render(<SearchContent initialQuery="" />);

    expect(screen.getByLabelText(/source id/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/people/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/labels/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/occurred after/i)).toBeInTheDocument();
  });

  it('prepares raw-memory-only search for memory mode', () => {
    render(<SearchContent initialQuery="surreal" />);

    expect(hooks.useSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        query: 'surreal',
        types: ['raw_memory'],
        include_documents: false,
        include_graph: false,
        include_raw_memory: true,
      }),
      expect.objectContaining({ enabled: false })
    );
  });

  it('uses graph-only search for knowledge mode', () => {
    render(<SearchContent initialQuery="surreal" />);

    expect(hooks.useSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        query: 'surreal',
        include_documents: false,
        include_graph: true,
      }),
      expect.any(Object)
    );
  });
});
