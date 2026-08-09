# PhysicalAI LeHome Challenge Bridge

Bridge the **LeHome Challenge** Isaac Sim garment-folding environment to
PhysicalAI Studio as a bimanual SO-101 follower robot.

This is a uv workspace containing:

- [`packages/physicalai-lehome-challenge-bridge-plugin/`](packages/physicalai-lehome-challenge-bridge-plugin/README.md) — the plugin: a `Robot` driver that boots Isaac Sim + the garment env and serves it as a zenoh owner, an MJPEG camera server, and a Studio catalog registration (attach-only).
- [`sim/`](sim/README.md) — everything needed to boot the simulation: Dockerfile, compose file, and download/serve scripts.

## How it works

```
┌────────────────────────  sim host / container  ─────────────────────────┐
│ physicalai-lehome-challenge-bridge serve                                │
│  ├─ Isaac Sim SimulationApp (main process)                              │
│  ├─ GarmentEnv (LeHome-BiSO101-Direct-Garment-v2)                       │
│  ├─ zenoh owner loop (run_owner, in-process)  ── state/action ──┐       │
│  └─ MJPEG camera server (top/left_wrist/right_wrist)  ── HTTP ──┼─┐     │
└──────────────────────────────────────────────────────────────────┼─┼─────┘
                                                                   │ │
┌────────────────────────  Studio host  ───────────────────────────┴─┴─────┐
│ PhysicalAI Studio catalog plugin (this package)                           │
│  └─ SharedRobot.attach(name="lehome-garment")  ◄── zenoh ────────────────┘
│  └─ MJPEG streams at http://<sim>:8090/camera/{top,left_wrist,right_wrist}│
└───────────────────────────────────────────────────────────────────────────┘
```

Key design points:

- **SimulationApp stays in the main process.** Isaac Sim cannot be launched
  from the physicalai owner-worker subprocess, so the owner loop runs
  **in-process** via `run_owner` (the foreground pattern of `physicalai robot
  serve`).
- **Studio only attaches.** The catalog definition never spawns the sim; the
  user starts it. If it's not running, discovery/connection fails cleanly.
- **Cameras over MJPEG.** The robot transport carries only joint state, so the
  three garment cameras are streamed over plain HTTP (`multipart/x-mixed-replace`)
  instead of fake USB devices.

## Quick start

1. Install the plugin on the Studio host (Python ≥ 3.12):
   ```bash
   pip install physicalai-lehome-challenge-bridge-plugin physicalai-studio-plugin physicalai-bimanual-so101-plugin
   ```
2. Boot the simulation and serve it (see [`sim/README.md`](sim/README.md)):
   ```bash
   sim/scripts/download-assets.sh
   docker compose -f sim/docker-compose.yml build
   docker compose -f sim/docker-compose.yml up -d
   docker compose -f sim/docker-compose.yml exec lehome sim/scripts/serve.sh --garment-type top_long
   ```
3. In Studio, connect to robot type **LeHome Garment Follower** (name
   `lehome-garment`). Open the camera feeds at `http://<host>:8090/`.

## Development

```bash
uv sync --dev
uv run ruff check packages/
uv run pytest packages/physicalai-lehome-challenge-bridge-plugin/tests
```

The plugin package keeps `requires-python = ">=3.11"` so it installs on the
Isaac Sim container (Python 3.11). The Studio-only deps (`physicalai-studio-plugin`,
`physicalai-bimanual-so101-plugin`) require Python ≥ 3.12 and are imported
lazily, so the package works on both.
