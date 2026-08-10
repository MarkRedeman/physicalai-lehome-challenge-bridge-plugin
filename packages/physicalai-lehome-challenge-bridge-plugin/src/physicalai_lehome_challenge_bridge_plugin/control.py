"""Thread-safe control commands for a running LeHome simulation.

The physicalai robot transport only carries joint state/actions, so scene
control (reset / garment switching) is exposed out-of-band over the MJPEG
HTTP server's ``/control`` endpoint. The HTTP handler enqueues a
:class:`ControlCommand` here; the owner loop drains it at the top of each
control tick, so the SimulationApp is only ever touched from the owner loop
thread — no races with Isaac Sim.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Literal

ControlKind = Literal["reset", "switch", "next"]

_DEFAULT_CONTROL: ControlInbox | None = None
_DEFAULT_CONTROL_LOCK = threading.Lock()


def get_default_control() -> ControlInbox:
    """Return the process-wide control inbox, creating it if needed.

    Returns:
        The shared :class:`ControlInbox`.
    """
    global _DEFAULT_CONTROL  # ruff: ignore[global-statement]
    with _DEFAULT_CONTROL_LOCK:
        if _DEFAULT_CONTROL is None:
            _DEFAULT_CONTROL = ControlInbox()
        return _DEFAULT_CONTROL


@dataclass
class ControlCommand:
    """One scene-control request understood by the owner loop."""

    kind: ControlKind
    name: str | None = None


@dataclass
class ControlInbox:
    """FIFO of pending control commands, shared between HTTP and owner loop."""

    _queue: queue.Queue[ControlCommand] = field(default_factory=queue.Queue)
    current_garment: str | None = None
    num_garments: int = 0
    garment_index: int = 0

    def push(self, command: ControlCommand) -> None:
        """Enqueue *command* for the owner loop to process."""
        self._queue.put(command)

    def drain(self) -> list[ControlCommand]:
        """Return and clear all currently pending commands, in FIFO order.

        Returns:
            The drained commands.
        """
        commands: list[ControlCommand] = []
        while True:
            try:
                commands.append(self._queue.get_nowait())
            except queue.Empty:
                return commands

    def update_state(self, *, garment: str | None, index: int, num_garments: int) -> None:
        """Publish the owner-loop's current garment state for HTTP responses."""
        self.current_garment = garment
        self.garment_index = index
        self.num_garments = num_garments
