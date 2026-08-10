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
            assert server._server is not None
        finally:
            server.stop()


class TestControlEndpoint:
    def _start_server(self, inbox):

        # Bind the handler to a dedicated inbox so tests are isolated.
        self._prev = None
        store = CameraFrameStore(["top"])
        server = MjpegCameraServer(store, host="127.0.0.1", port=0)
        server.start()
        assert server._server is not None
        port = server._server.server_address[1]

        # Re-point the handler class control to the given inbox.
        handler = server._server.RequestHandlerClass
        self._prev = handler.control
        handler.control = inbox
        return server, port, handler

    def test_post_control_reset(self) -> None:
        import http.client

        from physicalai_lehome_challenge_bridge_plugin.control import ControlInbox

        inbox = ControlInbox()
        server, port, _ = self._start_server(inbox)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", "/control", body='{"cmd":"reset"}', headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            assert resp.status == 202
            resp.read()
            conn.close()

            drained = inbox.drain()
            assert len(drained) == 1
            assert drained[0].kind == "reset"
        finally:
            server.stop()
            if self._prev is not None:
                handler = None  # ruff: ignore[unused-variable]

    def test_post_control_switch(self) -> None:
        import http.client

        from physicalai_lehome_challenge_bridge_plugin.control import ControlInbox

        inbox = ControlInbox()
        server, port, _ = self._start_server(inbox)
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request(
                "POST",
                "/control",
                body='{"cmd":"switch","name":"Top_Long_Seen_3"}',
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            assert resp.status == 202
            resp.read()
            conn.close()

            drained = inbox.drain()
            assert drained[0].kind == "switch"
            assert drained[0].name == "Top_Long_Seen_3"
        finally:
            server.stop()

    def test_post_control_invalid_json(self) -> None:
        import http.client

        from physicalai_lehome_challenge_bridge_plugin.control import ControlInbox

        server, port, _ = self._start_server(ControlInbox())
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", "/control", body="not json")
            resp = conn.getresponse()
            assert resp.status == 400
            resp.read()
            conn.close()
        finally:
            server.stop()

    def test_post_control_unknown_cmd(self) -> None:
        import http.client

        from physicalai_lehome_challenge_bridge_plugin.control import ControlInbox

        server, port, _ = self._start_server(ControlInbox())
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", "/control", body='{"cmd":"explode"}')
            resp = conn.getresponse()
            assert resp.status == 400
            resp.read()
            conn.close()
        finally:
            server.stop()

    def test_post_switch_requires_name(self) -> None:
        import http.client

        from physicalai_lehome_challenge_bridge_plugin.control import ControlInbox

        server, port, _ = self._start_server(ControlInbox())
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("POST", "/control", body='{"cmd":"switch"}')
            resp = conn.getresponse()
            assert resp.status == 400
            resp.read()
            conn.close()
        finally:
            server.stop()
