"""Lazy Isaac Sim bootstrap for the LeHome garment environment.

All Isaac Sim / lehome imports live inside this module's functions so that
importing the bridge package on a Studio host (which has no Isaac Sim) is
safe. Only the serve CLI inside the simulator process calls these.
"""

from __future__ import annotations

import argparse
import pathlib
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from isaaclab.envs import DirectRLEnv
    from torch import Tensor

# Task registered by lehome.tasks.bedroom (see lehome/tasks/bedroom/__init__.py).
TASK_NAME = "LeHome-BiSO101-Direct-Garment-v2"


@dataclass
class SimLaunchConfig:
    """Options controlling the Isaac Sim app and garment environment."""

    garment_type: str = "top_long"
    garment_name: str | None = None
    garment_version: str = "Release"
    garment_cfg_base_path: str = "Assets/objects/Challenge_Garment"
    particle_cfg_path: str = "source/lehome/lehome/tasks/bedroom/config_file/particle_garment_cfg.yaml"
    headless: bool = False
    enable_cameras: bool = True
    device: str = "cuda"
    seed: int = 42
    # AppLauncher kwargs passthrough (subset of add_app_launcher_args).
    launcher_kwargs: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        """Return fields as a JSON-safe mapping for ``@export_config``.

        Returns:
            A plain dict of all configuration fields.

        """
        return asdict(self)


class SimBootstrapper:
    """Owns the SimulationApp + GarmentEnv lifecycle for one owner process.

    The owner loop runs in the same process as ``SimulationApp`` (required by
    Isaac Sim), so this class is constructed and driven by the serve CLI via
    the physicalai ``Robot`` protocol, never across a process boundary.
    """

    def __init__(self, config: SimLaunchConfig) -> None:
        """Initialize a disconnected bootstrapper.

        Args:
            config: Sim launch configuration.

        """
        self._config = config
        self._app = None
        self._env: DirectRLEnv | None = None

    @property
    def env(self) -> DirectRLEnv:
        """The created garment environment (requires :meth:`connect`).

        Returns:
            The live garment environment.

        Raises:
            ConnectionError: If :meth:`connect` has not been called.

        """
        if self._env is None:
            msg = "Simulation is not connected. Call connect() first."
            raise ConnectionError(msg)
        return self._env

    def connect(self) -> None:
        """Launch SimulationApp and create the garment environment."""
        if self._env is not None:
            return
        self._app = self._launch_app()
        # Importing the task package registers the gym env id.
        import gymnasium as gym  # ruff: ignore[import-outside-top-level]
        import lehome.tasks.bedroom  # ruff: ignore[import-outside-top-level, unused-import]

        env_cfg = self._build_env_cfg()
        self._env = gym.make(TASK_NAME, cfg=env_cfg).unwrapped
        self._env.initialize_obs()

    def _launch_app(self) -> object:
        from isaaclab.app import AppLauncher  # ruff: ignore[import-outside-top-level]

        args = self._build_launcher_args()
        app_launcher = AppLauncher(vars(args))
        return app_launcher.app

    def _build_launcher_args(self) -> argparse.Namespace:
        base: dict[str, object] = {
            "headless": self._config.headless,
            "enable_cameras": self._config.enable_cameras,
            "livestream": 0,
            "device": self._config.device,
            "kit_args": "--/log/level=error --/log/fileLogLevel=error --/log/outputStreamLevel=error",
        }
        base.update(self._config.launcher_kwargs)
        return argparse.Namespace(**base)

    def _build_env_cfg(self) -> object:
        from lehome.tasks.bedroom.garment_bi_cfg_v2 import GarmentEnvCfg  # ruff: ignore[import-outside-top-level]

        cfg = GarmentEnvCfg()
        cfg.garment_cfg_base_path = self._config.garment_cfg_base_path
        cfg.particle_cfg_path = self._config.particle_cfg_path
        cfg.use_random_seed = False
        cfg.random_seed = self._config.seed

        # Resolve the garment name from the eval list for the requested type.
        if self._config.garment_name is not None:
            cfg.garment_name = self._config.garment_name
        else:
            cfg.garment_name = self._resolve_garment_name()
        cfg.garment_version = self._config.garment_version
        return cfg

    def _resolve_garment_name(self) -> str:
        type_map = {
            "top_long": "Top_Long",
            "top_short": "Top_Short",
            "pant_long": "Pant_Long",
            "pant_short": "Pant_Short",
            "custom": "Top_Long",
        }
        prefix = type_map.get(self._config.garment_type, "Top_Long")
        list_path = (
            pathlib.Path(self._config.garment_cfg_base_path) / self._config.garment_version / prefix / f"{prefix}.txt"
        )
        if not list_path.exists():
            return f"{prefix}_Unseen_0"
        names = [line.strip() for line in list_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return names[0] if names else f"{prefix}_Unseen_0"

    def step(self, action: Tensor) -> None:
        """Step the environment with the given action tensor."""
        self.env.step(action)

    def reset(self) -> None:
        """Reset the environment to its initial state."""
        self.env.reset()

    def disconnect(self) -> None:
        """Close the SimulationApp, releasing the GPU."""
        env, self._env = self._env, None
        del env
        if self._app is not None:
            self._app.close()
            self._app = None
