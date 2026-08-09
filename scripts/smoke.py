# ruff: file-ignore[implicit-namespace-package] -- scripts/ is not a package (no __init__.py)
"""Verify installed wheels can be imported and report their versions.

Usage:
    python scripts/smoke.py [package-name ...]
    python scripts/smoke.py   # reads all packages from release-please-config.json
"""

import importlib
import importlib.metadata
import json
import pathlib
import re
import sys


def main() -> None:
    """Import each requested package and report its installed version."""
    pkg_names = _get_package_names()

    for pkg_name in pkg_names:
        try:
            import_name = pkg_name.replace("-", "_")
            importlib.import_module(import_name)
            importlib.metadata.version(pkg_name)
        except (ImportError, importlib.metadata.PackageNotFoundError):
            sys.exit(1)


def _get_package_names() -> list[str]:
    if len(sys.argv) > 1:
        return sys.argv[1:]

    config_path = pathlib.Path(__file__).parent.parent / ".github" / "release-please-config.json"
    if config_path.exists():
        with config_path.open(encoding="utf-8") as f:
            config = json.load(f)
        return [pkg["package-name"] for pkg in config["packages"].values()]

    # Fall back to workspace members when release-please config is absent.
    root = pathlib.Path(__file__).parent.parent
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8")
        members = re.findall(r"^\s*members\s*=\s*\[(.*?)\]", text, re.MULTILINE | re.DOTALL)
        names: list[str] = []
        for block in members:
            for raw in re.findall(r'"([^"]+)"', block):
                if "*" in raw:
                    expanded = sorted(p.name for p in root.glob(raw) if p.is_dir())
                    names.extend(expanded)
                else:
                    names.append(raw)
        names = sorted(set(names))
        if names:
            return names

    sys.exit(2)


if __name__ == "__main__":
    main()
