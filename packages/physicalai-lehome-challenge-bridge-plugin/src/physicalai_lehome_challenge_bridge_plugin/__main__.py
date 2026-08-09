"""CLI entrypoint for the LeHome challenge bridge.

Usage:

    physicalai-lehome-challenge-bridge serve --name lehome-garment [options]

Boots Isaac Sim + the LeHome garment environment in the *current* process,
then runs the zenoh robot owner loop (``run_owner``) in-process so
``SimulationApp`` stays in the main process — the physicalai owner-worker
subprocess model cannot be used because Isaac Sim must own the main process.
Studio attaches to this owner; if the process is not running, Studio's
connection fails cleanly.
"""

from __future__ import annotations

import argparse
import signal
import threading

from loguru import logger
from physicalai.config import to_config
from physicalai.robot.transport import OwnerEvent, RobotOwnerConfig, run_owner

from physicalai_lehome_challenge_bridge_plugin._frame_store import get_default_store
from physicalai_lehome_challenge_bridge_plugin.camera_server import MjpegCameraServer
from physicalai_lehome_challenge_bridge_plugin.constants import DEFAULT_CAMERA_PORT, DEFAULT_ROBOT_NAME
from physicalai_lehome_challenge_bridge_plugin.env_bootstrapper import SimLaunchConfig
from physicalai_lehome_challenge_bridge_plugin.lehome_robot import LeHomeGarmentRobot


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="physicalai-lehome-challenge-bridge",
        description="Bridge the Isaac Sim LeHome challenge environment to PhysicalAI Studio",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Boot Isaac Sim + garment env and serve it as a zenoh owner")
    serve.add_argument(
        "--name",
        type=str,
        default=DEFAULT_ROBOT_NAME,
        help=f"Zenoh robot name (default: {DEFAULT_ROBOT_NAME})",
    )
    serve.add_argument(
        "--garment-type",
        type=str,
        default="top_long",
        choices=["top_long", "top_short", "pant_long", "pant_short", "custom"],
        help="Garment category to load (default: top_long)",
    )
    serve.add_argument(
        "--garment-name",
        type=str,
        default=None,
        help="Explicit garment name (e.g. Top_Long_Unseen_0); default picks the first from the eval list",
    )
    serve.add_argument(
        "--garment-version",
        type=str,
        default="Release",
        help="Garment version folder: Release or Holdout (default: Release)",
    )
    serve.add_argument(
        "--garment-cfg-base-path",
        type=str,
        default="Assets/objects/Challenge_Garment",
        help="Base path of the garment configurations",
    )
    serve.add_argument(
        "--particle-cfg-path",
        type=str,
        default="source/lehome/lehome/tasks/bedroom/config_file/particle_garment_cfg.yaml",
        help="Path of the particle configuration",
    )
    serve.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run Isaac Sim without a viewport window",
    )
    serve.add_argument(
        "--no-cameras",
        action="store_true",
        default=False,
        help="Disable camera rendering and the MJPEG camera server",
    )
    serve.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Simulation device: cuda or cpu (default: cuda)",
    )
    serve.add_argument(
        "--rate-hz",
        type=float,
        default=90.0,
        help="Owner control loop rate in Hz (default: 90, matching sim dt=1/90)",
    )
    serve.add_argument(
        "--camera-port",
        type=int,
        default=DEFAULT_CAMERA_PORT,
        help=f"MJPEG camera HTTP port (default: {DEFAULT_CAMERA_PORT})",
    )
    serve.add_argument(
        "--allow-remote",
        action="store_true",
        default=False,
        help="Allow remote zenoh connections (default: loopback only)",
    )
    return parser


def _start(args: argparse.Namespace) -> int:
    enable_cameras = not args.no_cameras
    sim_config = SimLaunchConfig(
        garment_type=args.garment_type,
        garment_name=args.garment_name,
        garment_version=args.garment_version,
        garment_cfg_base_path=args.garment_cfg_base_path,
        particle_cfg_path=args.particle_cfg_path,
        headless=args.headless,
        enable_cameras=enable_cameras,
        device=args.device,
    )
    robot = LeHomeGarmentRobot(sim_config.as_dict(), enable_cameras=enable_cameras)

    config = RobotOwnerConfig(
        name=args.name,
        robot=to_config(robot),
        allow_remote=args.allow_remote,
        rate_hz=args.rate_hz,
        idle_timeout=None,
    )

    camera_server: MjpegCameraServer | None = None
    if enable_cameras:
        camera_server = MjpegCameraServer(
            get_default_store(["top", "left_wrist", "right_wrist"]),
            port=args.camera_port,
        )
        camera_server.start()

    shutdown = threading.Event()

    def _signal_handler(signum: int, frame: object) -> None:
        _ = signum, frame
        logger.info("Shutdown requested")
        shutdown.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    def _ready() -> None:
        logger.success(f"Serving robot {config.name!r} at {config.rate_hz:g} Hz")

    def _on_event(event: OwnerEvent) -> None:
        logger.info("Owner event: {}", event)

    logger.info("Booting Isaac Sim + LeHome garment environment ...")
    try:
        result = run_owner(config, shutdown, ready=_ready, on_event=_on_event)
    except KeyboardInterrupt:
        result = None
    finally:
        if camera_server is not None:
            camera_server.stop()
    logger.info("Bridge stopped (reason={})", result)
    return 0


def main() -> None:
    """Parse command-line arguments and run the requested command.

    Raises:
        SystemExit: Always, with the serve exit code or 1 for usage errors.

    """
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        raise SystemExit(_start(args))
    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
