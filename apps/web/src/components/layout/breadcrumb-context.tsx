'use client';

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { IconComponent } from '@/components/ui/icons';

export interface BreadcrumbItem {
  label: string;
  href?: string;
  icon?: IconComponent;
}

interface BreadcrumbContextValue {
  override: BreadcrumbItem[] | null;
  setOverride: (items: BreadcrumbItem[] | null) => void;
}

const BreadcrumbContext = createContext<BreadcrumbContextValue | null>(null);

export function BreadcrumbProvider({ children }: { children: ReactNode }) {
  const [override, setOverride] = useState<BreadcrumbItem[] | null>(null);
  const value = useMemo(() => ({ override, setOverride }), [override]);
  return <BreadcrumbContext.Provider value={value}>{children}</BreadcrumbContext.Provider>;
}

export function useBreadcrumbOverride(): BreadcrumbItem[] | null {
  return useContext(BreadcrumbContext)?.override ?? null;
}

/**
 * Push custom breadcrumb items from a page. Clears automatically on unmount,
 * so the breadcrumb falls back to the pathname-derived trail.
 *
 * Pages call this in render — items are reconciled in an effect so the
 * persistent breadcrumb in the layout smoothly morphs to the new trail
 * instead of being torn down and re-mounted on every navigation.
 */
export function useSetBreadcrumb(items: BreadcrumbItem[] | null | undefined) {
  const ctx = useContext(BreadcrumbContext);
  const setOverride = ctx?.setOverride;
  const previous = useRef<{ key: string; items: BreadcrumbItem[] | null }>({
    key: '',
    items: null,
  });

  const key =
    items
      ?.map(item => {
        const iconName = item.icon?.displayName ?? item.icon?.name ?? '';
        return `${item.label}\u001f${item.href ?? ''}\u001f${iconName}`;
      })
      .join('\u001e') ?? '';

  // Stabilize the item list so identical-but-different references don't
  // thrash the override on every render.
  if (previous.current.key !== key) {
    previous.current = {
      key,
      items: items && items.length > 0 ? items : null,
    };
  }
  const stable = previous.current.items;

  useEffect(() => {
    if (!setOverride) return;
    setOverride(stable);
    return () => setOverride(null);
  }, [stable, setOverride]);
}

export function useClearBreadcrumb() {
  const ctx = useContext(BreadcrumbContext);
  const setOverride = ctx?.setOverride;
  return useCallback(() => setOverride?.(null), [setOverride]);
}
