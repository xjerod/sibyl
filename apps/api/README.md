# Sibyl API Server

FastAPI + MCP server providing the backend for Sibyl's knowledge graph, task workflows, search, and
real-time updates.

## Quick Reference

```bash
# Start server
moon run api:serve        # or: uv run sibyld serve

# Start worker (Redis coordination only)
moon run api:worker       # or: uv run sibyld worker

# Quality checks
moon run api:test         # Run tests
moon run api:lint         # Lint
moon run api:typecheck    # Type check
```

## What's Here

- **MCP Server:** 5-tool API for search, exploration, capture, and task management
- **REST API:** Full CRUD for entities, tasks, projects, and sources
- **Auth System:** JWT, OAuth (GitHub), API keys, RBAC
- **Background Jobs:** In-process local runtime or Redis-backed `arq` workers
- **WebSocket:** Real-time updates for entities and tasks

## Architecture

```
Sibyl Combined App (port 3334)
├── /api/*    → FastAPI REST endpoints
├── /mcp      → MCP streamable-http (4 tools)
├── /ws       → WebSocket for real-time updates
└── Lifespan  → Background queue + session management
```

## Key Directories

| Directory     | Purpose                                                          |
| ------------- | ---------------------------------------------------------------- |
| `api/routes/` | REST endpoints (tasks, entities, auth, crawler, admin, and more) |
| `ai/`         | DB-backed LLM settings, validation routes, and runtime invalidation |
| `auth/`       | JWT, sessions, API keys, RBAC, RLS                               |
| `crawler/`    | Documentation ingestion pipeline                                 |
| `jobs/`       | Background job definitions                                       |
| `db/`         | Legacy SQLModel + Alembic models                                 |

## Configuration

**Required:**

```bash
SIBYL_JWT_SECRET=...              # Auth
SIBYL_ANTHROPIC_API_KEY=...       # Required when LLM provider=anthropic
# SIBYL_OPENAI_API_KEY=sk-...     # Required when LLM provider=openai
# SIBYL_GEMINI_API_KEY=...        # Required when LLM provider=gemini

# Embeddings: choose OpenAI or Gemini
SIBYL_EMBEDDING_PROVIDER=openai   # openai | gemini
SIBYL_OPENAI_API_KEY=sk-...       # Required when embedding provider=openai
# SIBYL_GEMINI_API_KEY=...        # Required when embedding provider=gemini
```

**Optional:**

```bash
SIBYL_STORE=surreal                   # default; legacy is migration/source-side only
SIBYL_COORDINATION_BACKEND=auto       # auto | local | redis
SIBYL_SURREAL_URL=ws://127.0.0.1:8000/rpc
SIBYL_SURREAL_USERNAME=root
SIBYL_SURREAL_PASSWORD=root
SIBYL_REDIS_HOST=127.0.0.1            # only needed for Redis coordination
SIBYL_REDIS_PORT=6381
SIBYL_LLM_PROVIDER=anthropic          # anthropic | gemini | openai
SIBYL_LLM_MODEL=claude-haiku-4-5
SIBYL_LLM_CRAWLER_MODEL=claude-haiku-4-5
SIBYL_LLM_SYNTHESIS_MODEL=claude-sonnet-4-6
SIBYL_LLM_TEMPERATURE=0
SIBYL_LLM_TIMEOUT_SECONDS=60
SIBYL_EMBEDDING_MODEL=text-embedding-3-small
SIBYL_EMBEDDING_DIMENSIONS=1536
SIBYL_GRAPH_EMBEDDING_PROVIDER=openai
SIBYL_GRAPH_EMBEDDING_MODEL=text-embedding-3-small
SIBYL_GRAPH_EMBEDDING_DIMENSIONS=1024
```

PostgreSQL settings are only for historical archive rehearsal commands that explicitly restore a
retained `postgres.sql` payload against an operator-managed database. They are not part of default
Surreal runtime startup.

Gemini keys can also be supplied through `GEMINI_API_KEY` or `GOOGLE_API_KEY`. Changing embedding
provider, model, or dimensions changes vector spaces; re-crawl sources and rebuild graph indexes
before mixing old and new search results.

LLM settings are instance-wide in v0.10. Environment variables win over database settings field by
field; env-backed fields return `409 LOCKED_BY_ENV` on write. Database settings are managed under:

```text
GET  /api/settings/ai/llm
PUT  /api/settings/ai/llm/{surface}
POST /api/settings/ai/llm/{surface}/test
POST /api/settings/ai/keys/{provider}/test
POST /api/settings/ai/models/{model_alias}/test
GET  /api/settings/ai/registry?kind=llm
```

Crawler extraction and synthesis generation now call `sibyl_core.ai` instead of provider SDKs
directly. Custom model IDs are accepted as database settings with an `unverified_model` warning;
operators should validate them with the model test endpoint before using them in production flows.

## CLI Commands

```bash
sibyld serve              # Start HTTP server
sibyld serve -t stdio     # Start stdio server (for MCP subprocess)
sibyld worker             # Start Redis worker (local mode exits cleanly)
sibyld up                 # Start all services (Supabase-style)
sibyld down               # Stop all services
sibyld db clear           # Delete all data (dangerous!)
sibyld generate realistic # Generate sample data
```

## Runtime Modes

For single-machine Surreal development, run `sibyld serve` or `sibyld up` with
`SIBYL_STORE=surreal`. The default `coordination_backend=auto` resolves to `local`, so background
jobs, pending state, locks, pub/sub, and schedules all stay in-process with no Redis requirement.

Redis remains available for distributed or multi-process dev. Set `SIBYL_COORDINATION_BACKEND=redis`
when you want the existing `arq` worker model, then run `sibyld worker` or `moon run api:worker`
separately.

## Key Patterns

**Multi-tenancy:** Every operation requires org context

```python
manager = EntityManager(client, group_id=str(org.id))
```

Write concurrency: the SurrealDB driver serializes WebSocket operations per client. Clone graph
drivers per organization rather than sharing one driver across org scopes.

**Request context:** Auth middleware injects user/org

```python
from sibyl.auth.dependencies import get_current_user, get_current_organization
```

## Dependencies

Depends on `sibyl-core` for models, graph client, and tool implementations.
