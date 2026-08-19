<div align="center">

# UniFi Virtual Lab

**A web-based, protocol-faithful simulator for UniFi networks.**

Design topologies, spin up virtual devices, adopt them into any UniFi OS Server
controller, push configuration, and exercise simulated traffic flows — all
without touching real hardware.

[![CI](https://github.com/Comm4nd0/unifi-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/Comm4nd0/unifi-lab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange.svg)](#status)

</div>

---

> ### Where the code is
>
> The project has been restarted around a self-contained simulator. Everything
> current lives under [`vnet/`](vnet/) — a pure-python simulation engine, a
> Django REST API and a UniFi-style web console. Start there:
> **[vnet/README.md](vnet/README.md)**.
>
> The original `backend/` and `frontend/` trees (virtual devices adopted into a
> real UniFi OS Server over the inform protocol) are kept for reference and are
> no longer the active line of work. The notes below describe that earlier
> design.

## What is this?

UniFi Virtual Lab (UVL) is a self-hosted web application that lets you
simulate UniFi devices against a real UniFi OS Server controller. The
controller sees a real network. You see a sandbox.

- **Protocol-faithful virtual devices.** Virtual APs, switches, and
  gateways speak the genuine UniFi inform protocol. The controller can't
  tell the difference.
- **Declarative blueprints.** Describe sites, VLANs, WLANs, clients, and
  traffic profiles in YAML. Version them in git. Instantiate them against
  any controller.
- **Simulated traffic.** Generate flow records that populate the controller's
  Top Applications, DPI, client flow, and firewall views.
- **API-first.** Every UI action is a documented REST call. CI pipelines
  drive UVL headlessly.
- **Runs anywhere.** One container on your laptop, or a full split-service
  deployment on a server. Same code, same behaviour.
- **Mobile viewer** (Phase 5) — iOS and Android apps for monitoring on the go.

## Who is it for?

- Infrastructure engineers automating UniFi deployments.
- MSPs rehearsing customer site rollouts.
- Homelab operators testing destructive changes against a production-clone
  before applying them for real.
- Network trainers and learners without a rack of gear.
- Anyone building tools on top of the UniFi controller API who wants a
  deterministic test target.

## What it isn't

- **Not a data-plane emulator.** UVL reports flows to the controller; it
  does not route packets between virtual clients.
- **Not a UniFi controller.** You bring your own UniFi OS Server. UVL
  simulates the *devices*, not the controller.
- **Not a firmware reverse-engineering platform.** UVL reads firmware
  metadata to build device templates but never executes firmware code.

## Status

**Pre-alpha.** Under active design and early implementation. Not yet
production-ready. The protocol round-trip (Phase 0) is the current milestone.

## Quickstart — Local Mode

Requires Docker + Docker Compose v2, plus a UniFi OS Server to point UVL at.

```bash
git clone https://github.com/Comm4nd0/unifi-lab.git
cd unifi-lab

cp .env.example .env.local
./infra/scripts/generate-secrets.sh >> .env.local

docker compose -f infra/docker-compose.local.yml up -d

# First-time bootstrap
docker compose -f infra/docker-compose.local.yml exec app \
    python manage.py migrate
docker compose -f infra/docker-compose.local.yml exec app \
    python manage.py createsuperuser
```

Open http://localhost:8003.

## How it works

```
┌────────────────────┐      ┌──────────────────────┐
│  Web UI (React)    │      │  Mobile (Flutter)    │
└──────────┬─────────┘      └──────────┬───────────┘
           │                           │
           │     REST + WebSocket      │
           └────────────┬──────────────┘
                        │
             ┌──────────┴──────────┐
             │  Django + DRF +     │
             │  Channels + Celery  │
             └──────────┬──────────┘
                        │
               Redis + Postgres
                        │
             ┌──────────┴──────────┐
             │  Device Engine      │
             │  (asyncio worker)   │
             └──────────┬──────────┘
                        │  inform (TNBU, AES)
             ┌──────────┴──────────┐
             │  Your UniFi OS      │
             │  Server             │
             └─────────────────────┘
```

Django handles HTTP + WebSocket. A separate asyncio worker process runs the
virtual devices. Celery handles firmware ingestion. All three share Postgres
and Redis.

## Use it from CI

```python
from uvl_client import UVLClient

async with UVLClient("https://uvl.example.com", token=TOKEN) as uvl:
    fleet = await uvl.fleets.create(
        name=f"ci-{run_id}",
        blueprint_id=BLUEPRINT_ID,
        controller_target_id=CONTROLLER_ID,
    )
    await uvl.fleets.wait_for_state(fleet.id, "running", timeout=120)

    # ... push config via controller API, run your assertions ...

    await uvl.fleets.teardown(fleet.id)
```

## Development

```bash
# Backend (Django, Python 3.12, uv)
cd backend
uv sync --all-extras
uv run python manage.py migrate
uv run daphne -b 0.0.0.0 -p 8003 config.asgi:application

# In another terminal — device engine worker
cd backend
uv run python -m engine.main

# In another terminal — Celery worker
cd backend
uv run celery -A config worker -l info

# In another terminal — React frontend
cd frontend
npm install
npm run dev
```

## Contributing

Contributions welcome. Before opening a PR:

1. For non-trivial changes, open an issue first.
2. Architectural changes require an ADR.
3. Every PR runs lint, type-check, unit, integration, and contract tests. All must pass.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/). PRs are squash-merged.

## Security

UVL is a testing tool with significant capability: it can drive real
controllers, hold encrypted credentials for them, and generate traffic
against them. Treat UVL instances the same way you'd treat any other
privileged piece of network infrastructure.

## Licence

MIT. See [LICENSE](LICENSE). Documentation is CC BY 4.0.

UVL is not affiliated with, endorsed by, or sponsored by Ubiquiti Inc.
"UniFi" is a trademark of Ubiquiti Inc. UVL interoperates with Ubiquiti
software and hardware via publicly documented and reverse-engineered
protocols.

## Acknowledgements

- [jeffreykog/unifi-inform-protocol](https://github.com/jeffreykog/unifi-inform-protocol)
  for the reverse-engineered protocol documentation that makes this
  project possible.
- [Art-of-WiFi/UniFi-API-client](https://github.com/Art-of-WiFi/UniFi-API-client)
  as a reference for the controller API surface.
- [aiounifi](https://github.com/Kane610/aiounifi) for async Python patterns.
