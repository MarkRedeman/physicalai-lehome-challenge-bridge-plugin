# LeHome Challenge simulation bootup

Everything needed to boot the Isaac Sim LeHome garment environment and serve
it to PhysicalAI Studio. The containerized setup is the main entry point;
host-level scripts are a fallback if container performance is inadequate.

## Prerequisites

- Docker ≥ 27 with Compose v2 and BuildKit (default)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- **Host NVIDIA driver on the R580 branch** (`580.x`). Isaac Sim 5.1.0 is only
  validated against R580; newer branches (R590/R595/R610) segfault in
  `librtx.scenedb` during startup. Check with `nvidia-smi --query-gpu=driver_version`.
- ~40 GB free disk for the build.

## Quick start (Docker, recommended)

### 1. Download assets + example dataset (host side)

```bash
sim/scripts/download-assets.sh     # Assets/ + Datasets/example
```

### Where do Assets and Datasets come from?

The simulation needs two data sets that are **not bundled** in this repo or
in the Docker image. They are downloaded from the LeHome Challenge's public
Hugging Face repos by `sim/scripts/download-assets.sh`:

| Directory           | Hugging Face repo                           | Contents                                                  |
| ------------------- | ------------------------------------------- | --------------------------------------------------------- |
| `Assets/`           | `lehome/asset_challenge` (dataset)          | Garment meshes + scene/robot USD assets used by Isaac Sim |
| `Datasets/example/` | `lehome/dataset_challenge_merged` (dataset) | Example demonstration episodes (episode_data, videos, …)  |

Both are **mounted into the container** at `/workspace/Assets` and
`/workspace/Datasets` via `docker-compose.yml` — they are never baked into
the image, so you can point the volumes at data you already downloaded
elsewhere by editing the compose file.

Requirements for the download script: the Hugging Face CLI
(`pip install -U "huggingface_hub[cli]"`). The script is resumable — re-run
it any time to pick up where it left off.

> If you already have the LeHome Challenge `Assets/` and `Datasets/` from the
> original challenge repo, copy or symlink them into this repo's
> `Assets/` / `Datasets/` directories (or update the volume mounts in
> `sim/docker-compose.yml` to point at them) and skip the download.

### 2. Build and start

```bash
docker compose -f sim/docker-compose.yml build
docker compose -f sim/docker-compose.yml up -d
```

The container stays alive (`sleep infinity`). Assets and datasets are mounted
from `../Assets` and `../Datasets`; the zenoh transport port (default
`lehome-garment` → `35869`) and the MJPEG camera port (`8090`) are published
so Studio on the host can reach them.

### 3. Start the bridge

```bash
docker compose -f sim/docker-compose.yml exec lehome sim/scripts/serve.sh \
    --name lehome-garment \
    --garment-type top_long \
    --allow-remote
```

This boots Isaac Sim + the garment env, starts the MJPEG camera server, and
runs the zenoh owner loop **in the same process**. Keep it running while you
work in Studio.

### 4. Connect from PhysicalAI Studio

Connect to robot type **LeHome Garment Follower** with name `lehome-garment`.
Studio attaches to the running owner — it never spawns the sim. If the sim is
not running, the probe reports it offline and connection fails cleanly.

Camera feeds (open in a browser or VLC):

- `http://<host>:8090/camera/top`
- `http://<host>:8090/camera/left_wrist`
- `http://<host>:8090/camera/right_wrist`

## Controlling the running simulation

While the sim is live, reset the scene or switch garments from the host via
the MJPEG server's `POST /control` endpoint (port `8090`, published to the
host):

```bash
# Reset the scene: re-home the robot and re-settle the current garment
curl -X POST http://localhost:8090/control -d '{"cmd":"reset"}'

# Switch to a specific garment by name
curl -X POST http://localhost:8090/control -d '{"cmd":"switch","name":"Top_Long_Seen_3"}'

# Advance to the next garment in the evaluation list (wraps around)
curl -X POST http://localhost:8090/control -d '{"cmd":"next"}'
```

Responses include the current state, e.g.
`{"ok": true, "current_garment": "Top_Long_Seen_3", "garment_index": 3, "num_garments": 12}`.
Commands are queued and applied by the owner loop on its next tick.

## Headless vs GUI

- `--headless`: no Isaac Sim viewport window (cameras still render). Good for
  servers.
- Without `--headless`: a viewport opens on the host display via X11. The
  compose file forwards `DISPLAY`, `$XAUTHORITY` and `/tmp/.X11-unix`; if the
  window doesn't appear, run `xhost +local:root` on the host.

## Host-level fallback (`serve-host.sh`)

If container performance is insufficient, install Isaac Sim + lehome directly
on a Linux host and use:

```bash
uv sync --group sim
sim/scripts/serve-host.sh --name lehome-garment --garment-type top_long
```

The host needs the same R580 driver, IsaacLab fork install (`isaaclab.sh -i
none` with the known fixes), the `lehome` package from the lehome-challenge
repo, and `Assets/` + `Datasets/` in this repo. See the plugin README for the
known build fixes.

## Ports

| Port  | Used for                                                                                                                                                |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 35869 | Zenoh robot transport (`lehome-garment`). The deterministic port derives from the robot name; change `--name` and update `docker-compose.yml` together. |
| 8090  | MJPEG camera HTTP server (3 endpoints)                                                                                                                  |

## Troubleshooting

- **Segfault in `librtx.scenedb.plugin.so`**: host driver is newer than R580.
  Downgrade to `nvidia-driver-580` and reboot.
- **`Authorization required` / no window**: run `xhost +local:root` on the host,
  or use `--headless`.
- **pynput X connection error**: ensure Xvfb is available (installed in the
  image; `serve.sh` starts it automatically) or a real `DISPLAY` is set.
- **GPU not visible**: `docker compose -f sim/docker-compose.yml exec lehome nvidia-smi`.
