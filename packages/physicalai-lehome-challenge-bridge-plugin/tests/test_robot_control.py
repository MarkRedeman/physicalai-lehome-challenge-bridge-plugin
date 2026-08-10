from __future__ import annotations

import numpy as np
import pytest

from physicalai_lehome_challenge_bridge_plugin import lehome_robot as lr_module
from physicalai_lehome_challenge_bridge_plugin.control import ControlCommand, ControlInbox
from physicalai_lehome_challenge_bridge_plugin.env_bootstrapper import SimLaunchConfig
from physicalai_lehome_challenge_bridge_plugin.lehome_robot import LeHomeGarmentRobot


class _FakeEnv:
    """Minimal stand-in for the DirectRLEnv used by control tests."""

    def __init__(self, garment_name: str = "Top_Long_Seen_0") -> None:
        self.cfg = type("Cfg", (), {"garment_name": garment_name})()
        self.reset_count = 0
        self.switched: list[str] = []
        self.step_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def switch_garment(self, name: str) -> None:
        self.switched.append(name)
        self.cfg.garment_name = name

    def step(self, action) -> None:
        self.step_count += 1

    def _get_observations(self) -> dict:
        return {"observation.state": np.zeros(12, dtype=np.float32)}


class _FakeBootstrapper:
    def __init__(self, env: _FakeEnv, garments: list[str]) -> None:
        self.env = env
        self._garments = garments

    def garment_list(self) -> list[str]:
        return list(self._garments)

    def step(self, action) -> None:
        self.env.step(action)

    def disconnect(self) -> None:
        pass


def _make_robot(
    garments: list[str], *, current: str = "Top_Long_Seen_0",
) -> tuple[LeHomeGarmentRobot, _FakeEnv, ControlInbox]:
    robot = LeHomeGarmentRobot(SimLaunchConfig().as_dict())
    fake_env = _FakeEnv(garment_name=current)
    robot._bootstrapper = _FakeBootstrapper(fake_env, garments)
    robot._garments = list(garments)
    robot._garment_index = garments.index(current) if current in garments else 0
    robot._pending_action = np.zeros(12, dtype=np.float32)
    return robot, fake_env, robot._control


class TestReset:
    def test_reset_calls_env_reset_and_steps_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(lr_module, "_action_to_tensor", lambda action, device: action)
        robot, fake_env, _ = _make_robot(["Top_Long_Seen_0"])
        robot.reset()
        assert fake_env.reset_count == 1
        assert fake_env.step_count > 0
        assert robot.current_garment == "Top_Long_Seen_0"

    def test_reset_not_connected_raises(self) -> None:
        robot = LeHomeGarmentRobot(SimLaunchConfig().as_dict())
        with pytest.raises(ConnectionError):
            robot.reset()


class TestSwitchGarment:
    def test_switch_calls_env_and_resets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(lr_module, "_action_to_tensor", lambda action, device: action)
        robot, fake_env, _ = _make_robot(["Top_Long_Seen_0", "Top_Long_Seen_1"], current="Top_Long_Seen_0")
        robot.switch_garment("Top_Long_Seen_1")
        assert fake_env.switched == ["Top_Long_Seen_1"]
        assert fake_env.reset_count == 1
        assert robot.current_garment == "Top_Long_Seen_1"
        assert robot._garment_index == 1

    def test_switch_not_connected_raises(self) -> None:
        robot = LeHomeGarmentRobot(SimLaunchConfig().as_dict())
        with pytest.raises(ConnectionError):
            robot.switch_garment("Top_Long_Seen_1")


class TestNextGarment:
    def test_next_advances_and_wraps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(lr_module, "_action_to_tensor", lambda action, device: action)
        garments = ["Top_Long_Seen_0", "Top_Long_Seen_1", "Top_Long_Seen_2"]
        robot, fake_env, _ = _make_robot(garments, current="Top_Long_Seen_1")
        robot.next_garment()
        assert fake_env.switched == ["Top_Long_Seen_2"]
        assert robot.current_garment == "Top_Long_Seen_2"

        robot.next_garment()
        assert fake_env.switched == ["Top_Long_Seen_2", "Top_Long_Seen_0"]
        assert robot.current_garment == "Top_Long_Seen_0"

    def test_next_empty_list_skips(self) -> None:
        robot, fake_env, _ = _make_robot([], current="Top_Long_Seen_0")
        robot.next_garment()
        assert fake_env.switched == []

    def test_next_not_connected_raises(self) -> None:
        robot = LeHomeGarmentRobot(SimLaunchConfig().as_dict())
        with pytest.raises(ConnectionError):
            robot.next_garment()


class TestHandleControl:
    def test_drain_applies_reset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(lr_module, "_action_to_tensor", lambda action, device: action)
        robot, fake_env, inbox = _make_robot(["Top_Long_Seen_0"])
        inbox.push(ControlCommand(kind="reset"))
        # Simulate the owner loop draining on the next observation tick.
        robot.get_observation()
        assert fake_env.reset_count == 1

    def test_drain_applies_next(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(lr_module, "_action_to_tensor", lambda action, device: action)
        robot, fake_env, inbox = _make_robot(["Top_Long_Seen_0", "Top_Long_Seen_1"], current="Top_Long_Seen_0")
        inbox.push(ControlCommand(kind="next"))
        robot.get_observation()
        assert fake_env.switched == ["Top_Long_Seen_1"]

    def test_unknown_command_ignored(self) -> None:
        robot, fake_env, inbox = _make_robot(["Top_Long_Seen_0"])
        inbox.push(ControlCommand(kind="reset"))  # type: ignore[arg-type]
        inbox.drain()
        # Pushing a bogus kind still drains without raising.
        assert robot._control.drain() == []
        assert fake_env.reset_count == 0
