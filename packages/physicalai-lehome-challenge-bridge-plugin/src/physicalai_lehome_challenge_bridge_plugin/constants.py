"""LeHome Challenge bridge robot constants.

The simulated robot is a bimanual SO-101 follower (12 joints, 6 per arm)
rendered by Isaac Sim. Joint names and ordering mirror the
``physicalai-bimanual-so101-plugin`` conventions so Studio URDF mapping,
teleoperation and action semantics stay identical to real hardware.
"""

from __future__ import annotations

from typing import Final

JOINT_ORDER: Final = (
    "left_shoulder_pan",
    "left_shoulder_lift",
    "left_elbow_flex",
    "left_wrist_flex",
    "left_wrist_roll",
    "left_gripper",
    "right_shoulder_pan",
    "right_shoulder_lift",
    "right_elbow_flex",
    "right_wrist_flex",
    "right_wrist_roll",
    "right_gripper",
)

NUM_JOINTS: Final = 12
NUM_SINGLE_ARM_JOINTS: Final = 6

LEFT_JOINTS: Final = JOINT_ORDER[:NUM_SINGLE_ARM_JOINTS]
RIGHT_JOINTS: Final = JOINT_ORDER[NUM_SINGLE_ARM_JOINTS:]

# Degrees, matching the SO-101 motor limits used by the bimanual plugin.
JOINT_LIMITS_DEG: Final = {
    "left_shoulder_pan": (-110.0, 110.0),
    "left_shoulder_lift": (-100.0, 100.0),
    "left_elbow_flex": (-97.0, 97.0),
    "left_wrist_flex": (-95.0, 95.0),
    "left_wrist_roll": (-157.0, 163.0),
    "left_gripper": (-10.0, 100.0),
    "right_shoulder_pan": (-110.0, 110.0),
    "right_shoulder_lift": (-100.0, 100.0),
    "right_elbow_flex": (-97.0, 97.0),
    "right_wrist_flex": (-95.0, 95.0),
    "right_wrist_roll": (-157.0, 163.0),
    "right_gripper": (-10.0, 100.0),
}

# Default Zenoh robot name exposed by the owner.
DEFAULT_ROBOT_NAME: Final = "lehome-garment"

# Default MJPEG camera HTTP port.
DEFAULT_CAMERA_PORT: Final = 8090

# Home joint positions in radians, ordered as JOINT_ORDER (left then right).
# Mirrors DUAL_ARM_HOME_POSITION from the lehome challenge's scripts/utils/common.py.
HOME_POSITION_RAD: Final = (
    -1.2363,  # left_shoulder_pan
    -1.7135,  # left_shoulder_lift
    1.4979,  # left_elbow_flex
    1.0534,  # left_wrist_flex
    -0.085,  # left_wrist_roll
    -0.01176,  # left_gripper
    1.2363,  # right_shoulder_pan
    -1.7135,  # right_shoulder_lift
    1.4979,  # right_elbow_flex
    1.0534,  # right_wrist_flex
    -0.085,  # right_wrist_roll
    -0.01176,  # right_gripper
)
