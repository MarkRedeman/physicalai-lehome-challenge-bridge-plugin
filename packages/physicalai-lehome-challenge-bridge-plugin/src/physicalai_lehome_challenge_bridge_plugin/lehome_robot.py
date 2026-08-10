"""LeHome Challenge garment environment exposed as a physicalai ``Robot``.

``LeHomeGarmentRobot`` implements the physicalai ``Robot`` protocol and is
``@export_config``-decorated so the owner runtime can construct it from a
JSON recipe. The heavy Isaac Sim bootstrapping is delegated to
:class:`~physicalai_lehome_challenge_bridge_plugin.env_bootstrapper.SimBootstrapper`,
which is created lazily on :meth:`connect` — so importing this module never
imports Isaac Sim.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import numpy as np
from loguru import logger
from physicalai.config import export_config

from physicalai_lehome_challenge_bridge_plugin._frame_store import CameraFrameStore, get_default_store
from physicalai_lehome_challenge_bridge_plugin.constants import HOME_POSITION_RAD, JOINT_ORDER, NUM_JOINTS
from physicalai_lehome_challenge_bridge_plugin.control import ControlCommand, ControlInbox, get_default_control
from physicalai_lehome_challenge_bridge_plugin.env_bootstrapper import SimBootstrapper, SimLaunchConfig

if TYPE_CHECKING:
    from physicalai.capture.frame import Frame
    from physicalai.robot.interface import RobotObservation

# Camera names published to the MJPEG server, keyed by env observation key.
_CAMERA_OBS_KEYS: dict[str, str] = {
    "top": "observation.images.top_rgb",
    "left_wrist": "observation.images.left_rgb",
    "right_wrist": "observation.images.right_rgb",
}

_RAD2DEG = 180.0 / np.pi
_DEG2RAD = np.pi / 180.0


def radians_to_degrees(values: np.ndarray) -> np.ndarray:
    """Convert a joint array from radians to degrees.

    Returns:
        The input converted to degrees.

    """
    return np.asarray(values, dtype=np.float32) * _RAD2DEG


def degrees_to_radians(values: np.ndarray) -> np.ndarray:
    """Convert a joint array from degrees to radians.

    Returns:
        The input converted to radians.

    """
    return np.asarray(values, dtype=np.float32) * _DEG2RAD


@dataclass
class LeHomeGarmentObservation:
    """Observation returned by the simulated garment robot."""

    joint_positions: np.ndarray
    timestamp: float
    sensor_data: dict[str, np.ndarray] | None = None
    images: dict[str, Frame] | None = None

    @property
    def state(self) -> np.ndarray:
        """Joint positions as the canonical state vector."""
        return self.joint_positions


@export_config(class_path="physicalai_lehome_challenge_bridge_plugin.lehome_robot.LeHomeGarmentRobot")
class LeHomeGarmentRobot:
    """Bimanual SO-101 follower simulated in the LeHome garment environment.

    Args:
        sim_config: Serialized :class:`SimLaunchConfig` options (JSON-safe
            mapping) controlling the Isaac Sim app and environment.
        enable_cameras: Whether to render and stream the camera feeds.

    """

    JOINT_ORDER: ClassVar[tuple[str, ...]] = JOINT_ORDER
    NUM_JOINTS: ClassVar[int] = NUM_JOINTS

    def __init__(self, sim_config: dict, *, enable_cameras: bool = True) -> None:
        """Initialize a disconnected simulation robot."""
        self._sim_config = SimLaunchConfig(**sim_config)
        self._enable_cameras = enable_cameras
        self._bootstrapper: SimBootstrapper | None = None
        self._camera_store: CameraFrameStore | None = None
        self._control: ControlInbox = get_default_control()
        self._garments: list[str] = []
        self._garment_index = 0
        self._pending_action: np.ndarray | None = None
        self._sequence = 0

    @property
    def joint_names(self) -> list[str]:
        """Ordered joint names (left arm then right arm)."""
        return list(self.JOINT_ORDER)

    @property
    def device_ids(self) -> tuple[str, ...]:
        """A simulation owns no physical device, so no exclusive device ids."""
        return ()

    def connect(self) -> None:
        """Launch Isaac Sim and create the garment environment (idempotent)."""
        if self.is_connected():
            return
        self._bootstrapper = SimBootstrapper(self._sim_config)
        self._bootstrapper.connect()
        if self._enable_cameras:
            self._camera_store = get_default_store(list(_CAMERA_OBS_KEYS))

        # Resolve the garment list and park the robot at home, then report state.
        self._garments = self._bootstrapper.garment_list()
        self._garment_index = self._find_garment_index(self._bootstrapper.env.cfg.garment_name)
        self._pending_action = radians_to_degrees(np.asarray(HOME_POSITION_RAD, dtype=np.float32))
        self._publish_control_state()

        logger.info("LeHome garment robot connected (task={})", "LeHome-BiSO101-Direct-Garment-v2")

    @property
    def current_garment(self) -> str | None:
        """Name of the garment currently loaded in the scene."""
        if not self.is_connected() or self._bootstrapper is None:
            return None
        return self._bootstrapper.env.cfg.garment_name

    @property
    def garments(self) -> list[str]:
        """Ordered garment names for the configured type."""
        return list(self._garments)

    def disconnect(self) -> None:
        """Close the SimulationApp, releasing the GPU."""
        if self._bootstrapper is not None:
            self._bootstrapper.disconnect()
            self._bootstrapper = None
        self._camera_store = None
        self._pending_action = None
        self._garments = []
        self._garment_index = 0
        self._publish_control_state()
        logger.info("LeHome garment robot disconnected")

    def is_connected(self) -> bool:
        """Return whether the SimulationApp and environment are live.

        Returns:
            True if connected, False otherwise.

        """
        return self._bootstrapper is not None

    def get_observation(self) -> RobotObservation:
        """Step the sim with the newest action and read joint + camera state.

        Returns:
            The current joint observation (degrees) plus camera frames.

        Raises:
            ConnectionError: If the robot is not connected.

        """
        if not self.is_connected():
            msg = "Robot is not connected. Call connect() first."
            raise ConnectionError(msg)
        assert self._bootstrapper is not None  # ruff: ignore[assert]  # guaranteed by is_connected()

        # Apply any pending scene-control commands before stepping the sim.
        for command in self._control.drain():
            self._handle_control(command)

        action = self._pending_action if self._pending_action is not None else np.zeros(NUM_JOINTS, dtype=np.float32)
        self._bootstrapper.step(_action_to_tensor(action, self._sim_config.device))

        observations = self._bootstrapper.env._get_observations()  # ruff: ignore[private-member-access]
        positions = radians_to_degrees(observations["observation.state"])

        images = None
        if self._camera_store is not None:
            images = self._capture_images(observations)

        self._sequence += 1
        return LeHomeGarmentObservation(
            joint_positions=positions,
            timestamp=time.monotonic(),
            sensor_data=None,
            images=images,
        )

    def send_action(self, action: np.ndarray, *, goal_time: float = 0.1) -> None:  # ruff: ignore[unused-method-argument]
        """Queue a joint target for the next simulation step.

        Args:
            action: Array of shape ``(12,)`` with joint targets in degrees,
                ordered as :attr:`joint_names`.
            goal_time: Ignored — the sim steps once per owner tick.

        Raises:
            ConnectionError: If the robot is not connected.
            ValueError: If ``action`` does not match the joint count.

        """
        if not self.is_connected():
            msg = "Robot is not connected. Call connect() first."
            raise ConnectionError(msg)

        if action.shape != (NUM_JOINTS,):
            msg = f"Expected action shape ({NUM_JOINTS},), got {action.shape}"
            raise ValueError(msg)
        self._pending_action = np.asarray(action, dtype=np.float32).copy()

    def reset(self) -> None:
        """Reset the scene: re-home the robot and re-settle the current garment.

        Runs the same pattern as the challenge eval script — ``env.reset()``
        followed by stabilization steps at the home pose — so the garment is
        ready for a fresh episode.

        Raises:
            ConnectionError: If the robot is not connected.

        """
        if not self.is_connected() or self._bootstrapper is None:
            msg = "Robot is not connected. Call connect() first."
            raise ConnectionError(msg)

        self._bootstrapper.env.reset()
        self._pending_action = radians_to_degrees(np.asarray(HOME_POSITION_RAD, dtype=np.float32))
        self._stabilize()
        self._publish_control_state()
        logger.info("LeHome garment scene reset (garment={})", self.current_garment)

    def switch_garment(self, name: str) -> None:
        """Switch the scene to a different garment, then reset it.

        Args:
            name: Garment name (e.g. ``Top_Long_Seen_3``).

        Raises:
            ConnectionError: If the robot is not connected.
        """
        if not self.is_connected() or self._bootstrapper is None:
            msg = "Robot is not connected. Call connect() first."
            raise ConnectionError(msg)

        self._bootstrapper.env.switch_garment(name)
        self._garment_index = self._find_garment_index(name)
        self.reset()
        logger.info("LeHome garment switched (garment={})", name)

    def next_garment(self) -> None:
        """Advance to the next garment in the evaluation list (wraps around).

        Raises:
            ConnectionError: If the robot is not connected.

        """
        if not self.is_connected() or self._bootstrapper is None:
            msg = "Robot is not connected. Call connect() first."
            raise ConnectionError(msg)
        if not self._garments:
            logger.warning("No garments available to advance to; skipping")
            return
        self._garment_index = (self._garment_index + 1) % len(self._garments)
        self.switch_garment(self._garments[self._garment_index])

    def _handle_control(self, command: ControlCommand) -> None:
        """Apply one control command to the live scene."""
        try:
            self._apply_control(command)
        except Exception:  # ruff: ignore[blind-except]  # a control failure must not kill the owner loop
            logger.exception("Failed to handle control command {}", command.kind)

    def _apply_control(self, command: ControlCommand) -> None:
        if command.kind == "reset":
            self.reset()
        elif command.kind == "switch":
            if command.name is None:
                logger.warning("Control 'switch' requires a garment name; ignoring")
                return
            self.switch_garment(command.name)
        elif command.kind == "next":
            self.next_garment()
        else:  # pragma: no cover - defensive against unknown kinds
            logger.warning("Unknown control command {!r}; ignoring", command.kind)

    def _find_garment_index(self, name: str | None) -> int:
        if name is None:
            return 0
        try:
            return self._garments.index(name)
        except ValueError:
            return 0

    def _stabilize(self, num_steps: int = 20) -> None:
        """Step the sim at the home pose so the garment settles after a reset."""
        assert self._bootstrapper is not None  # ruff: ignore[assert]  # guarded by callers
        home = _action_to_tensor(
            radians_to_degrees(np.asarray(HOME_POSITION_RAD, dtype=np.float32)),
            self._sim_config.device,
        )
        for _ in range(num_steps):
            self._bootstrapper.step(home)

    def _publish_control_state(self) -> None:
        self._control.update_state(
            garment=self.current_garment,
            index=self._garment_index,
            num_garments=len(self._garments),
        )

    def _capture_images(self, observations: dict) -> dict:
        from physicalai.capture.frame import Frame  # ruff: ignore[import-outside-top-level]

        images: dict[str, Frame] = {}
        assert self._camera_store is not None  # ruff: ignore[assert]  # guaranteed when enable_cameras
        for camera_name, obs_key in _CAMERA_OBS_KEYS.items():
            frame = np.asarray(observations[obs_key])
            self._camera_store.update(camera_name, frame)
            images[camera_name] = Frame(data=frame, timestamp=time.monotonic(), sequence=self._sequence)
        return images

    def __getstate__(self) -> dict:
        """Return serializable construction state.

        Returns:
            A JSON-safe mapping of construction arguments.

        """
        return {
            "sim_config": self._sim_config.as_dict(),
            "enable_cameras": self._enable_cameras,
        }

    def __setstate__(self, state: dict) -> None:
        """Restore serializable construction state."""
        self._sim_config = SimLaunchConfig(**state["sim_config"])
        self._enable_cameras = bool(state.get("enable_cameras", True))
        self._bootstrapper = None
        self._camera_store = None
        self._control = get_default_control()
        self._garments = []
        self._garment_index = 0
        self._pending_action = None
        self._sequence = 0


def _action_to_tensor(action_deg: np.ndarray, device: str) -> object:
    """Convert a degrees action array to the env's (1, 12) radians tensor.

    Returns:
        A CUDA/CPU tensor of shape ``(1, 12)`` in radians.

    """
    import torch  # ruff: ignore[import-outside-top-level]

    return torch.from_numpy(degrees_to_radians(action_deg)).unsqueeze(0).to(device)
