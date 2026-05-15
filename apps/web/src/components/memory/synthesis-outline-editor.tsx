'use client';

import { EntityBadge } from '@/components/ui/badge';
import { FormField } from '@/components/ui/form-field';
import { Input, Textarea } from '@/components/ui/input';
import type { SynthesisSectionRequest, SynthesisSourcePack } from '@/lib/api';

function sourceIdsToText(sourceIds: string[] | undefined): string {
  return (sourceIds ?? []).join(', ');
}

function textToSourceIds(value: string): string[] {
  return value
    .split(',')
    .map(part => part.trim())
    .filter(Boolean);
}

export function SynthesisOutlineEditor({
  sections,
  sourcePacks,
  onSectionsChange,
}: {
  sections: SynthesisSectionRequest[];
  sourcePacks: SynthesisSourcePack[];
  onSectionsChange: (sections: SynthesisSectionRequest[]) => void;
}) {
  function updateSection(index: number, patch: Partial<SynthesisSectionRequest>) {
    onSectionsChange(
      sections.map((section, i) => (i === index ? { ...section, ...patch } : section))
    );
  }

  return (
    <section className="space-y-3 rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-base p-4 shadow-card">
      <div>
        <h2 className="text-sm font-semibold text-sc-fg-primary">Outline Review</h2>
        <p className="mt-1 text-sm text-sc-fg-muted">
          Tune section prompts and required sources before drafting.
        </p>
      </div>

      {sections.length === 0 ? (
        <p className="rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-highlight/40 px-3 py-4 text-sm text-sc-fg-muted">
          Plan a synthesis run to review the outline.
        </p>
      ) : (
        <div className="space-y-3">
          {sections.map((section, index) => {
            const sourcePack = sourcePacks[index];
            const sourceCount =
              section.required_source_ids?.length ?? sourcePack?.source_ids.length ?? 0;

            return (
              <article
                key={`section-${index}`}
                className="space-y-3 rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-highlight/40 p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs uppercase tracking-[0.12em] text-sc-fg-subtle">
                    Section {index + 1}
                  </p>
                  <EntityBadge type={`${sourceCount} sources`} />
                </div>

                <FormField label="Title">
                  {field => (
                    <Input
                      {...field}
                      value={section.title}
                      onChange={event => updateSection(index, { title: event.target.value })}
                    />
                  )}
                </FormField>

                <FormField label="Prompt">
                  {field => (
                    <Textarea
                      {...field}
                      value={section.prompt ?? ''}
                      rows={3}
                      onChange={event => updateSection(index, { prompt: event.target.value })}
                    />
                  )}
                </FormField>

                <FormField label="Required Sources">
                  {field => (
                    <Input
                      {...field}
                      value={sourceIdsToText(section.required_source_ids)}
                      onChange={event =>
                        updateSection(index, {
                          required_source_ids: textToSourceIds(event.target.value),
                        })
                      }
                      placeholder="source ids separated by commas"
                    />
                  )}
                </FormField>

                {sourcePack && (
                  <div className="rounded-lg border border-sc-cyan/20 bg-sc-cyan/10 p-3">
                    <p className="text-xs font-medium uppercase tracking-[0.12em] text-sc-cyan">
                      Source Pack
                    </p>
                    <div className="mt-2 space-y-2">
                      {sourcePack.sources.slice(0, 4).map(source => (
                        <div
                          key={source.id}
                          className="rounded border border-sc-fg-subtle/20 bg-sc-bg-base/70 px-3 py-2"
                        >
                          <p className="truncate text-sm font-medium text-sc-fg-primary">
                            {source.name}
                          </p>
                          <p className="mt-1 line-clamp-2 text-xs text-sc-fg-muted">
                            {source.content_preview}
                          </p>
                        </div>
                      ))}
                    </div>
                    {(sourcePack.hidden_count > 0 || sourcePack.redaction_count > 0) && (
                      <p className="mt-2 text-xs text-sc-yellow">
                        {sourcePack.hidden_count} hidden · {sourcePack.redaction_count} redacted
                      </p>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
