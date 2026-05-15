'use client';

import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  Check,
  Database,
  Flash,
  Globe,
  InfoCircle,
  RefreshDouble,
  Settings as SettingsIcon,
  WarningTriangle,
} from '@/components/ui/icons';
import { Spinner } from '@/components/ui/spinner';
import { Tooltip } from '@/components/ui/tooltip';
import type {
  AIModelEntry,
  LLMConfigSource,
  LLMProviderName,
  LLMSurface,
  LLMSurfaceSettings,
  LLMTestResult,
  UpdateLLMSurfaceRequest,
} from '@/lib/api';
import {
  useLLMRegistry,
  useLLMSettings,
  useTestLLMSurface,
  useUpdateLLMSurface,
} from '@/lib/hooks';

const CUSTOM_MODEL = '__custom__';

const SURFACES: Array<{
  id: LLMSurface;
  label: string;
  description: string;
  useCase: string;
}> = [
  {
    id: 'default',
    label: 'Default',
    description: 'Fallback surface for shared LLM consumers.',
    useCase: 'default',
  },
  {
    id: 'crawler',
    label: 'Crawler',
    description: 'Structured entity extraction for crawled documents.',
    useCase: 'extraction',
  },
  {
    id: 'synthesis',
    label: 'Synthesis',
    description: 'Long-form generation and memory synthesis.',
    useCase: 'synthesis',
  },
];

const PROVIDERS: Array<{ value: LLMProviderName; label: string }> = [
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'openai', label: 'OpenAI' },
];

interface SurfaceDraft {
  provider: LLMProviderName;
  model: string;
  customModel: string;
  temperature: string;
  maxTokens: string;
  timeoutSeconds: string;
  advancedOpen: boolean;
  customConfirmed: boolean;
}

function providerLabel(provider: string) {
  return PROVIDERS.find(item => item.value === provider)?.label ?? provider;
}

function normalizeProvider(value: unknown): LLMProviderName {
  return value === 'gemini' || value === 'openai' || value === 'anthropic' ? value : 'anthropic';
}

function fieldText(value: string | number | null) {
  return value === null || value === undefined ? '' : String(value);
}

function modelsForProvider(entries: AIModelEntry[], provider: LLMProviderName) {
  return entries.filter(entry => entry.kind === 'llm' && entry.provider === provider);
}

function recommendedModel(
  entries: AIModelEntry[],
  provider: LLMProviderName,
  useCase: string
): AIModelEntry | undefined {
  const providerModels = modelsForProvider(entries, provider);
  return (
    providerModels.find(entry => entry.use_cases.includes(useCase)) ??
    providerModels.find(entry => entry.use_cases.includes('default')) ??
    providerModels[0]
  );
}

function isCuratedModel(entries: AIModelEntry[], provider: LLMProviderName, model: string) {
  return modelsForProvider(entries, provider).some(
    entry => entry.alias === model || entry.snapshot === model || entry.provider_model_id === model
  );
}

function createDraft(surface: LLMSurfaceSettings, entries: AIModelEntry[]): SurfaceDraft {
  const provider = normalizeProvider(surface.provider.value);
  const model = fieldText(surface.model.value);
  const custom = model ? !isCuratedModel(entries, provider, model) : false;
  return {
    provider,
    model,
    customModel: custom ? model : '',
    temperature: fieldText(surface.temperature.value),
    maxTokens: fieldText(surface.max_tokens.value),
    timeoutSeconds: fieldText(surface.timeout_seconds.value),
    advancedOpen: custom,
    customConfirmed: false,
  };
}

function sourceLabel(source: LLMConfigSource) {
  if (source === 'env') return 'env';
  if (source === 'db') return 'db';
  return 'default';
}

function SourceBadge({
  source,
  locked,
  envVar,
}: {
  source: LLMConfigSource;
  locked?: boolean;
  envVar?: string | null;
}) {
  const Icon = source === 'env' ? Globe : source === 'db' ? Database : InfoCircle;
  const content = locked && envVar ? `Locked by ${envVar}` : sourceLabel(source);

  return (
    <Tooltip content={content}>
      <span
        className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium ${
          source === 'env'
            ? 'border-sc-purple/30 bg-sc-purple/10 text-sc-purple'
            : source === 'db'
              ? 'border-sc-cyan/30 bg-sc-cyan/10 text-sc-cyan'
              : 'border-sc-fg-subtle/20 bg-sc-bg-highlight text-sc-fg-muted'
        }`}
      >
        <Icon width={11} height={11} />
        {sourceLabel(source)}
      </span>
    </Tooltip>
  );
}

function FieldLabel({
  children,
  source,
  locked,
  envVar,
}: {
  children: string;
  source: LLMConfigSource;
  locked?: boolean;
  envVar?: string | null;
}) {
  return (
    <span className="mb-1.5 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.08em] text-sc-fg-subtle">
      {children}
      <SourceBadge source={source} locked={locked} envVar={envVar} />
    </span>
  );
}

function lockedTitle(field: { locked_by_env: boolean; env_var: string | null }) {
  return field.locked_by_env && field.env_var ? `${field.env_var} controls this field` : undefined;
}

function parseEnvLockedError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  try {
    const payload = JSON.parse(message) as {
      detail?: { code?: string; fields?: Array<{ field?: string; env_var?: string | null }> };
    };
    if (payload.detail?.code === 'LOCKED_BY_ENV') {
      const fields = payload.detail.fields ?? [];
      const names = fields
        .map(field => (field.env_var ? `${field.field} (${field.env_var})` : field.field))
        .filter(Boolean)
        .join(', ');
      return names
        ? `These fields are controlled by environment variables: ${names}.`
        : "This field is set by an environment variable and can't be changed here.";
    }
  } catch {
    return message;
  }
  return message;
}

function formatTokens(result: LLMTestResult) {
  const input = result.input_tokens ?? 0;
  const output = result.output_tokens ?? 0;
  return input || output ? `${input} in / ${output} out` : 'tokens unavailable';
}

function buildRequest(draft: SurfaceDraft): UpdateLLMSurfaceRequest {
  const model =
    draft.model === CUSTOM_MODEL || draft.customModel.trim()
      ? draft.customModel.trim()
      : draft.model.trim();
  const request: UpdateLLMSurfaceRequest = {
    provider: draft.provider,
    model,
    temperature: Number(draft.temperature),
    timeout_seconds: Number(draft.timeoutSeconds),
  };
  const maxTokens = draft.maxTokens.trim();
  if (maxTokens) {
    request.max_tokens = Number(maxTokens);
  }
  return request;
}

function validateDraft(draft: SurfaceDraft) {
  const needsCustomModel = draft.model === CUSTOM_MODEL || draft.advancedOpen;
  if (needsCustomModel && !draft.customModel.trim()) {
    return 'Enter a custom model before saving.';
  }
  if (!needsCustomModel && !draft.model.trim()) {
    return 'Choose a model before saving.';
  }
  if (needsCustomModel && draft.customModel.trim() && !draft.customConfirmed) {
    return 'Confirm the custom model before saving.';
  }
  if (!Number.isFinite(Number(draft.temperature))) {
    return 'Temperature must be a number.';
  }
  if (!Number.isFinite(Number(draft.timeoutSeconds))) {
    return 'Timeout must be a number.';
  }
  if (draft.maxTokens.trim() && !Number.isInteger(Number(draft.maxTokens))) {
    return 'Max tokens must be a whole number.';
  }
  return null;
}

export function LLMConfigCard() {
  const { data: settings, isLoading } = useLLMSettings();
  const { data: registry } = useLLMRegistry('llm');
  const updateSurface = useUpdateLLMSurface();
  const testSurface = useTestLLMSurface();

  const entries = useMemo(() => registry?.entries ?? [], [registry]);
  const [drafts, setDrafts] = useState<Partial<Record<LLMSurface, SurfaceDraft>>>({});
  const [saveErrors, setSaveErrors] = useState<Partial<Record<LLMSurface, string>>>({});
  const [testResults, setTestResults] = useState<Partial<Record<LLMSurface, LLMTestResult>>>({});
  const [savingSurface, setSavingSurface] = useState<LLMSurface | null>(null);
  const [testingSurface, setTestingSurface] = useState<LLMSurface | null>(null);

  useEffect(() => {
    if (!settings) return;
    setDrafts(
      Object.fromEntries(
        SURFACES.map(surface => [surface.id, createDraft(settings.surfaces[surface.id], entries)])
      ) as Record<LLMSurface, SurfaceDraft>
    );
  }, [settings, entries]);

  const updateDraft = (surface: LLMSurface, patch: Partial<SurfaceDraft>) => {
    setDrafts(current => ({
      ...current,
      [surface]: {
        ...(current[surface] as SurfaceDraft),
        ...patch,
      },
    }));
    setSaveErrors(current => ({ ...current, [surface]: undefined }));
  };

  const handleProviderChange = (
    surface: LLMSurface,
    provider: LLMProviderName,
    useCase: string
  ) => {
    const recommended = recommendedModel(entries, provider, useCase);
    updateDraft(surface, {
      provider,
      model: recommended?.alias ?? '',
      customModel: '',
      advancedOpen: false,
      customConfirmed: false,
    });
  };

  const handleSave = async (surface: LLMSurface) => {
    const draft = drafts[surface];
    if (!draft) return;

    const validationError = validateDraft(draft);
    if (validationError) {
      setSaveErrors(current => ({ ...current, [surface]: validationError }));
      return;
    }

    setSavingSurface(surface);
    try {
      const response = await updateSurface.mutateAsync({
        surface,
        request: buildRequest(draft),
      });
      toast.success(`${SURFACES.find(item => item.id === surface)?.label ?? surface} LLM saved`);
      if (response.warning === 'unverified_model') {
        toast.warning('Saved with an unverified model');
      }
    } catch (error) {
      setSaveErrors(current => ({ ...current, [surface]: parseEnvLockedError(error) }));
    } finally {
      setSavingSurface(null);
    }
  };

  const handleTest = async (surface: LLMSurface) => {
    setTestingSurface(surface);
    try {
      const result = await testSurface.mutateAsync(surface);
      setTestResults(current => ({ ...current, [surface]: result }));
      if (result.valid) {
        toast.success(`${surface} surface is ready`);
      } else {
        toast.error(result.error || `${surface} surface test failed`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Surface test failed');
    } finally {
      setTestingSurface(null);
    }
  };

  if (isLoading || !settings) {
    return (
      <section className="rounded-lg border border-sc-fg-subtle/10 bg-sc-bg-base p-6">
        <div className="flex items-center justify-center py-8">
          <Spinner size="md" color="purple" />
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-sc-fg-subtle/10 bg-sc-bg-base p-6">
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-3">
          <SettingsIcon width={20} height={20} className="mt-0.5 text-sc-purple" />
          <div>
            <h3 className="font-semibold text-sc-fg-primary">Language Models</h3>
            <p className="mt-1 text-sm text-sc-fg-muted">
              Instance-wide model routing for extraction, defaults, and synthesis.
            </p>
          </div>
        </div>
        <div className="rounded-lg border border-sc-yellow/20 bg-sc-yellow/10 px-3 py-2 text-sm text-sc-fg-secondary">
          These settings apply to every organization in this deployment.
        </div>
      </div>

      <div className="grid gap-4">
        {SURFACES.map(surfaceInfo => {
          const surface = settings.surfaces[surfaceInfo.id];
          const draft = drafts[surfaceInfo.id] ?? createDraft(surface, entries);
          const providerModels = modelsForProvider(entries, draft.provider);
          const recommended = recommendedModel(entries, draft.provider, surfaceInfo.useCase);
          const modelIsCustom =
            !!draft.model && !isCuratedModel(entries, draft.provider, draft.model);
          const selectedModel = modelIsCustom ? CUSTOM_MODEL : draft.model;
          const result = testResults[surfaceInfo.id];

          return (
            <div
              key={surfaceInfo.id}
              className="rounded-lg border border-sc-fg-subtle/10 bg-sc-bg-dark/40 p-4"
            >
              <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="font-medium text-sc-fg-primary">{surfaceInfo.label}</h4>
                    {surface.api_key.configured ? (
                      <span className="inline-flex items-center gap-1 rounded border border-sc-green/30 bg-sc-green/10 px-2 py-0.5 text-xs text-sc-green">
                        <Check width={12} height={12} />
                        Key ready
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded border border-sc-red/30 bg-sc-red/10 px-2 py-0.5 text-xs text-sc-red">
                        <WarningTriangle width={12} height={12} />
                        Missing key
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm text-sc-fg-muted">{surfaceInfo.description}</p>
                </div>
                <button
                  type="button"
                  onClick={() => handleTest(surfaceInfo.id)}
                  disabled={testingSurface === surfaceInfo.id}
                  aria-label={`Test ${surfaceInfo.label}`}
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-highlight px-3 py-2 text-sm font-medium text-sc-fg-secondary transition-colors hover:bg-sc-bg-base disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {testingSurface === surfaceInfo.id ? (
                    <Spinner size="sm" color="current" />
                  ) : (
                    <RefreshDouble width={14} height={14} />
                  )}
                  Test
                </button>
              </div>

              <div className="grid gap-4 lg:grid-cols-[160px_minmax(220px,1fr)_120px_130px_130px]">
                <label className="block" title={lockedTitle(surface.provider)}>
                  <FieldLabel
                    source={surface.provider.source}
                    locked={surface.provider.locked_by_env}
                    envVar={surface.provider.env_var}
                  >
                    Provider
                  </FieldLabel>
                  <select
                    value={draft.provider}
                    onChange={event =>
                      handleProviderChange(
                        surfaceInfo.id,
                        event.target.value as LLMProviderName,
                        surfaceInfo.useCase
                      )
                    }
                    disabled={surface.provider.locked_by_env}
                    className="w-full rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-base px-3 py-2.5 text-sm text-sc-fg-primary focus:border-sc-cyan/50 focus:outline-none focus:ring-1 focus:ring-sc-cyan/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {PROVIDERS.map(provider => (
                      <option key={provider.value} value={provider.value}>
                        {provider.label}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block" title={lockedTitle(surface.model)}>
                  <FieldLabel
                    source={surface.model.source}
                    locked={surface.model.locked_by_env}
                    envVar={surface.model.env_var}
                  >
                    Model
                  </FieldLabel>
                  <select
                    value={selectedModel}
                    onChange={event => {
                      if (event.target.value === CUSTOM_MODEL) {
                        updateDraft(surfaceInfo.id, {
                          model: CUSTOM_MODEL,
                          customModel: modelIsCustom ? draft.customModel || draft.model : '',
                          advancedOpen: true,
                          customConfirmed: false,
                        });
                        return;
                      }
                      updateDraft(surfaceInfo.id, {
                        model: event.target.value,
                        customModel: '',
                        advancedOpen: false,
                        customConfirmed: false,
                      });
                    }}
                    disabled={surface.model.locked_by_env}
                    className="w-full rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-base px-3 py-2.5 text-sm text-sc-fg-primary focus:border-sc-cyan/50 focus:outline-none focus:ring-1 focus:ring-sc-cyan/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {providerModels.map(model => (
                      <option key={model.alias} value={model.alias}>
                        {model.alias}
                        {model.alias === recommended?.alias ? ' (recommended)' : ''}
                      </option>
                    ))}
                    <option value={CUSTOM_MODEL}>Custom model...</option>
                  </select>
                </label>

                <label className="block" title={lockedTitle(surface.temperature)}>
                  <FieldLabel
                    source={surface.temperature.source}
                    locked={surface.temperature.locked_by_env}
                    envVar={surface.temperature.env_var}
                  >
                    Temp
                  </FieldLabel>
                  <input
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    value={draft.temperature}
                    onChange={event =>
                      updateDraft(surfaceInfo.id, { temperature: event.target.value })
                    }
                    disabled={surface.temperature.locked_by_env}
                    className="w-full rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-base px-3 py-2.5 text-sm text-sc-fg-primary focus:border-sc-cyan/50 focus:outline-none focus:ring-1 focus:ring-sc-cyan/20 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </label>

                <label className="block" title={lockedTitle(surface.max_tokens)}>
                  <FieldLabel
                    source={surface.max_tokens.source}
                    locked={surface.max_tokens.locked_by_env}
                    envVar={surface.max_tokens.env_var}
                  >
                    Max Tokens
                  </FieldLabel>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={draft.maxTokens}
                    onChange={event =>
                      updateDraft(surfaceInfo.id, { maxTokens: event.target.value })
                    }
                    disabled={surface.max_tokens.locked_by_env}
                    placeholder="default"
                    className="w-full rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-base px-3 py-2.5 text-sm text-sc-fg-primary placeholder:text-sc-fg-subtle focus:border-sc-cyan/50 focus:outline-none focus:ring-1 focus:ring-sc-cyan/20 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </label>

                <label className="block" title={lockedTitle(surface.timeout_seconds)}>
                  <FieldLabel
                    source={surface.timeout_seconds.source}
                    locked={surface.timeout_seconds.locked_by_env}
                    envVar={surface.timeout_seconds.env_var}
                  >
                    Timeout
                  </FieldLabel>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={draft.timeoutSeconds}
                    onChange={event =>
                      updateDraft(surfaceInfo.id, { timeoutSeconds: event.target.value })
                    }
                    disabled={surface.timeout_seconds.locked_by_env}
                    className="w-full rounded-lg border border-sc-fg-subtle/20 bg-sc-bg-base px-3 py-2.5 text-sm text-sc-fg-primary focus:border-sc-cyan/50 focus:outline-none focus:ring-1 focus:ring-sc-cyan/20 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </label>
              </div>

              <div className="mt-4 flex flex-col gap-3 border-t border-sc-fg-subtle/10 pt-4">
                <button
                  type="button"
                  onClick={() => updateDraft(surfaceInfo.id, { advancedOpen: !draft.advancedOpen })}
                  className="inline-flex w-fit items-center gap-2 text-sm font-medium text-sc-cyan transition-colors hover:text-sc-purple"
                >
                  <Flash width={14} height={14} />
                  Advanced
                </button>

                {draft.advancedOpen && (
                  <div className="grid gap-3 rounded-lg border border-sc-yellow/20 bg-sc-yellow/10 p-3 md:grid-cols-[1fr_auto] md:items-end">
                    <label className="block">
                      <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.08em] text-sc-fg-subtle">
                        Custom Model
                      </span>
                      <input
                        type="text"
                        value={draft.customModel}
                        onChange={event =>
                          updateDraft(surfaceInfo.id, {
                            customModel: event.target.value,
                            model: CUSTOM_MODEL,
                            customConfirmed: false,
                          })
                        }
                        placeholder={`${providerLabel(draft.provider)} model id`}
                        className="w-full rounded-lg border border-sc-yellow/30 bg-sc-bg-base px-3 py-2.5 text-sm text-sc-fg-primary placeholder:text-sc-fg-subtle focus:border-sc-yellow/60 focus:outline-none focus:ring-1 focus:ring-sc-yellow/20"
                      />
                    </label>
                    <label className="flex items-center gap-2 rounded-lg border border-sc-yellow/20 bg-sc-bg-base px-3 py-2.5 text-sm text-sc-fg-secondary">
                      <input
                        type="checkbox"
                        checked={draft.customConfirmed}
                        onChange={event =>
                          updateDraft(surfaceInfo.id, { customConfirmed: event.target.checked })
                        }
                        className="h-4 w-4 accent-sc-yellow"
                      />
                      I understand this model is unverified
                    </label>
                  </div>
                )}

                {saveErrors[surfaceInfo.id] && (
                  <div className="rounded-lg border border-sc-red/20 bg-sc-red/10 p-3 text-sm text-sc-red">
                    {saveErrors[surfaceInfo.id]}
                  </div>
                )}

                {result && (
                  <div
                    className={`rounded-lg border p-3 text-sm ${
                      result.valid
                        ? 'border-sc-green/20 bg-sc-green/10 text-sc-fg-secondary'
                        : 'border-sc-red/20 bg-sc-red/10 text-sc-red'
                    }`}
                  >
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="font-medium">
                        {result.valid ? 'Test passed' : `Test failed: ${result.status}`}
                      </span>
                      <span>{Math.round(result.latency_ms)} ms</span>
                      <span>{formatTokens(result)}</span>
                    </div>
                    {result.parsed_output && (
                      <pre className="mt-2 overflow-x-auto rounded bg-sc-bg-base p-2 text-xs text-sc-fg-muted">
                        {JSON.stringify(result.parsed_output, null, 2)}
                      </pre>
                    )}
                    {result.error && <p className="mt-2">{result.error}</p>}
                  </div>
                )}

                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => handleSave(surfaceInfo.id)}
                    disabled={savingSurface === surfaceInfo.id}
                    aria-label={`Save ${surfaceInfo.label}`}
                    className="inline-flex items-center justify-center gap-2 rounded-lg bg-sc-cyan px-3 py-2 text-sm font-medium text-sc-bg-dark transition-colors hover:bg-sc-cyan/90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {savingSurface === surfaceInfo.id ? (
                      <>
                        <Spinner size="sm" color="current" />
                        Saving...
                      </>
                    ) : (
                      'Save'
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
