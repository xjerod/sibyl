# Sibyl Local Infrastructure

Local Kubernetes development for a small scalable Sibyl fleet.

The Tilt path runs Sibyl in its default SurrealDB-native mode, with TiKV as SurrealDB's distributed
datastore and Valkey as the coordination plane for jobs, locks, pub/sub, and rate limits.

## Components

| Component | Chart or manifest | Purpose |
| --- | --- | --- |
| Gateway API | upstream CRDs | Gateway resources for Kong |
| cert-manager | `jetstack/cert-manager` | Local TLS certificate plumbing |
| Kong Operator | `kong/kong-operator` | Gateway API implementation |
| TiDB Operator | `pingcap/tidb-operator` | Manages the TiKV cluster |
| TiKV/PD | `infra/local/tidb-cluster.yaml` | Distributed datastore for SurrealDB |
| SurrealDB | `surrealdb/surrealdb` | Graph, content, and auth store |
| Valkey | `valkey/valkey` | Distributed coordination for Sibyl replicas |
| Sibyl | `../../charts/sibyl` | Backend, worker, and frontend deployments |

## Shape

- 3 PD pods and 3 TiKV pods for the datastore demo
- 2 SurrealDB pods connected to `tikv://sibyl-tikv-pd:2379`
- 3 Valkey pods: one primary plus two replicas
- 2 Sibyl backend pods
- 2 Sibyl worker pods
- 2 Sibyl frontend pods

## Quick Start

```bash
# Start your Kubernetes environment first.
minikube start --cpus=6 --memory=12288 --driver=docker
podman --version # or docker version

export SIBYL_JWT_SECRET="$(openssl rand -hex 32)"
export SIBYL_SURREAL_PASSWORD="sibyl-local-dev"
export SIBYL_REDIS_PASSWORD="sibyl-local-dev"
export ANTHROPIC_API_KEY="sk-ant-..."

tilt up
```

The Tiltfile creates the local `sibyl-secrets` Secret from those environment variables.

## Manual Render Checks

```bash
helm template surrealdb surrealdb/surrealdb \
  --version 0.4.0 \
  -n sibyl \
  -f surrealdb-values.yaml

helm template valkey valkey/valkey \
  --version 0.9.4 \
  -n sibyl \
  -f valkey-values.yaml

helm template sibyl ../../charts/sibyl \
  -n sibyl \
  -f sibyl-values.yaml
```

## Access

```bash
kubectl port-forward -n sibyl svc/surrealdb 8000:8000
kubectl port-forward -n sibyl svc/valkey 6379:6379
kubectl port-forward -n sibyl svc/sibyl-backend 3334:3334
kubectl port-forward -n sibyl svc/sibyl-frontend 3337:3337
```
