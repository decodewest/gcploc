# AGENTS.md

## Project purpose

gcploc provides a shared local emulator stack for common GCP services so multiple
apps can develop against the same local infrastructure. It includes a Python CLI,
Docker Compose orchestration, and an optional web control panel.

## Core commands

- Install CLI: `pip install -e cli/`
- Start all emulator services: `gcploc start services`
- Start selected services: `gcploc start pubsub gcs`
- Start control panel: `gcploc start cp`
- Stop everything: `gcploc stop`
- Stop only services: `gcploc stop services`
- Stop only control panel: `gcploc stop cp`
- Health diagnostics: `gcploc doctor`

## Architecture map

- CLI entrypoint: `cli/gcploc.py`
- Python packaging metadata: `cli/setup.py`
- Service orchestration: `docker-compose.yml`
- Runtime defaults and env contract: `.env.example`
- Control panel frontend/backend: `control-panel/`
- Dependency/legal credits: `ATTRIBUTIONS.md`

## Contribution guardrails

- Keep the repository generic and reusable; avoid project-specific names and business terms.
- New emulator services must be configurable and documented for broad use.
- Preserve safety behavior around stop operations and dependent container checks.
- Keep host ports/env vars configurable via `.env` and `.env.example`.
- Update docs when commands, profiles, or environment variables change.

## Adding a new emulator service

1. Add the service container and profile in `docker-compose.yml`.
2. Add target/service/port mappings in `cli/gcploc.py`.
3. Add env variables to `.env.example` if needed.
4. Document usage and service matrix updates in `README.md`.
5. Add dependency/image attribution in `ATTRIBUTIONS.md`.

## Attribution policy

If this repo starts using a new image, package, framework, or copied component pattern:
- Add an entry in `ATTRIBUTIONS.md` with source and license.
- Keep attribution accurate during upgrades and replacements.
