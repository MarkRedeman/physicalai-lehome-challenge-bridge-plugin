"""PhysicalAI Studio catalog registration for the LeHome garment simulation.

The simulated robot is a bimanual SO-101 follower running inside Isaac Sim.
Studio only ever *attaches* to an existing owner (the sim must be started by
the user, e.g. ``physicalai-lehome-challenge-bridge serve``); this plugin
never spawns the simulation. If the owner is not reachable, discovery and
connection fail cleanly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from physicalai.config import export_config
from physicalai_studio_plugin import (
    CatalogRobotFactory,
    PayloadContainer,
    PortScanner,
    RobotAdapterOptions,
    RobotAsset,
    RobotCatalogDefinition,
    RobotProbe,
    SerialPortInfo,
)
from pydantic import BaseModel, Field

from physicalai_lehome_challenge_bridge_plugin._urdf import get_urdf_path
from physicalai_lehome_challenge_bridge_plugin.constants import DEFAULT_ROBOT_NAME, JOINT_ORDER

if TYPE_CHECKING:
    from typing import Protocol

    import numpy as np
    from physicalai.robot.interface import Robot as PhysicalAIRobot
    from physicalai.robot.interface import RobotObservation
    from physicalai.robot.transport import SharedRobot

    class _RobotCatalogRegistry(Protocol):
        def register_robot(self, definition: RobotCatalogDefinition) -> None: ...


# Map physicalai joint names (left_*/right_*) to the URDF joints.
_LEHOME_TO_URDF: dict[str, list[str]] = {name: [name] for name in JOINT_ORDER}


_LEHOME_ASSET = RobotAsset(
    urdf_relative_path=Path("so101_dual/so101_dual.urdf"),
    packages={"so101_dual": Path("so101_dual")},
    joint_map=_LEHOME_TO_URDF,
    root_resolver=get_urdf_path,
)


class LeHomeGarmentPayload(BaseModel):
    """Connection settings for the running LeHome garment simulation owner."""

    name: str = Field(
        default=DEFAULT_ROBOT_NAME,
        description="Zenoh logical robot name of the running Isaac Sim simulation",
    )
    allow_remote: bool = Field(
        default=False,
        description="Allow connecting to a zenoh owner beyond localhost",
    )
    connect_timeout: float = Field(
        default=10.0,
        description="Timeout in seconds for connecting to the zenoh owner",
    )


class LeHomeGarmentProbe(RobotProbe[LeHomeGarmentPayload]):
    """Discover and query running LeHome garment simulation owners."""

    async def discover(self, manager: PortScanner) -> list[SerialPortInfo]:
        """Return robots found by the port scanner (none for a sim).

        Returns:
            Detected robots (empty for a simulation).

        """
        _ = self
        await manager.find_robots()
        return manager.robots

    async def identify(
        self,
        payload: LeHomeGarmentPayload,
        manager: PortScanner | None = None,
        joint: str | None = None,
    ) -> None:
        """Perform no visual identification for the simulated robot."""
        _ = self, payload, manager, joint

    async def is_online(
        self,
        payload: LeHomeGarmentPayload,
        manager: PortScanner | None = None,
    ) -> bool:
        """Return whether the configured simulation owner is reachable.

        Returns:
            True if the zenoh owner answers a metadata probe.

        """
        _ = self, manager
        return await asyncio.to_thread(_check_zenoh_robot_online, payload.name)


def _check_zenoh_robot_online(name: str) -> bool:
    from physicalai.robot.transport import SharedRobot  # ruff: ignore[import-outside-top-level]

    try:
        robot = SharedRobot.attach(name=name, connect_timeout=2.0)
        robot.connect()
        robot.disconnect()
    except (ConnectionError, TimeoutError, RuntimeError):
        return False
    else:
        return True


_LEHOME_PROBE = LeHomeGarmentProbe()


@export_config(class_path="physicalai_lehome_challenge_bridge_plugin.studio_catalog._SharedLeHomeRobot")
class _SharedLeHomeRobot:
    """Adapter exposing a shared (zenoh) owner through the Robot protocol."""

    def __init__(self, shared_robot: SharedRobot) -> None:
        self._shared_robot = shared_robot
        self.joint_names = list(JOINT_ORDER)

    @property
    def device_ids(self) -> tuple[str, ...]:
        """The attached Isaac Sim owner, not this wrapper, owns the sim."""
        return ()

    def connect(self) -> None:
        self._shared_robot.connect()

    def disconnect(self) -> None:
        self._shared_robot.disconnect()

    def get_observation(self) -> RobotObservation:
        return self._shared_robot.get_observation()

    def send_action(self, action: np.ndarray, *, goal_time: float = 0.1) -> None:
        self._shared_robot.send_action(action, goal_time=goal_time)

    def is_connected(self) -> bool:
        return self._shared_robot.is_connected()


async def _build_lehome_robot(
    robot: PayloadContainer[LeHomeGarmentPayload],
    factory: CatalogRobotFactory,
) -> PhysicalAIRobot:
    """Attach to the running simulation owner (never spawns it).

    Returns:
        A robot adapter wrapping the attached shared owner.

    """
    _ = factory
    await asyncio.sleep(0)
    raw = robot.payload
    validated = raw if isinstance(raw, LeHomeGarmentPayload) else LeHomeGarmentPayload.model_validate(raw)

    from physicalai.robot.transport import SharedRobot  # ruff: ignore[import-outside-top-level]

    shared = SharedRobot.attach(
        name=validated.name,
        allow_remote=validated.allow_remote,
        connect_timeout=validated.connect_timeout,
    )
    return _SharedLeHomeRobot(shared)


def _definitions() -> list[RobotCatalogDefinition]:
    return [
        RobotCatalogDefinition(
            type="LeHome_Garment_Follower",
            display_name="LeHome Garment Follower",
            role="follower",
            robot_builder=_build_lehome_robot,
            robot_payload=LeHomeGarmentPayload,
            asset=_LEHOME_ASSET,
            adapter_options=RobotAdapterOptions(include_velocities=False, external_effort_gain=None),
            probe=_LEHOME_PROBE,
        ),
    ]


def _assert_payload_model_resolvable(model: type[BaseModel]) -> None:
    model.model_rebuild(_types_namespace=globals(), raise_errors=True)


def register_physicalai_studio_plugin(registry: _RobotCatalogRegistry) -> None:
    """Register the LeHome garment catalog definition."""
    for definition in _definitions():
        payload_model = definition.robot_payload
        if isinstance(payload_model, type) and issubclass(payload_model, BaseModel):
            _assert_payload_model_resolvable(payload_model)
        registry.register_robot(definition)
