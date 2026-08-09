"""MJPEG-over-HTTP camera server.

Serves the latest rendered camera frames as classic MJPEG streams
(``multipart/x-mixed-replace``), one endpoint per camera. This is the
out-of-band image channel for the LeHome bridge: the physicalai robot
transport only carries joint state, so camera feeds go over plain HTTP
instead (no v4l2loopback needed, unlike the MuJoCo plugin).
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from numpy.typing import NDArray

    from physicalai_lehome_challenge_bridge_plugin._frame_store import CameraFrameStore

_BOUNDARY = "frame"
_BOUNDARY_BYTES = b"--frame\r\n"
_CONTENT_TYPE = "image/jpeg"
_CHUNK = f"Content-Type: {_CONTENT_TYPE}\r\nContent-Length: {{len}}\r\n\r\n"


def _encode_jpeg(frame: NDArray) -> bytes | None:
    """Encode an ``(H, W, 3)`` uint8 RGB frame to JPEG bytes.

    Returns:
        JPEG bytes, or ``None`` if encoding fails.

    """
    import cv2  # ruff: ignore[import-outside-top-level]

    ok, buf = cv2.imencode(".jpg", frame[:, :, ::-1], [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        return None
    return buf.tobytes()


class _MjpegHandler(BaseHTTPRequestHandler):
    """Serves one MJPEG stream per registered camera endpoint."""

    store: CameraFrameStore
    camera_names: list[str]

    def do_GET(self) -> None:
        if self.path == "/":
            self._serve_index()
            return
        camera = self.path.strip("/")
        if not camera.startswith("camera/"):
            self.send_error(404, "Not found")
            return
        name = camera[len("camera/") :]
        if name not in self.camera_names:
            self.send_error(404, f"Unknown camera {name!r}")
            return
        self._serve_stream(name)

    def _serve_index(self) -> None:
        body = "<html><body><ul>"
        for name in self.camera_names:
            body += f'<li><a href="/camera/{name}">{name}</a></li>'
        body += "</ul></body></html>"
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_stream(self, name: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={_BOUNDARY}")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self._stream_frames(name)
        except (TimeoutError, BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.close_connection = True

    def _stream_frames(self, name: str) -> None:
        while True:
            frame = self.store.latest(name)
            if frame is None:
                threading.Event().wait(0.05)
                continue
            jpeg = _encode_jpeg(frame)
            if jpeg is None:
                continue
            self.wfile.write(_BOUNDARY_BYTES)
            self.wfile.write(_CHUNK.format(len=len(jpeg)).encode())
            self.wfile.write(jpeg)
            self.wfile.write(b"\r\n")
            self.wfile.flush()
            threading.Event().wait(0.03)  # ~30 FPS ceiling

    @staticmethod
    def log_message(fmt: str, *args: object) -> None:
        logger.debug(fmt, *args)


class MjpegCameraServer:
    """Runs the MJPEG HTTP server on a background thread."""

    def __init__(
        self,
        store: CameraFrameStore,
        *,
        host: str = "0.0.0.0",  # ruff: ignore[hardcoded-bind-all-interfaces]  # nosec B104: explicit server bind
        port: int = 8090,
    ) -> None:
        """Initialize a stopped camera server.

        Args:
            store: Frame store read by the MJPEG handlers.
            host: Bind address. Defaults to all interfaces so the Studio host
                can reach the feeds.  # nosec B104: explicit server bind
            port: HTTP listen port.

        """
        self._store = store
        self._host = host
        self._port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Bind and start serving in a daemon thread."""
        handler = _mjpeg_handler_factory(self._store)
        self._server = ThreadingHTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(
            "MJPEG camera server listening on http://{}:{}/ (cameras: {})",
            self._host,
            self._port,
            self._store.names(),
        )

    def stop(self) -> None:
        """Shut down the HTTP server."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


def _mjpeg_handler_factory(store: CameraFrameStore) -> Callable[..., BaseHTTPRequestHandler]:
    """Return a handler class bound to *store*.

    Returns:
        A ``BaseHTTPRequestHandler`` subclass reading from *store*.

    """

    class _Handler(_MjpegHandler):  # type: ignore[misc, valid-type]
        camera_names = store.names()

    _Handler.store = store
    return _Handler
