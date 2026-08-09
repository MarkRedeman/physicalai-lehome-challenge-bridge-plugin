"""LeHome Challenge bridge plugin for PhysicalAI Studio."""

# ruff: file-ignore[import-outside-top-level] -- lazy imports keep the package importable without Isaac Sim

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from physicalai_lehome_challenge_bridge_plugin.lehome_robot import (
        LeHomeGarmentObservation as LeHomeGarmentObservation,
    )
    from physicalai_lehome_challenge_bridge_plugin.lehome_robot import (
        LeHomeGarmentRobot as LeHomeGarmentRobot,
    )

__all__ = [
    "LeHomeGarmentObservation",
    "LeHomeGarmentRobot",
]


def __getattr__(name: str) -> object:
    if name == "LeHomeGarmentRobot":
        from physicalai_lehome_challenge_bridge_plugin.lehome_robot import (
            LeHomeGarmentRobot,
        )

        return LeHomeGarmentRobot
    if name == "LeHomeGarmentObservation":
        from physicalai_lehome_challenge_bridge_plugin.lehome_robot import (
            LeHomeGarmentObservation,
        )

        return LeHomeGarmentObservation
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
