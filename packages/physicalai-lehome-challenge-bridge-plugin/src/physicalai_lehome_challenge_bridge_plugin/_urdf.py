"""URDF asset resolution for the Studio catalog.

The LeHome bridge reuses the bimanual SO-101 description (so101_dual.urdf +
its 12-joint left_*/right_* map) from ``physicalai-bimanual-so101-plugin`` so
Studio renders the same robot it would see on real hardware — no asset
duplication in this package.

The bimanual plugin is imported lazily: it requires Python >=3.12 and is only
installed on the Studio host, never in the Isaac Sim container (Python 3.11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def get_urdf_path() -> Path:
    """Return the path to the bimanual SO-101 URDF directory.

    Returns:
        The ``urdf/`` directory containing the bimanual description.

    """
    from physicalai_bimanual_so101_plugin import (  # ruff: ignore[import-outside-top-level]
        get_urdf_path as _bimanual_urdf_path,
    )

    return _bimanual_urdf_path()
