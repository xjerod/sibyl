# Docker Compose Deployment

Local development using Docker Compose for database services with the Python/Node applications
running natively.

## Architecture

Docker Compose runs the database services while applications run natively for hot reload:

```
+------------------+     +------------------+
|   Native Apps    |     |   Docker Compose |
|------------------|     |------------------|
| Backend (:3334)  |---->| SurrealDB (:8000)|
| Frontend (:3337) |     | Redis* (:6381)   |
| Jobs + Schedules |     |                  |
+------------------+     +------------------+
```

`Redis` is opt-in for distributed or multi-process dev. The default local path only needs SurrealDB.

## Prerequisites

- Docker and Docker Compose
- Python 3.13+
- Node.js 20+ and pnpm
- uv (Python package manager)

## Quick Start

```bash
# 1. Start database services
docker compose up -d surrealdb

# 2. Install dependencies
uv sync                         # Python packages
cd apps/web && pnpm install     # Frontend packages

# 3. Configure environment
cp .env.example .env
# Edit .env and add:
#   SIBYL_JWT_SECRET=<random-secret>
#   SIBYL_OPENAI_API_KEY=sk-...

# 4. Start all services
moon run dev
```

For Redis-backed coordination, opt into the `redis` profile explicitly:

```bash
docker compose --profile redis up -d surrealdb redis
SIBYL_COORDINATION_BACKEND=redis moon run dev
```

## Service Definitions

The `docker-compose.yml` defines a Surreal-first local stack plus opt-in profiles:

```yaml
services:
  surrealdb:
    image: ${SIBYL_SURREAL_IMAGE:-surrealdb/surrealdb:v3.0.5}
    container_name: sibyl-surrealdb
    ports:
      - "8000:8000"
    volumes:
      - ./.moon/cache/surreal-dev:/data

  redis:
    image: valkey/valkey:8-alpine
    container_name: sibyl-redis
    profiles: ["redis"]
    ports:
      - "6381:6379"
```

The default image is pinned to SurrealDB server `v3.0.5` for reproducible local and CI behavior.
Override `SIBYL_SURREAL_IMAGE` when rehearsing a newer server patch.

## Port Mappings

| Service   | Host Port | Container Port | Purpose                       |
| --------- | --------- | -------------- | ----------------------------- |
| SurrealDB | 8000      | 8000           | Default local graph runtime   |
| Redis     | 6381      | 6379           | Optional coordination backend |

Ports are offset from defaults to avoid conflicts with local services.

## Moonrepo Commands

```bash
# Start databases only
moon run docker-up

# Stop databases
moon run docker-down

# Start recommended Surreal local-dev stack
moon run dev

# Start API + Worker only (no frontend)
moon run dev-api

# Start frontend only
moon run dev-web

# Start Redis worker when SIBYL_COORDINATION_BACKEND=redis
moon run api:worker

# Stop all services
moon run stop
```

## Full Stack Compose

For a complete containerized deployment (backend + frontend + databases), use
`docker-compose.prod.yml`:

```bash
# Copy environment file
cp apps/api/.env.example .env

# Edit .env with required secrets:
#   SIBYL_JWT_SECRET=<generate with: openssl rand -hex 32>
#   SIBYL_OPENAI_API_KEY=sk-...

# Start all services
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop all services
docker compose -f docker-compose.prod.yml down
```

### Production Compose Services

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    ports:
      - "3334:3334"
    environment:
      SIBYL_SURREAL_URL: ws://surrealdb:8000/rpc
      SIBYL_JWT_SECRET: ${SIBYL_JWT_SECRET}
      SIBYL_OPENAI_API_KEY: ${SIBYL_OPENAI_API_KEY}
    depends_on:
      surrealdb:
        condition: service_healthy

  worker:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    command: ["sibyld", "worker"]
    environment:
      SIBYL_SURREAL_URL: ws://surrealdb:8000/rpc
      SIBYL_JWT_SECRET: ${SIBYL_JWT_SECRET}
      SIBYL_OPENAI_API_KEY: ${SIBYL_OPENAI_API_KEY}
    depends_on:
      surrealdb:
        condition: service_healthy

  frontend:
    build:
      context: ./apps/web
      dockerfile: Dockerfile
    ports:
      - "3337:3337"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:3334
    depends_on:
      backend:
        condition: service_healthy

  # ... databases as above
```

## Volume Persistence

The default Surreal local-dev path persists data in the bind mount configured by `SURREAL_DATA_DIR`
or `.moon/cache/surreal-dev` by default.

```bash
# Inspect the default local Surreal data directory
ls .moon/cache/surreal-dev
```

Legacy services still use Docker volumes:

```bash
docker volume ls | grep sibyl

# Remove volumes (DESTROYS DATA)
docker compose down -v
```

## Connecting to Databases

### SurrealDB Health

```bash
curl http://localhost:8000/health
```

### Redis CLI

```bash
# Only when the redis profile is running
docker exec -it sibyl-redis redis-cli
```

### Migration Archive Rehearsal

The default compose file no longer ships a PostgreSQL sidecar. Historical `postgres.sql` archive
rehearsal must point at an explicitly managed external database, then run the migration command with
`--restore-database-dump`.

## Troubleshooting

### Port Conflicts

If ports 8000 or 6381 are in use:

```bash
# Check what's using the port
lsof -i :8000
lsof -i :6381

# Stop conflicting services or modify docker-compose.yml ports
```

### Database Not Starting

```bash
# Check container logs
docker compose logs surrealdb
docker compose logs redis

# Restart with clean state
docker compose down -v
docker compose up -d surrealdb
```

### Connection Refused

Ensure your `.env` uses the correct ports:

```bash
SIBYL_SURREAL_URL=ws://127.0.0.1:8000/rpc
SIBYL_REDIS_PORT=6381        # Only when coordination backend is redis
```

## Next Steps

- [Environment Variables](environment.md) - Full configuration options
- [Troubleshooting](troubleshooting.md) - Common issues
