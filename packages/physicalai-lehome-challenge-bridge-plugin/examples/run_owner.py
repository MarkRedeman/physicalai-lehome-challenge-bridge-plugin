"""Launch the LeHome garment simulation as a zenoh robot owner.

Programmatic equivalent of ``physicalai-lehome-challenge-bridge serve``,
useful when embedding the owner loop in an existing script.

Usage:
    uv run python examples/run_owner.py [--name <name>] [--garment-type <type>]

The owner runs in the current process (required by Isaac Sim's SimulationApp)
and blocks until SIGINT/SIGTERM. Studio attaches to it by name.
"""

from __future__ import annotations

import argparse
import signal
import threading

from loguru import logger
from physicalai.config import to_config
from physicalai.robot.transport import OwnerEvent, RobotOwnerConfig, run_owner

from physicalai_lehome_challenge_bridge_plugin.env_bootstrapper import SimLaunchConfig
from physicalai_lehome_challenge_bridge_plugin.lehome_robot import LeHomeGarmentRobot


def main() -> None:
    """Run the owner loop with the given options."""
    parser = argparse.ArgumentParser(description="Run LeHome garment env as a zenoh owner")
    parser.add_argument("--name", type=str, default="lehome-garment", help="Zenoh robot name")
    parser.add_argument(
        "--garment-type",
        type=str,
        default="top_long",
        choices=["top_long", "top_short", "pant_long", "pant_short", "custom"],
    )
    parser.add_argument("--headless", action="store_true", help="Run without a viewport")
    parser.add_argument("--rate-hz", type=float, default=90.0, help="Owner loop rate")
    parser.add_argument("--allow-remote", action="store_true", help="Allow remote zenoh")
    args = parser.parse_args()

    sim_config = SimLaunchConfig(garment_type=args.garment_type, headless=args.headless)
    robot = LeHomeGarmentRobot(sim_config.as_dict())

    config = RobotOwnerConfig(
        name=args.name,
        robot=to_config(robot),
        allow_remote=args.allow_remote,
        rate_hz=args.rate_hz,
        idle_timeout=None,
    )

    shutdown = threading.Event()

    def _signal_handler(signum: int, frame: object) -> None:
        _ = signum, frame
        shutdown.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    def _ready() -> None:
        logger.success(f"Serving robot {config.name!r} at {config.rate_hz:g} Hz")

    def _on_event(event: OwnerEvent) -> None:
        logger.info("Owner event: {}", event)

    try:
        run_owner(config, shutdown, ready=_ready, on_event=_on_event)
    except KeyboardInterrupt:
        pass
    logger.info("Owner stopped")


if __name__ == "__main__":
    main()
