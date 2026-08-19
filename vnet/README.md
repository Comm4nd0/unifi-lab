# UniFi Virtual Lab

Build a UniFi network that does not exist, then find out what it would do.

Pick hardware from the UniFi catalogue, patch it together port by port, hang
clients and traffic off it, and the simulator tells you what the network does:
which ports spanning tree blocks, where a loop would take you down, which
uplink saturates first, and which access point runs out of PoE budget. The
console is laid out like the UniFi Network application, so what you learn here
transfers to the real thing.

```
┌──────────────┐    REST     ┌───────────────┐    calls    ┌─────────────┐
│  console     │ ──────────► │  netsim       │ ──────────► │  simcore    │
│  React 19    │ ◄────────── │  Django + DRF │ ◄────────── │  pure python│
└──────────────┘   JSON      └───────────────┘   results   └─────────────┘
```

`simcore` has no framework dependency at all. It takes a description of a site
and returns spanning tree state, PoE budgets, per-link load and a ranked list of
problems. `netsim` persists sites and exposes them over HTTP. The console draws
the result and lets you change it.

## Running it

Everything runs from one process on port 8003.

```bash
cd vnet/frontend && npm install && npm run build   # builds into ../backend/web
cd ../backend
uv venv && uv pip install -e ".[dev]"
uv run python manage.py migrate
uv run python manage.py seed_demo                  # optional example site
uv run python manage.py runserver 0.0.0.0:8003
```

Open <http://localhost:8003>. The API is at `/api/`, the schema at
`/api/schema/`, and Swagger UI at `/api/docs/`.

For frontend work, run Vite separately — it proxies `/api` to port 8003:

```bash
cd vnet/frontend && npm run dev     # http://localhost:5173
```

With Docker:

```bash
cd vnet && docker compose up --build
```

## What is simulated

**Hardware.** 46 models across gateways, switches, access points and Protect
gear, each with its real port complement — RJ45 and SFP cages, per-port speeds,
which ports source PoE and to which standard, PoE budgets and power draw.
Adding a device materialises every one of its ports, and only ports that
physically exist can be patched.

**Cabling.** Copper goes to copper, fibre to fibre. A link negotiates to the
slowest of the two ports and the cable grade, so Cat5e between two 10G SFP+
ports is flagged rather than silently ignored.

**Spanning tree.** A single-instance RSTP/STP model. Bridges are elected by
priority then MAC, path costs follow the 802.1D-2004 table, and ports come out
as root, designated, alternate or backup. Devices that cannot run STP — access
points, cameras, or a switch where you turned it off — are modelled as hubs:
every cable into them merges into one shared segment. That is what makes a
loop through an unmanaged device show up here exactly as it does in real life,
because nothing in that path can block a port.

It reports live forwarding loops, blocked and backup ports, BPDU guard
violations, root bridge elections decided by MAC address, an access-layer
switch winning the root election, isolated segments, and legacy 802.1D's
30-second convergence.

**Power.** Which switch port feeds each powered device, whether the standard is
sufficient (an 802.3at access point on an 802.3af port does not boot), per-port
watts, and per-switch budgets. A PoE-powered switch losing its feed takes
everything downstream with it, iteratively.

**Traffic.** Flows are placed on the topology spanning tree actually left
forwarding, so a blocked port carries nothing. When a link is oversubscribed
every flow crossing it backs off by the same factor, which is close enough to
what TCP does to a saturated uplink. Wireless clients consume AP airtime,
internet flows are capped by the WAN circuit, and a live loop pegs every link
in it at 100% with a broadcast storm.

Numbers are engineering approximations, not a packet-level simulator. They are
right about ordering, saturation points and failure modes — not about the third
decimal place.

## Layout

```
vnet/
├── backend/
│   ├── simcore/          # framework-free simulation engine
│   │   ├── catalog.py    #   hardware catalogue (data/catalog.json)
│   │   ├── topology.py   #   site graph, cabling rules
│   │   ├── stp.py        #   spanning tree
│   │   ├── power.py      #   PoE
│   │   ├── traffic.py    #   flow placement and capacity
│   │   └── engine.py     #   ties it together
│   ├── netsim/           # Django app: models, services, DRF views
│   ├── config/           # Django project
│   └── tests/            # pytest — engine and API
└── frontend/             # React console
```

## Adding hardware

Models live in `backend/simcore/data/catalog.json`. Ports are declared as
groups and expanded into individually addressable ports at load time:

```json
{
  "key": "usw-pro-24-poe",
  "name": "Switch Pro 24 PoE",
  "line": "switch",
  "poe_budget_w": 400,
  "ports": [
    {"count": 16, "start": 1, "label": "Port {n}", "media": "rj45",
     "speed_mbps": 1000, "poe_out": "802.3at", "poe_max_w": 30},
    {"count": 2, "start": 25, "label": "SFP+ {n}", "media": "sfp+",
     "speed_mbps": 10000, "role": "uplink"}
  ]
}
```

Adding a model is a data change. No code, no migration.

## Blueprints

A whole site exports to JSON (or YAML) and imports back as a copy —
`GET /api/sites/{id}/blueprint/` and `POST` the same path. Useful for fixtures,
for sharing a topology, and for driving the lab from CI.

## Tests

```bash
cd vnet/backend
uv run pytest            # engine + API
uv run ruff check .
uv run mypy simcore netsim
cd ../frontend && npx tsc --noEmit
```
