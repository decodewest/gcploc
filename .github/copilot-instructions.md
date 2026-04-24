# Copilot Instructions for gcploc

## Build, run, test commands

- Create env + install CLI:
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
  - `pip install -e cli/`
- CLI quick checks:
  - `gcploc start services`
  - `gcploc status`
  - `gcploc doctor`
  - `gcploc stop`
- Control panel:
  - `npm --prefix control-panel install`
  - `npm --prefix control-panel run dev`
  - `npm --prefix control-panel run api`

## Coding style expectations

- Prefer small, focused changes over broad rewrites.
- Keep output and UX clear in CLI (readable sections, concise success/warn lines).
- Preserve backward compatibility unless explicitly removed.
- Use ASCII-only text unless file already uses non-ASCII.
- Keep comments concise and only where behavior is not obvious.

## Where to add new emulator services

- Compose service definitions and profiles: `docker-compose.yml`
- CLI command routing and checks: `cli/gcploc.py`
  - `EMULATOR_TARGETS` set
  - `TARGET_TO_COMPOSE_SERVICES` map
  - `TARGET_TO_HOST_PORT` map
  - `_has_running_emulator_containers()` name list
  - `doctor()` containers dict
  - `status` command service name list
- Environment defaults: `.env.example`
- Documentation and examples: `README.md`
- Backend service registry: `control-panel/backend/server.py` (`SERVICE_META`)
- Legal credits for dependencies/images: `ATTRIBUTIONS.md`

## Guardrails

- Keep this repository generic: no app- or org-specific resource names.
- Maintain safe stop behavior; do not remove dependent-container warnings.
- Do not hardcode local paths or secrets.
- Keep command names centered on `services` and `cp`.
