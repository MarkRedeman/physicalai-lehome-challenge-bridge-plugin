from __future__ import annotations

from physicalai_lehome_challenge_bridge_plugin.constants import (
    DEFAULT_CAMERA_PORT,
    DEFAULT_ROBOT_NAME,
    JOINT_LIMITS_DEG,
    JOINT_ORDER,
    LEFT_JOINTS,
    NUM_JOINTS,
    NUM_SINGLE_ARM_JOINTS,
    RIGHT_JOINTS,
)


class TestJointOrder:
    def test_num_joints(self) -> None:
        assert NUM_JOINTS == 12
        assert NUM_SINGLE_ARM_JOINTS == 6

    def test_left_and_right_arms(self) -> None:
        assert JOINT_ORDER[:6] == LEFT_JOINTS
        assert JOINT_ORDER[6:] == RIGHT_JOINTS

    def test_left_joint_names(self) -> None:
        assert LEFT_JOINTS == (
            "left_shoulder_pan",
            "left_shoulder_lift",
            "left_elbow_flex",
            "left_wrist_flex",
            "left_wrist_roll",
            "left_gripper",
        )

    def test_no_overlap_between_arms(self) -> None:
        assert set(LEFT_JOINTS).isdisjoint(RIGHT_JOINTS)

    def test_joint_order_unique(self) -> None:
        assert len(set(JOINT_ORDER)) == NUM_JOINTS


class TestConstants:
    def test_default_robot_name(self) -> None:
        assert DEFAULT_ROBOT_NAME == "lehome-garment"

    def test_default_camera_port(self) -> None:
        assert DEFAULT_CAMERA_PORT == 8090

    def test_limits_cover_all_joints(self) -> None:
        assert set(JOINT_LIMITS_DEG) == set(JOINT_ORDER)

    def test_gripper_limit(self) -> None:
        assert JOINT_LIMITS_DEG["left_gripper"] == (-10.0, 100.0)
        assert JOINT_LIMITS_DEG["right_gripper"] == (-10.0, 100.0)
