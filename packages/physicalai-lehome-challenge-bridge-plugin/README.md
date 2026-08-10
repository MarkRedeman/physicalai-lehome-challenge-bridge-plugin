# PhysicalAI LeHome Challenge Bridge Plugin

Bridges the **LeHome Challenge** Isaac Sim garment-folding environment to
PhysicalAI Studio as a bimanual SO-101 follower robot.

- Run a virtual SO-101 (garment folding) robot inside Isaac Sim.
- Teleoperate / monitor it from PhysicalAI Studio exactly like real hardware.
- Stream the three garment cameras (top, left wrist, right wrist) as
  **MJPEG-over-HTTP** feeds — no fake USB devices needed.
- Studio **only attaches** to an already-running simulation. The user starts
  Isaac Sim; if it is not running, connection fails cleanly.

## Architecture

```text
┌───────────────────────────  sim host / container  ───────────────────────────┐
│ physicalai-lehome-challenge-bridge serve                                     │
│  ├─ Isaac Sim SimulationApp (main process)                                    │
│  ├─ GarmentEnv (LeHome-BiSO101-Direct-Garment-v2)                             │
│  ├─ zenoh owner loop (run_owner, in-process)  ── state/action ──┐            │
│  └─ MJPEG camera server (top/left_wrist/right_wrist)  ── HTTP ──┼─┐          │
└───────────────────────────────────────────────────────────────────┼─┼──────────┘
                                                                     │ │
┌───────────────────────────  Studio host  ─────────────────────────┴─┴────────┐
│ PhysicalAI Studio catalog plugin (this package)                              │
│  └─ SharedRobot.attach(name="lehome-garment")  ◄── zenoh ────────────────────┘
│  └─ MJPEG streams at http://<sim>:8090/camera/{top,left_wrist,right_wrist}    │
└──────────────────────────────────────────────────────────────────────────────┘
```

The key design constraint: `SimulationApp` must live in the **main process**,
so the zenoh owner loop runs **in-process** via `run_owner` (the foreground
pattern used by `physicalai robot serve`), not the detached owner-worker
subprocess used by the MuJoCo plugin.

## Quick start

### 1. Start the simulation (the user's job)

See [`sim/`](../../sim/README.md) for the containerized setup (recommended) or the
host-level scripts. In short:

```bash
# inside the sim environment (container or host with Isaac Sim + lehome):
physicalai-lehome-challenge-bridge serve \
    --name lehome-garment \
    --garment-type top_long \
    --allow-remote
```

### 2. Connect from PhysicalAI Studio

Open Studio and connect to robot type **LeHome Garment Follower** with name
`lehome-garment` (the default). Studio attaches to the running owner; if the
sim is not running, the probe reports it offline.

### 3. View cameras

The MJPEG feeds are at:

- `http://<sim-host>:8090/camera/top`
- `http://<sim-host>:8090/camera/left_wrist`
- `http://<sim-host>:8090/camera/right_wrist`

`http://<sim-host>:8090/` lists all available streams.

## CLI

```bash
physicalai-lehome-challenge-bridge serve --help
```

Common options:

- `--name <name>`: zenoh robot name (default `lehome-garment`)
- `--garment-type <type>`: `top_long` | `top_short` | `pant_long` | `pant_short` | `custom`
- `--headless`: run without a viewport window
- `--no-cameras`: disable camera rendering and the MJPEG server
- `--camera-port <port>`: MJPEG HTTP port (default `8090`)
- `--rate-hz <hz>`: owner loop rate (default `90`, matching sim `dt=1/90`)
- `--allow-remote`: allow zenoh connections beyond localhost

## Studio catalog integration

The package registers a `physicalai.studio.catalog_plugins` entry point so
Studio discovers the robot type automatically when the plugin is installed on
the Studio host. The catalog definition is **attach-only** — it never spawns
the simulation.

## Controlling the running simulation

While the simulation is live, you can reset the scene or switch garments from
the host via the MJPEG server's `POST /control` endpoint (port `8090`):

```bash
# Reset the scene: re-home the robot and re-settle the current garment
curl -X POST http://localhost:8090/control -d '{"cmd":"reset"}'

# Switch to a specific garment by name
curl -X POST http://localhost:8090/control -d '{"cmd":"switch","name":"Top_Long_Seen_3"}'

# Advance to the next garment in the evaluation list (wraps around)
curl -X POST http://localhost:8090/control -d '{"cmd":"next"}'
```

Each request returns a JSON body with the current state, e.g.:

```json
{
  "ok": true,
  "current_garment": "Top_Long_Seen_3",
  "garment_index": 3,
  "num_garments": 12
}
```

Commands are applied by the owner loop on its next control tick (they are
queued and drained single-threaded, so there are no races with Isaac Sim).

## Development

```bash
uv sync --dev
uv run ruff check packages/
uv run pytest packages/physicalai-lehome-challenge-bridge-plugin/tests
```
