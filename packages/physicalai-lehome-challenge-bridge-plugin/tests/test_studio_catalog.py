from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from physicalai.config import to_config
from physicalai.robot.transport import SharedRobot

from physicalai_lehome_challenge_bridge_plugin.studio_catalog import (
    LeHomeGarmentPayload,
    LeHomeGarmentProbe,
    _definitions,
    _SharedLeHomeRobot,
    register_physicalai_studio_plugin,
)


class TestLeHomeGarmentPayload:
    def test_default_payload(self) -> None:
        payload = LeHomeGarmentPayload()
        assert payload.name == "lehome-garment"
        assert payload.allow_remote is False
        assert payload.connect_timeout == 10.0

    def test_custom_payload(self) -> None:
        payload = LeHomeGarmentPayload(name="my-sim", allow_remote=True, connect_timeout=5.0)
        assert payload.name == "my-sim"
        assert payload.allow_remote is True
        assert payload.connect_timeout == 5.0

    def test_payload_model_rebuild(self) -> None:
        LeHomeGarmentPayload.model_rebuild(raise_errors=True)


class TestDefinitions:
    def test_definitions_return_list(self) -> None:
        defs = _definitions()
        assert len(defs) == 1

    def test_definition_contents(self) -> None:
        definition = _definitions()[0]
        assert definition.type == "LeHome_Garment_Follower"
        assert definition.display_name == "LeHome Garment Follower"
        assert definition.role == "follower"
        assert definition.asset is not None
        assert definition.robot_payload is LeHomeGarmentPayload
        assert definition.probe is not None

    def test_adapter_options(self) -> None:
        definition = _definitions()[0]
        assert definition.adapter_options.include_velocities is False
        assert definition.adapter_options.external_effort_gain is None

    def test_builder_callable(self) -> None:
        definition = _definitions()[0]
        assert callable(definition.robot_builder)

    def test_urdf_asset(self) -> None:
        definition = _definitions()[0]
        asset = definition.asset
        assert asset is not None
        assert str(asset.urdf_relative_path) == "so101_dual/so101_dual.urdf"
        assert "so101_dual" in asset.packages
        assert "left_shoulder_pan" in asset.joint_map
        assert "right_gripper" in asset.joint_map
        assert asset.root_resolver is not None


class TestSharedLeHomeRobot:
    def test_has_no_owned_devices(self) -> None:
        robot = _SharedLeHomeRobot(SharedRobot.attach("lehome-garment"))
        assert robot.device_ids == ()

    def test_exports_attach_only_shared_robot_recipe(self) -> None:
        robot = _SharedLeHomeRobot(SharedRobot.attach("lehome-garment", connect_timeout=5.0))

        assert to_config(robot) == {
            "class_path": "physicalai_lehome_challenge_bridge_plugin.studio_catalog._SharedLeHomeRobot",
            "init_args": {
                "shared_robot": {
                    "class_path": "physicalai.robot.SharedRobot",
                    "init_args": {
                        "name": "lehome-garment",
                        "allow_remote": False,
                        "connect_timeout": 5.0,
                    },
                },
            },
        }


class TestProbe:
    @pytest.mark.anyio
    async def test_discover(self) -> None:
        probe = LeHomeGarmentProbe()
        manager = AsyncMock()
        manager.robots = []
        result = await probe.discover(manager)
        assert result == []
        manager.find_robots.assert_awaited_once()

    @pytest.mark.anyio
    async def test_identify(self) -> None:
        probe = LeHomeGarmentProbe()
        payload = LeHomeGarmentPayload()
        await probe.identify(payload)

    @pytest.mark.anyio
    async def test_is_online_no_owner(self) -> None:
        from physicalai_lehome_challenge_bridge_plugin import studio_catalog as sc

        probe = LeHomeGarmentProbe()
        payload = LeHomeGarmentPayload(name="nonexistent")

        with patch.object(sc, "_check_zenoh_robot_online", return_value=False):
            result = await probe.is_online(payload)
            assert result is False


class TestRegistration:
    def test_register_called(self) -> None:
        registry = MagicMock()
        register_physicalai_studio_plugin(registry)
        registry.register_robot.assert_called_once()
