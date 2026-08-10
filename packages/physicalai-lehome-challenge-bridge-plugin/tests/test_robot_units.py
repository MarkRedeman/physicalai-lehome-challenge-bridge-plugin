"""Unit tests for the LeHome garment robot and config resolution."""

from __future__ import annotations

import pathlib
import sys
from types import ModuleType

import numpy as np
import pytest
from physicalai.config import to_config

from physicalai_lehome_challenge_bridge_plugin.constants import NUM_JOINTS
from physicalai_lehome_challenge_bridge_plugin.env_bootstrapper import SimBootstrapper, SimLaunchConfig
from physicalai_lehome_challenge_bridge_plugin.lehome_robot import (
    LeHomeGarmentObservation,
    LeHomeGarmentRobot,
    degrees_to_radians,
    radians_to_degrees,
)


class TestUnitConversion:
    def test_rad_to_deg(self) -> None:
        out = radians_to_degrees(np.array([np.pi / 2, 0.0, -np.pi]))
        np.testing.assert_allclose(out, [90.0, 0.0, -180.0], atol=1e-5)

    def test_deg_to_rad(self) -> None:
        out = degrees_to_radians(np.array([90.0, 0.0, -180.0]))
        np.testing.assert_allclose(out, [np.pi / 2, 0.0, -np.pi], atol=1e-6)

    def test_roundtrip(self) -> None:
        values = np.array([-110.0, -100.0, -97.0, -95.0, -157.0, -10.0], dtype=np.float32)
        np.testing.assert_allclose(radians_to_degrees(degrees_to_radians(values)), values, atol=1e-3)


class TestLeHomeGarmentObservation:
    def test_state_returns_positions(self) -> None:
        obs = LeHomeGarmentObservation(joint_positions=np.zeros(NUM_JOINTS, dtype=np.float32), timestamp=0.0)
        assert obs.state is obs.joint_positions


class TestLeHomeGarmentRobotConfig:
    def test_exports_config_recipe(self) -> None:
        sim_config = SimLaunchConfig(garment_type="top_long", headless=True, device="cuda")
        robot = LeHomeGarmentRobot(sim_config.as_dict(), enable_cameras=True)
        config = to_config(robot)
        assert config["class_path"] == ("physicalai_lehome_challenge_bridge_plugin.lehome_robot.LeHomeGarmentRobot")
        assert config["init_args"]["sim_config"]["garment_type"] == "top_long"
        assert config["init_args"]["enable_cameras"] is True

    def test_joint_names(self) -> None:
        robot = LeHomeGarmentRobot(SimLaunchConfig().as_dict())
        assert len(robot.joint_names) == NUM_JOINTS
        assert robot.joint_names[0] == "left_shoulder_pan"
        assert robot.joint_names[-1] == "right_gripper"

    def test_device_ids_empty(self) -> None:
        robot = LeHomeGarmentRobot(SimLaunchConfig().as_dict())
        assert robot.device_ids == ()

    def test_not_connected_by_default(self) -> None:
        robot = LeHomeGarmentRobot(SimLaunchConfig().as_dict())
        assert robot.is_connected() is False

    def test_get_observation_before_connect_raises(self) -> None:
        robot = LeHomeGarmentRobot(SimLaunchConfig().as_dict())
        with pytest.raises(ConnectionError):
            robot.get_observation()

    def test_send_action_before_connect_raises(self) -> None:
        robot = LeHomeGarmentRobot(SimLaunchConfig().as_dict())
        with pytest.raises(ConnectionError):
            robot.send_action(np.zeros(NUM_JOINTS, dtype=np.float32))


class TestParticleCfgResolution:
    def test_existing_path_passthrough(self, tmp_path: pathlib.Path) -> None:
        cfg = tmp_path / "particle_garment_cfg.yaml"
        cfg.write_text("x: 1", encoding="utf-8")
        bootstrapper = SimBootstrapper(SimLaunchConfig(particle_cfg_path=str(cfg)))
        assert pathlib.Path(bootstrapper._resolve_particle_cfg_path()) == cfg

    def test_absolute_path_passthrough(self, tmp_path: pathlib.Path) -> None:
        cfg = tmp_path / "particle_garment_cfg.yaml"
        bootstrapper = SimBootstrapper(SimLaunchConfig(particle_cfg_path=str(cfg)))
        assert pathlib.Path(bootstrapper._resolve_particle_cfg_path()) == cfg

    def test_package_relative_fallback(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Fake an editable-installed lehome package with the config shipped
        # inside it, and a missing repo-relative default.
        package_dir = tmp_path / "lehome"
        config_file = package_dir / "tasks" / "bedroom" / "config_file" / "particle_garment_cfg.yaml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("x: 1", encoding="utf-8")

        fake_lehome = ModuleType("lehome")
        fake_lehome.__file__ = str(package_dir / "__init__.py")
        monkeypatch.setitem(sys.modules, "lehome", fake_lehome)

        bootstrapper = SimBootstrapper(SimLaunchConfig(particle_cfg_path="source/lehome/.../particle_garment_cfg.yaml"))
        assert pathlib.Path(bootstrapper._resolve_particle_cfg_path()) == config_file

    def test_no_candidate_returns_configured(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        package_dir = tmp_path / "lehome"
        fake_lehome = ModuleType("lehome")
        fake_lehome.__file__ = str(package_dir / "__init__.py")
        monkeypatch.setitem(sys.modules, "lehome", fake_lehome)

        configured = "source/lehome/lehome/tasks/bedroom/config_file/particle_garment_cfg.yaml"
        bootstrapper = SimBootstrapper(SimLaunchConfig(particle_cfg_path=configured))
        assert bootstrapper._resolve_particle_cfg_path() == configured
