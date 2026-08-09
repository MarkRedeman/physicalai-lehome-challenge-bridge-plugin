"""Thread-safe store of the latest rendered camera frames.

The owner loop renders the garment environment's TiledCameras every control
tick and writes the newest frame here; the MJPEG HTTP server reads from this
store when a client connects. Because owner and camera server live in the
same process, a mutex-protected dict is all we need — no IPC.

The owner driver is constructed from a config inside ``run_owner`` (a fresh
instance), while the camera server is started by the CLI in the same process.
A module-level default store lets both sides reach the same frames without
threading a live object through a JSON config.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

_DEFAULT_STORE: CameraFrameStore | None = None
_DEFAULT_STORE_LOCK = threading.Lock()


def get_default_store(camera_names: list[str]) -> CameraFrameStore:
    """Return the process-wide camera frame store, (re)creating if needed.

    Returns:
        The shared store configured for *camera_names*.

    """
    global _DEFAULT_STORE  # ruff: ignore[global-statement]
    requested = set(camera_names)
    with _DEFAULT_STORE_LOCK:
        if _DEFAULT_STORE is None or set(_DEFAULT_STORE.names()) != requested:
            _DEFAULT_STORE = CameraFrameStore(list(requested))
        return _DEFAULT_STORE


class CameraFrameStore:
    """Holds the latest RGB frame for each named camera."""

    def __init__(self, camera_names: list[str]) -> None:
        self._lock = threading.Lock()
        self._names = set(camera_names)
        self._frames: dict[str, np.ndarray] = {}

    def names(self) -> list[str]:
        """Return the configured camera names.

        Returns:
            The camera names in arbitrary order.

        """
        return list(self._names)

    def update(self, name: str, frame: np.ndarray) -> None:
        """Atomically store the newest frame for *name*."""
        if name not in self._names:
            return
        with self._lock:
            self._frames[name] = frame

    def latest(self, name: str) -> np.ndarray | None:
        """Return the newest frame for *name*, or ``None`` if none yet.

        Returns:
            The latest RGB frame, or ``None`` before any update.

        """
        with self._lock:
            return self._frames.get(name)
