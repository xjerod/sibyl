'use client';

import type { SynthesisVerification } from '@/lib/api';

const STATUS_STYLES: Record<SynthesisVerification['status'], string> = {
  pending: 'border-sc-fg-subtle/20 bg-sc-fg-subtle/10 text-sc-fg-muted',
  gaps: 'border-sc-yellow/30 bg-sc-yellow/10 text-sc-yellow',
  pass: 'border-sc-green/30 bg-sc-green/10 text-sc-green',
};

function titleCase(value: string): string {
  return value
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function SynthesisVerificationPanel({
  verification,
}: {
  verification: SynthesisVerification;
}) {
  return (
    <section className="rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-base p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-sc-fg-primary">Verification</h2>
        <span
          className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[verification.status]}`}
        >
          {titleCase(verification.status)}
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-highlight/40 p-3">
          <p className="text-xs uppercase tracking-[0.12em] text-sc-fg-subtle">Sources</p>
          <p className="mt-2 text-xl font-semibold text-sc-fg-primary">
            {verification.source_count}
          </p>
        </div>
        <div className="rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-highlight/40 p-3">
          <p className="text-xs uppercase tracking-[0.12em] text-sc-fg-subtle">Gaps</p>
          <p className="mt-2 text-xl font-semibold text-sc-fg-primary">{verification.gap_count}</p>
        </div>
      </div>

      {verification.gaps.length > 0 ? (
        <div className="mt-4 space-y-2">
          {verification.gaps.map(gap => (
            <article
              key={`${gap.section_id}-${gap.reason}-${gap.query}`}
              className="rounded-lg border border-sc-yellow/20 bg-sc-yellow/10 p-3"
            >
              <p className="text-sm font-medium text-sc-yellow">{gap.title}</p>
              <p className="mt-1 text-sm text-sc-fg-muted">{gap.reason}</p>
              <p className="mt-2 truncate font-mono text-xs text-sc-fg-subtle">{gap.query}</p>
            </article>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-sc-fg-muted">
          No verification gaps reported for this synthesis run.
        </p>
      )}
    </section>
  );
}
