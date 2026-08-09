from __future__ import annotations

import numpy as np
import pytest
from physicalai.config import to_config

from physicalai_lehome_challenge_bridge_plugin.constants import NUM_JOINTS
from physicalai_lehome_challenge_bridge_plugin.env_bootstrapper import SimLaunchConfig
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
