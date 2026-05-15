import { describe, expect, it } from 'vitest';
import { render, screen } from '@/test/utils';
import { SourceImportProgress } from './source-import-progress';

const status = {
  import_id: 'import-1',
  adapter_name: 'mbox',
  adapter_version: '1.0',
  source_identity: 'mailbox.mbox',
  source_version: null,
  status: 'running' as const,
  privacy_class: 'personal',
  target_memory_scope: 'private' as const,
  target_scope_key: null,
  checkpoint: {},
  progress: {
    imported_count: 2,
    skipped_count: 1,
    dedupe_count: 1,
    error_count: 0,
    attachment_count: 3,
    extraction_pending_count: 1,
    raw_memory_count: 2,
  },
  raw_memory_ids: ['raw-1'],
  dedupe_keys: ['dedupe-1'],
  duplicate_dedupe_keys: ['dedupe-duplicate'],
  skipped_records: [
    {
      adapter_record_id: 'mbox:1',
      source_uri: 'mbox:///mailbox.mbox',
      reason: 'message_parse_failed',
      metadata: {
        raw_subject: 'private subject',
        sender: 'person@example.com',
      },
    },
  ],
  errors: [
    {
      code: 'adapter_error',
      message: 'failed before content extraction',
      metadata: {
        raw_body: 'secret body',
      },
    },
  ],
  created_at: '2026-05-14T12:00:00Z',
  updated_at: '2026-05-14T12:01:00Z',
  completed_at: null,
};

describe('SourceImportProgress', () => {
  it('renders source-safe import status without skipped metadata', () => {
    render(<SourceImportProgress status={status} />);

    expect(screen.getByText('Import Progress')).toBeInTheDocument();
    expect(screen.getByText('message_parse_failed')).toBeInTheDocument();
    expect(screen.getByText('failed before content extraction')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'raw-1' })).toHaveAttribute(
      'href',
      '/memory/sources/raw-1'
    );
    expect(screen.queryByText('private subject')).not.toBeInTheDocument();
    expect(screen.queryByText('person@example.com')).not.toBeInTheDocument();
    expect(screen.queryByText('secret body')).not.toBeInTheDocument();
  });
});
