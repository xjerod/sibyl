import { beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  AIModelEntry,
  LLMConfigSource,
  LLMProviderName,
  LLMSettingsResponse,
  LLMSurface,
} from '@/lib/api';
import { render, screen } from '@/test/utils';

const hooks = vi.hoisted(() => ({
  useLLMRegistry: vi.fn(),
  useLLMSettings: vi.fn(),
  useTestLLMSurface: vi.fn(),
  useUpdateLLMSurface: vi.fn(),
}));

const toast = vi.hoisted(() => ({
  error: vi.fn(),
  success: vi.fn(),
  warning: vi.fn(),
}));

vi.mock('@/lib/hooks', () => hooks);
vi.mock('sonner', () => ({ toast }));

import { LLMConfigCard } from './llm-config-card';

function valueField(value: string | number | null, source: LLMConfigSource = 'default') {
  return {
    value,
    source,
    locked_by_env: source === 'env',
    env_var: source === 'env' ? 'SIBYL_LLM_CRAWLER_MODEL' : null,
  };
}

function secretField(configured = true, source: LLMConfigSource = 'db') {
  return {
    configured,
    source,
    locked_by_env: source === 'env',
    env_var: source === 'env' ? 'SIBYL_ANTHROPIC_API_KEY' : null,
    masked: configured ? 'sk-...test' : null,
  };
}

function surface(
  id: LLMSurface,
  provider: LLMProviderName,
  model: string,
  modelSource: LLMConfigSource = 'default'
) {
  return {
    surface: id,
    provider: valueField(provider),
    model: valueField(model, modelSource),
    temperature: valueField(0),
    max_tokens: valueField(null),
    timeout_seconds: valueField(60),
    api_key: secretField(true),
    cached_at: null,
  };
}

function settings(): LLMSettingsResponse {
  return {
    scope: 'instance_wide',
    surfaces: {
      default: surface('default', 'anthropic', 'claude-haiku-4-5'),
      crawler: surface('crawler', 'anthropic', 'claude-haiku-4-5'),
      synthesis: surface('synthesis', 'anthropic', 'claude-sonnet-4-6'),
    },
  };
}

function model(alias: string, provider: LLMProviderName, useCases: string[]): AIModelEntry {
  return {
    alias,
    snapshot: `${alias}-snapshot`,
    kind: 'llm',
    provider,
    provider_model_id: `${alias}-provider`,
    pydantic_ai_model_class: 'TestModel',
    use_cases: useCases,
    capabilities: ['structured_output'],
    max_output_tokens: 8192,
    embedding_dimensions: null,
    default_temperature: 0,
    input_cost_per_mtok_usd: 1,
    output_cost_per_mtok_usd: 5,
    cost_source_url: 'https://example.test',
    last_verified_at: '2026-05-15T00:00:00Z',
    deprecated_after: null,
    warning: null,
  };
}

describe('LLMConfigCard', () => {
  let updateMutateAsync: ReturnType<typeof vi.fn>;
  let testMutateAsync: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    updateMutateAsync = vi.fn().mockResolvedValue({
      warning: null,
      surface: settings().surfaces.crawler,
    });
    testMutateAsync = vi.fn().mockResolvedValue({
      surface: 'crawler',
      provider: 'anthropic',
      model: 'claude-haiku-4-5',
      status: 'valid',
      valid: true,
      latency_ms: 42,
      parsed_output: { ok: true, summary: 'ready' },
      input_tokens: 3,
      output_tokens: 4,
      error: null,
    });

    hooks.useLLMSettings.mockReturnValue({ data: settings(), isLoading: false });
    hooks.useLLMRegistry.mockReturnValue({
      data: {
        entries: [
          model('claude-haiku-4-5', 'anthropic', ['default', 'extraction']),
          model('claude-sonnet-4-6', 'anthropic', ['synthesis']),
          model('gemini-3-flash', 'gemini', ['extraction']),
        ],
      },
      isLoading: false,
    });
    hooks.useUpdateLLMSurface.mockReturnValue({
      mutateAsync: updateMutateAsync,
      isPending: false,
    });
    hooks.useTestLLMSurface.mockReturnValue({
      mutateAsync: testMutateAsync,
      isPending: false,
    });
    toast.error.mockReset();
    toast.success.mockReset();
    toast.warning.mockReset();
  });

  it('renders instance-wide language model rows', () => {
    render(<LLMConfigCard />);

    expect(screen.getByText('Language Models')).toBeInTheDocument();
    expect(screen.getByText(/every organization/i)).toBeInTheDocument();
    expect(screen.getByText('Default')).toBeInTheDocument();
    expect(screen.getByText('Crawler')).toBeInTheDocument();
    expect(screen.getByText('Synthesis')).toBeInTheDocument();
  });

  it('saves the crawler surface through the LLM settings mutation', async () => {
    const { user } = render(<LLMConfigCard />);

    await user.click(screen.getByRole('button', { name: 'Save Crawler' }));

    expect(updateMutateAsync).toHaveBeenCalledWith({
      surface: 'crawler',
      request: {
        provider: 'anthropic',
        model: 'claude-haiku-4-5',
        temperature: 0,
        timeout_seconds: 60,
      },
    });
  });

  it('runs a surface test and renders latency plus token counts', async () => {
    const { user } = render(<LLMConfigCard />);

    await user.click(screen.getByRole('button', { name: 'Test Crawler' }));

    expect(testMutateAsync).toHaveBeenCalledWith('crawler');
    expect(await screen.findByText('Test passed')).toBeInTheDocument();
    expect(screen.getByText('42 ms')).toBeInTheDocument();
    expect(screen.getByText('3 in / 4 out')).toBeInTheDocument();
  });

  it('shows environment-locked fields as disabled', () => {
    const locked = settings();
    locked.surfaces.crawler = surface('crawler', 'anthropic', 'claude-haiku-4-5', 'env');
    hooks.useLLMSettings.mockReturnValue({ data: locked, isLoading: false });

    render(<LLMConfigCard />);

    const selects = screen.getAllByRole('combobox');
    expect(selects[3]).toBeDisabled();
  });
});
