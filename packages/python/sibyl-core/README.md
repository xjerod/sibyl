# sibyl-core

Core library for Sibyl — domain models, graph operations, retrieval algorithms, and tool
implementations. Shared foundation for the API server and CLI.

## Quick Reference

```bash
# Install
uv add sibyl-core

# Development
moon run core:lint        # Ruff check
moon run core:typecheck   # Pyright
moon run core:test        # Pytest
```

## What's Here

- **models/** — Domain entities (Task, Project, Epic, Source, etc.)
- **graph/** — FalkorDB/Graphiti client, entity management
- **retrieval/** — Graphiti node-hybrid search, fusion, deduplication
- **tools/** — MCP tool implementations (search, explore, add, manage)
- **tasks/** — Workflow engine, dependency resolution
- **auth/** — JWT primitives, password hashing

## Structure

```
src/sibyl_core/
├── models/
│   ├── entities.py       # Entity, EntityType, base classes
│   ├── tasks.py          # Task, Project, Epic, Milestone
│   ├── sources.py        # Source, Document
│   └── responses.py      # API response models
├── graph/
│   ├── client.py         # GraphClient (connection, write lock)
│   ├── entities.py       # EntityManager (CRUD, search)
│   └── relationships.py  # RelationshipManager
├── retrieval/
│   ├── hybrid.py         # Hybrid search orchestration
│   └── fusion.py         # Score fusion (RRF)
├── tools/
│   ├── search.py         # Semantic search
│   ├── explore.py        # Graph navigation
│   ├── add.py            # Entity creation
│   └── manage.py         # Task workflow, admin
└── tasks/
    ├── workflow.py       # State machine, transitions
    └── manager.py        # Task operations
```

## Usage

### Models

```python
from sibyl_core.models import (
    Entity, EntityType, Task, TaskStatus, Project, Epic,
)

task = Task(
    name="Implement OAuth",
    content="Add Google and GitHub OAuth",
    project_id="proj_abc",
    status=TaskStatus.TODO,
)
```

### Graph Client

```python
from sibyl_core.graph import GraphClient, EntityManager

client = await GraphClient.create()
manager = EntityManager(client, group_id=str(org_id))

# CRUD
await manager.create(entity)
entity = await manager.get_by_id("entity_abc")
results = await manager.search("authentication patterns", limit=20)
```

### Write Concurrency

Write concurrency is handled by FalkorDB's BlockingConnectionPool (50 connections, 60s timeout).
No application-level locking is required.

```python
# Direct writes are safe - connection pool handles concurrency
await client.execute_write_org(org_id, query, **params)

# Or use EntityManager
await manager.create(entity)
```

### Task Workflow

```python
from sibyl_core.tasks import TaskManager

manager = TaskManager(entity_manager)
await manager.start_task(task_id)
await manager.complete_task(task_id, learnings="Key insight...")
await manager.block_task(task_id, reason="Waiting on API")
```

## Entity Types

| Type | Description |
|------|-------------|
| `pattern` | Reusable coding patterns |
| `episode` | Temporal learnings |
| `task` | Work items with workflow |
| `project` | Container for tasks |
| `epic` | Feature-level grouping |
| `source` | Documentation sources |
| `document` | Crawled content |

## Relationship Types

```python
from sibyl_core.models import RelationshipType

# Knowledge
RelationshipType.APPLIES_TO, REQUIRES, CONFLICTS_WITH, SUPERSEDES

# Task
RelationshipType.BELONGS_TO, DEPENDS_ON, BLOCKS, REFERENCES

```

## Configuration

```bash
SIBYL_OPENAI_API_KEY=sk-...         # Required (embeddings)
SIBYL_FALKORDB_HOST=localhost
SIBYL_FALKORDB_PORT=6380
SIBYL_ANTHROPIC_API_KEY=...         # Optional (LLM-powered features)
```

## Key Patterns

**Multi-tenancy:** Every operation requires org context
```python
manager = EntityManager(client, group_id=str(org.id))
```

**Node labels:** Graphiti creates `Episodic` and `Entity` nodes
```cypher
WHERE (n:Episodic OR n:Entity) AND n.entity_type = $type
```

**Creation paths:** LLM-powered (`create`) vs direct (`create_direct`)
```python
await manager.create(entity)         # Slower, richer extraction
await manager.create_direct(entity)  # Faster, no LLM
```

## Testing

```bash
# With mock LLM (fast, deterministic)
SIBYL_MOCK_LLM=true uv run pytest tests/

# Live model tests (costs money)
uv run pytest tests/live --live-models
```
