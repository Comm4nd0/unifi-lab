# Claude Code Briefing — UniFi Virtual Lab (UVL)

You are helping build **UniFi Virtual Lab** (UVL), a web-based, protocol-faithful simulator for UniFi networks. Read this file at the start of every session. Re-read the _Current Phase_ and _Don'ts_ sections before proposing any non-trivial change.

## Project in one paragraph

UVL is a self-hosted web application that simulates UniFi devices (APs, switches, gateways) against a real UniFi OS Server controller. Virtual devices speak the genuine UniFi inform protocol, so the controller cannot distinguish them from real hardware. Users design networks as YAML blueprints, instantiate them as fleets against controllers, and exercise simulated traffic flows. Primary consumer: Marco's `Bare-Metal-Automation` CI pipeline.

## Owner and context

- **Owner:** Marco (@Comm4nd0). Infrastructure Automation Specialist, Royal Marines veteran, runs Chiltern View Farm.
- **Related projects in his ecosystem:** Bare Metal Automation (BMA), For Sale By Owner (FSBO — Django), Oakwood Climbing Gym (Django), PAWS 4 Thought Dogs (Django + Flutter), PedigreePro (Flutter).
- **Hosting target:** Luma001 — Marco's Hetzner VPS. Shared Caddy at `~/caddy/`.

## Stack

Do not deviate from these without proposing an ADR.

**Backend API:** Django 5 + Django REST Framework + drf-spectacular + Django Channels + djoser + SimpleJWT, served via Daphne (ASGI). Python 3.12. Package management: `uv`.

**Device engine:** Separate asyncio worker process. Not inside Django. Uses `httpx` for HTTP, `cryptography` for AES, SQLAlchemy 2.0 async for DB reads. Entry point: `python -m engine.main`.

**Background jobs:** Celery + Redis. Used only for firmware ingestion.

**Storage:** Postgres 16 (prod + local), Redis 7, MinIO in prod / filesystem in local mode.

**Web frontend:** React 19 + Vite + TypeScript + Tailwind + shadcn/ui + TanStack Query + TanStack Router + Zustand.

**Mobile (Phase 5):** Flutter 3.x + Dart, Riverpod state, dio + retrofit HTTP, viewer-only.

**Infra:** Docker + Docker Compose. Caddy as reverse proxy on Luma001.

## Repo layout (short)

```
backend/                # Django project
├── config/             # settings, ASGI, Celery, Channels routing
├── apps/               # Django apps: accounts, controllers, firmware,
│                       # blueprints, fleets, devices, traffic, audit, system
├── engine/             # SEPARATE PROCESS — asyncio device worker
│                       # Do NOT import engine.* from apps.*
├── manage.py
└── pyproject.toml

frontend/               # React SPA
mobile/                 # Flutter app (Phase 5+)
clients/{python,typescript}/  # Generated SDKs
infra/                  # Docker compose, Caddy snippet, scripts
schemas/                # JSON Schemas + OpenAPI snapshot
docs/                   # MkDocs Material
fixtures/               # Test fixtures (pcaps, firmware — gitignored)
```

## Ports on Luma001

Reserved and already in use on Marco's Hetzner box. **UVL uses 8003.** Do not suggest other ports.

| Port | Service                        |
| ---- | ------------------------------ |
| 8000 | PAWS 4 Thought Dogs            |
| 8001 | Oakwood Climbing Gym           |
| 8002 | For Sale By Owner (FSBO)       |
| 8003 | **UVL — reserved**             |

Caddy at `~/caddy/Caddyfile` reverse-proxies `172.17.0.1:8003` for UVL. A paste-ready snippet lives at `infra/caddy/uvl.snippet.caddyfile`.

## Current phase

**Phase 0 — Protocol Round Trip.**

Goal: a standalone Python script creates a virtual device, adopts it into a real UniFi OS Server, and maintains a heartbeat for ≥30 minutes. No web UI, no DB, no fleets.

Deliverables:
- `backend/engine/protocol/` — TNBU codec with AES-128-CBC and AES-128-GCM support.
- `backend/engine/device.py` — minimum `VirtualDevice` with state machine.
- `backend/engine/scripts/solo_device.py` — the smoke test entrypoint.
- Unit tests against pcap fixtures under `backend/tests/fixtures/pcaps/`.

**Do not** start Phase 1 work (Django API, React) until the Phase 0 exit criteria are met.

**Current scaffold state:** all structure exists but protocol/crypto/codec modules are interface-only stubs raising `NotImplementedError`. Real implementation awaits captured pcaps.

## Coding conventions

- **Python:** Ruff (lint + format), `mypy --strict` where feasible, type hints on all public functions.
- **Commits:** Conventional Commits. Scope encouraged: `feat(protocol):`, `fix(engine):`.
- **PRs:** One concern per PR. Description links the use case or ADR.
- **Tests:** Unit tests first for `engine/protocol/`. Integration tests gated on fixture availability.
- **Secrets:** Never commit. Never log. Use `cryptography.Fernet` for at-rest.
- **Logging:** `structlog`, JSON output, request/session correlation ID.
- **Imports:** Ordered by ruff isort. No `from x import *`.
- **Async:** `async`/`await` throughout the engine. No sync HTTP calls, no `requests` library.
- **DB in engine:** SQLAlchemy 2.0 async only. Never import Django ORM from `engine/`.
- **DB in Django:** Django ORM. Services wrap domain logic; views stay thin.

## Don'ts

These are not stylistic preferences. Deviating from any of these is a reason to pause and ask Marco first.

- **Don't add new top-level dependencies without proposing them in the PR description.** Every new package is a maintenance commitment.
- **Don't touch Alembic** unless Marco confirms — UVL is Django-migrations-first.
- **Don't run `makemigrations`** without scanning the diff and explaining it.
- **Don't run `migrate`** in production or shared environments.
- **Don't reach for Celery** for anything that isn't genuinely fire-and-forget.
- **Don't import `engine.*` from `apps.*`** or vice versa, except the narrowly-scoped `engine.clients` interface.
- **Don't use Django async views** for hot endpoints unless benchmarks justify it.
- **Don't mix ORM layers** — Django ORM in Django code, SQLAlchemy async in engine.
- **Don't assume AES-CBC is sufficient.** Newer firmware uses AES-GCM; support both.
- **Don't generate synthetic inform captures for tests** when real ones exist.
- **Don't expose Django Admin publicly** without explicit confirmation.
- **Don't add Kubernetes, gRPC, GraphQL, Kafka, or multi-tenancy** — rejected for v1.
- **Don't log inform keys, JWTs, passwords, or controller credentials** at any level.
- **Don't use `requests`, `aiohttp`, or `urllib3` directly.** Standard is `httpx` (async).

## Do's

- **Do read the current phase note before touching anything new.**
- **Do use TodoWrite-style planning** for multi-step work; one commit per logical step.
- **Do write tests first** for `engine/protocol/`. Zero forgiveness for regressions.
- **Do prefer small PRs** stacked toward a phase goal.
- **Do reference the vault** when making structural decisions. Vault > README > memory.
- **Do ask before introducing a new service** (new container, new queue, new external dependency).
- **Do update the OpenAPI snapshot** when you change the API. CI checks it.
- **Do regenerate client SDKs** after API changes: Python, TypeScript, (Dart in Phase 5).
- **Do run `uv run ruff check . && uv run mypy . && uv run pytest`** before declaring a task done.

## Key vault references

Marco maintains a design vault in Obsidian, which is the authoritative design source. The notes you'll reference most:

- `Tech/30 - Stack Decisions` — why Django, why worker, why Flutter.
- `Tech/31 - Data Model` — schema authoritative.
- `Tech/32 - API Design` — endpoint contracts.
- `Tech/33 - WebSocket Protocol` — WS message envelope and channels.
- `Components/20..30` — per-component specs.
- `References/50 - Inform Protocol Notes` — wire format, encryption, payload keys.
- `Decisions/ADR-0001..0010` — architectural decisions (ADR-0001 superseded by ADR-0008).

If the vault and the code disagree, the vault is usually the intent and the code the drift — raise it.

## Working with Marco

- **He's technical.** Full CLI comfort, Django veteran, runs his own infra.
- **He prefers concise answers over exhaustive ones.** Lead with the recommendation and cost, not the decision tree.
- **He ships.** He'll push back on over-engineering and deferred value.
- **Time zone:** UK (BST / GMT).
- **Hardware:** Chiltern View has a real UniFi Dream Machine setup — real captures available.

## When you're unsure

1. Check the vault note for the relevant component or phase.
2. Check the relevant ADR.
3. If still unclear, **ask in the PR or commit message** rather than guessing.
4. Prefer making the question explicit in code comments (`# TODO: confirm X with Marco`) over silent choices.

## Non-trivial decisions you may face and the expected answer

- "Should this live in Django or the worker?" — If it's about HTTP requests, users, or business rules, Django. If it's about a running virtual device, worker. If ambiguous, surface the question.
- "Should this be Celery or asyncio?" — Celery for genuinely one-shot, forgettable background work. Asyncio for anything stateful or long-lived.
- "Should this be in a model or a service?" — Django models hold state and simple accessors. Services hold logic. No fat models.
- "Can I add `foo` library?" — If it isn't already in `pyproject.toml`, propose first.
- "Should this endpoint be async?" — Default to sync under ASGI. Only async if benchmarks warrant.

## Session start checklist

Each session, before writing code:

1. [ ] Run `git status` and `git log -5` to see where the tree is.
2. [ ] Read this file if it's been more than a session since you last did.
3. [ ] Read the current phase note in the Obsidian vault.
4. [ ] Identify which component you're touching and re-read its spec.
5. [ ] Plan the change; one commit per logical step.
