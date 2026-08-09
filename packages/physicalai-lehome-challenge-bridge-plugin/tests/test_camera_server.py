from __future__ import annotations

import numpy as np

from physicalai_lehome_challenge_bridge_plugin._frame_store import CameraFrameStore, get_default_store
from physicalai_lehome_challenge_bridge_plugin.camera_server import MjpegCameraServer, _encode_jpeg


class TestCameraFrameStore:
    def test_update_and_latest(self) -> None:
        store = CameraFrameStore(["top", "left_wrist", "right_wrist"])
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        store.update("top", frame)
        stored = store.latest("top")
        assert stored is not None
        assert stored.shape == frame.shape

    def test_unknown_camera_ignored(self) -> None:
        store = CameraFrameStore(["top"])
        store.update("nope", np.zeros((10, 10, 3), dtype=np.uint8))
        assert store.latest("nope") is None

    def test_none_before_update(self) -> None:
        store = CameraFrameStore(["top"])
        assert store.latest("top") is None

    def test_names(self) -> None:
        store = CameraFrameStore(["top", "left_wrist"])
        assert set(store.names()) == {"top", "left_wrist"}


class TestDefaultStore:
    def test_reuses_same_instance_for_same_names(self) -> None:
        first = get_default_store(["top", "left_wrist", "right_wrist"])
        second = get_default_store(["top", "left_wrist", "right_wrist"])
        assert first is second


class TestJpegEncode:
    def test_encodes_rgb_frame(self) -> None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        jpeg = _encode_jpeg(frame)
        assert jpeg is not None
        assert jpeg[:2] == b"\xff\xd8"  # JPEG SOI marker


class TestMjpegCameraServer:
    def test_start_and_stop(self) -> None:
        store = CameraFrameStore(["top", "left_wrist", "right_wrist"])
        server = MjpegCameraServer(store, host="127.0.0.1", port=0)
        server.start()
        try:
            assert server._server is not None  # ruff: ignore[private-member-access]
        finally:
            server.stop()
