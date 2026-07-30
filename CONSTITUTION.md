# gcploc Constitution

Version: 1.0.0 | Ratified: 2026-07-30

This document is the primary governance veto for humans and AI agents working in
this repository. It adapts transferable engineering discipline from sibling
product workspaces into language appropriate for a public, standalone tool.

## I. Purpose

gcploc is a shared local GCP emulator stack: a Python CLI, Docker Compose
orchestration, and an optional web control panel for observation. It is MIT
licensed, reusable across projects, and not a product SaaS.

## II. Core Principles

### 1. Cost-first and smallest useful change

Prefer the simplest viable approach. Do not add frameworks, chart libraries,
proxies, or Speckit ceremony when a small CLI or read-only API suffices.

### 2. Clarify ambiguity; do not invent product coupling

When requirements are unclear, ask. Do not hard-code consumer app names,
internal monorepo paths, or business terms into committed files.

### 3. Explicit scope and exit criteria

Ship observation and orchestration features with clear non-goals. Silent scope
creep (management UIs, tenant admin, usage-attribution charts) is a defect.

### 4. Observation over management in the control panel

The control panel is read-oriented: Docker status, logs, discovered network
clients, and optional emulator resource inspect. Start/stop/create/delete remain
CLI responsibilities.

### 5. Safety and honesty

Preserve stop warnings when non-gcploc containers are attached to `gcploc_net`.
Surface degraded or unreachable state honestly; never show stale resource counts
as if a stopped emulator were live.

## III. Independence and public surface

gcploc must remain publishable and usable outside any parent workspace.

1. **No committed product coupling** — do not reference parent monorepos,
   product names, internal project IDs, or business terms in committed source,
   docs, examples, or UI copy.
2. **No code dependencies on sibling product repos** — gcploc must not import,
   submodule, or require sibling application packages.
3. **Private aliases only** — `.gcploc.aliases.toml` is gitignored. Ship only
   generic placeholders in `.gcploc.aliases.example.toml`.
4. **Discover, do not catalog consumers** — connected clients are discovered via
   Docker network inspection; never maintain a hard-coded app list.

### Speckit non-adoption

By design, gcploc is **not** a Speckit project. Do not initialize `.specify/`,
Speckit skills, feature NNN folders, or Speckit status indexes here. Product
delivery systems belong in the workspaces that consume gcploc.

### Workspace dogfood

When this repo is checked out beside sibling product repositories, agents must
not edit those siblings from a gcploc session. Product-specific delivery rules
live in those repositories. Write authority for this session ends at the gcploc
repository root. gcploc remains independently governable when published alone.

## IV. Platform constraints

- **Cross-platform tooling** — CLI, hooks, and scripts must work on Windows,
  macOS, and Linux. Prefer `pathlib.Path`, `shutil.which`, argv lists with
  `shell=False`, and `env=` over Unix-only shell prefixes or PowerShell-only
  assumptions.
- **Line endings** — repository text uses LF (`eol=lf`). Prefer writers that
  emit LF for non-Windows-script text.
- **Configuration** — host ports and defaults stay configurable via `.env` and
  `.env.example`.
- **Secrets** — never commit credentials or machine-local secrets.
- **Attribution** — new images, packages, or copied patterns must be recorded in
  `ATTRIBUTIONS.md`.

## V. Control panel constraints

1. Two information categories: **Emulator services** (owned by gcploc) and
   **Connected clients** (discovered peers on `gcploc_net`).
2. Glanceable running-only summary stats (resource inventory and/or aggregate
   Docker CPU/memory) stay on a single muted line per card.
3. **Inspect** is disabled when the emulator is stopped; **View logs** remains
   available (Docker logs work after stop).
4. No user/tenant administration, impersonation, or resource mutation from the UI.
5. Per-client traffic attribution charts and time-series stores are out of scope
   unless a future amendment explicitly expands this section.

## VI. Adding an emulator service

1. Add the service container and profile in `docker-compose.yml`.
2. Add target/service/port mappings in `cli/gcploc.py`.
3. Add env variables to `.env.example` if needed.
4. Document usage and the service matrix in `README.md`.
5. Add dependency/image attribution in `ATTRIBUTIONS.md`.
6. Register the service in `control-panel/backend/server.py` (`SERVICE_META`).

## VII. Governance

- This constitution has veto power over plans and implementations in this repo.
- Amendments bump the version footer and note the change date.
- Agents and humans are expected to comply; conflicts with convenience defaults
  resolve in favor of independence, safety, and observation-only UI scope.

**Version:** 1.0.0 — Initial constitution (independence, Speckit non-adoption,
control-panel observation rules).
