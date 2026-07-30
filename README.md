# gcploc — Local GCP Emulators

Centralized Docker Compose stack for running local GCP emulator services that can be shared across projects.

## Services

| Service target | Container | Image | Port |
|----------------|-----------|-------|------|
| `pubsub` | `pubsub` | `gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators` | 8085 |
| `gcs` | `fakegcs` | `fsouza/fake-gcs-server:latest` | 4443 |
| `cloudtasks` | `cloudtasks` | `ghcr.io/aertje/cloud-tasks-emulator:latest` | 8123 |
| `firestore` | `firestore` | `gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators` | 8080 |
| `spanner` | `spanner` | `gcr.io/cloud-spanner-emulator/emulator:latest` | 9010 (gRPC), 9020 (REST) |
| `bigtable` | `bigtable` | `gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators` | 8086 |
| `secretmanager` | `secretmanager` | `nicholasgasior/gcp-secret-manager-fake:latest` ¹ | 4444 |

¹ Community image — not an official Google emulator. Override with `GCPLOC_SECRETMANAGER_IMAGE`.

All containers are reachable by hostname within the shared `gcploc_net` Docker bridge network.

## Prerequisites

- Docker + Docker Compose v2
- Python 3.11+ (for the CLI)

## Install the CLI

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e cli/
```

## Control Panel

Tech stack:
- React + TypeScript + Vite
- Tailwind CSS (neutral palette, dark/light themes)
- shadcn-style component primitives (`Button`, `Card`, `Badge`)

Where it lives:
- Main dashboard: `control-panel/src/App.tsx`
- Theme and tokens: `control-panel/src/index.css`
- UI primitives: `control-panel/src/components/ui/*`
- Status / SSE / logs API: `control-panel/backend/server.py`

Run via CLI (recommended):

```bash
gcploc start cp
```

Or run directly:

```bash
npm --prefix control-panel install
npm --prefix control-panel run api   # backend on :8787
npm --prefix control-panel run dev   # UI on :5173
```

Open `http://localhost:5173` in your browser.

The dashboard uses SSE (`/api/events`) for near real-time updates, falls back to `/api/status` every 30s, and serves container logs via `/api/logs/{serviceId}`.

The dashboard uses a dual-pane layout on large screens: **Emulator services** (two-column card grid with docker CPU/memory snippets and emulator summaries) and **Connected clients** (sticky sidebar with containers on `gcploc_net`, plus a stop-confirmation preview). On mobile, connected clients appear first.

For Fake GCS, Pub/Sub, and Cloud Tasks, open **Inspect** on a running service. The **Observe** tab calls read APIs (`/api/observe/gcs`, `/api/observe/pubsub`, `/api/observe/cloudtasks`). The **Manage** tab runs scoped local actions via `GET /api/manage/capabilities` and `POST /api/manage/{serviceId}/{action}` (409 when the emulator is stopped). Destructive actions require typing the resource name in the UI. Start/stop containers stays CLI-only; manage never targets cloud APIs.

## Usage

```bash
# Start all emulator services
gcploc start services

# Start selected emulator services
gcploc start gcs cloudtasks

# Start control panel only
gcploc start cp

# Start emulator services and control panel together
gcploc start services cp

# Stop all emulator services and control panel
gcploc stop

# Stop only emulator services
gcploc stop services

# Stop only selected emulator services
gcploc stop pubsub

# Stop only control panel
gcploc stop cp

# Skip dependency warning prompt (use with care)
gcploc stop --force

# Show emulator container status
gcploc status

# Show required ports and who is using them
gcploc ports

# Tail logs (logical targets or compose names both work)
gcploc logs pubsub
gcploc logs -f gcs
gcploc logs fakegcs

# Diagnose potential issues
gcploc doctor
```

`gcploc stop` checks for non-gcploc containers attached to `gcploc_net` before stopping emulator services. This helps prevent accidental shutdown while dependent app containers are still running.

## Optional local aliases

Aliases are **local-only** so personal or internal project names never ship in this repo.

1. Copy `.gcploc.aliases.example.toml` to `.gcploc.aliases.toml`
2. Uncomment or add your own alias mappings
3. Use them: `gcploc start myapp`

Example:

```toml
[aliases]
myapp = ["pubsub", "gcs"]
workers = ["gcs", "cloudtasks"]
full = ["services", "cp"]
```

`.gcploc.aliases.toml` is gitignored. Point elsewhere with `GCPLOC_ALIASES_FILE` if needed.

## Connecting applications

Each application Docker Compose should declare `gcploc_net` as an external network. Run `gcploc start <service>` before starting your app stack.

### Container hostnames

| Service | Hostname | Port |
|---------|----------|------|
| Pub/Sub emulator | `pubsub` | `8085` |
| Fake GCS | `fakegcs` | `4443` |
| Cloud Tasks | `cloudtasks` | `8123` |
| Firestore emulator | `firestore` | `8080` |
| Cloud Spanner | `spanner` | `9010` (gRPC), `9020` (REST) |
| Bigtable emulator | `bigtable` | `8086` |
| Secret Manager fake | `secretmanager` | `4444` |

### Env vars applications typically need

For Pub/Sub:

```
PUBSUB_EMULATOR_HOST=pubsub:8085
```

For GCS (use `STORAGE_EMULATOR_HOST` — standard for `google-cloud-storage`):

```
STORAGE_EMULATOR_HOST=http://fakegcs:4443
STORAGE_EMULATOR_PUBLIC_HOST=http://localhost:4443
```

For Cloud Tasks:

```
CLOUD_TASKS_EMULATOR_HOST=cloudtasks:8123
```

### Example: join from another Compose project

```yaml
services:
  api:
    environment:
      PUBSUB_EMULATOR_HOST: pubsub:8085
      STORAGE_EMULATOR_HOST: http://fakegcs:4443
      CLOUD_TASKS_EMULATOR_HOST: cloudtasks:8123
    networks:
      - default
      - gcploc_net

networks:
  gcploc_net:
    external: true
```

Do **not** set emulator host variables in production (Cloud Run, Terraform, etc.).

## Resource initialization

gcploc intentionally does not create app-specific topics, buckets, or queues under your application project ID. It only pre-seeds Cloud Tasks queues under `GCPLOC_PROJECT_ID` (`gcploc-local` by default). Create application resources from your own tooling after emulators are up.

## Configuration

Copy `.env.example` to `.env` (defaults work for standard dev setup):

```bash
cp .env.example .env
```

The CLI loads `.env` for port checks (`ports`, conflict detection on `start`). Docker Compose also reads `.env` automatically. Process environment variables always win over `.env`.

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `GCPLOC_PROJECT_ID` | `gcploc-local` | GCP project ID used by all emulators |
| `GCPLOC_TASKS_LOCATION` | `us-central1` | Cloud Tasks region |
| `GCPLOC_PUBSUB_HOST_PORT` | `8085` | Host port published for Pub/Sub emulator |
| `GCPLOC_GCS_HOST_PORT` | `4443` | Host port published for Fake GCS |
| `GCPLOC_CLOUDTASKS_HOST_PORT` | `8123` | Host port published for Cloud Tasks emulator |
| `GCPLOC_FIRESTORE_HOST_PORT` | `8080` | Host port published for Firestore emulator |
| `GCPLOC_SPANNER_GRPC_HOST_PORT` | `9010` | Host port for Spanner gRPC |
| `GCPLOC_SPANNER_REST_HOST_PORT` | `9020` | Host port for Spanner REST |
| `GCPLOC_BIGTABLE_HOST_PORT` | `8086` | Host port published for Bigtable emulator |
| `GCPLOC_SECRETMANAGER_HOST_PORT` | `4444` | Host port for Secret Manager fake |
| `GCPLOC_SECRETMANAGER_IMAGE` | `nicholasgasior/gcp-secret-manager-fake:latest` | Image for Secret Manager fake |
| `GCPLOC_CP_URL` | `http://localhost:5173` | Control panel URL used by `gcploc start cp` |
| `GCPLOC_TASKS_QUEUE_PRIMARY` | `default` | Primary queue name passed to Cloud Tasks emulator |
| `GCPLOC_TASKS_QUEUE_SECONDARY` | `ai` | Secondary queue name passed to Cloud Tasks emulator |

If startup fails with host port conflicts, either stop the conflicting container, or change one of the host port variables above and retry.

## Profiles

Docker Compose profiles map to service targets:

| Profile | Services started |
|---------|------------------|
| `pubsub` | `pubsub` |
| `gcs` | `fakegcs` |
| `cloudtasks` | `cloudtasks` |
| `firestore` | `firestore` |
| `spanner` | `spanner` |
| `bigtable` | `bigtable` |
| `secretmanager` | `secretmanager` |

Multiple profiles can be combined:

```bash
COMPOSE_PROFILES=gcs,cloudtasks docker compose up -d
# or via CLI:
gcploc start gcs cloudtasks
```

## License and attributions

gcploc is released under the [MIT License](LICENSE).

It builds on emulator images, libraries, and tools created by the open-source
community. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for a full list of credits.
