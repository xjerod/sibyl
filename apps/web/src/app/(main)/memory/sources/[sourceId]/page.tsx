'use client';

import { use } from 'react';
import { Breadcrumb } from '@/components/layout/breadcrumb';
import { PageHeader } from '@/components/layout/page-header';
import { SourceInspectPanel } from '@/components/memory/source-inspect-panel';

interface PageProps {
  params: Promise<{ sourceId: string }>;
}

export default function MemorySourcePage({ params }: PageProps) {
  const { sourceId } = use(params);
  const decodedSourceId = decodeURIComponent(sourceId);

  return (
    <div className="space-y-4 animate-fade-in">
      <Breadcrumb
        items={[
          { label: 'Home', href: '/' },
          { label: 'Memory', href: '/memory' },
          { label: decodedSourceId },
        ]}
      />
      <PageHeader
        title="Source Inspect"
        description="Source metadata, visibility, derived records, audit receipts, and lifecycle actions"
      />
      <SourceInspectPanel sourceId={decodedSourceId} />
    </div>
  );
}
