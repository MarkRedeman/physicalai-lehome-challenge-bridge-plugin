#!/usr/bin/env bash
#
# Host-level fallback: start the LeHome challenge bridge on a host that
# already has Isaac Sim + lehome installed (no Docker). Use this when the
# containerized setup's performance is not good enough.
#
# Prereqs (installed manually, see README):
#   - Python 3.11 venv with: uv sync --group sim  (or pip install of the same)
#   - IsaacLab fork installed via isaaclab.sh -i none (with the known fixes)
#   - lehome package installed from the lehome-challenge repo
#   - Assets/ and Datasets/ present in this repo root
#
# Usage:
#   ./serve-host.sh [serve args...]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV="${VENV:-$REPO_ROOT/.venv}"
if [[ ! -x "$VENV/bin/physicalai-lehome-challenge-bridge" ]]; then
	echo "error: bridge CLI not found in $VENV. Run: uv sync --group sim" >&2
	exit 1
fi
export PATH="$VENV/bin:$PATH"

# Start a virtual display for pynput / X11-dependent imports.
if ! xdpyinfo -display "${DISPLAY:-:0}" >/dev/null 2>&1; then
	Xvfb :99 -screen 0 1920x1080x24 &>/tmp/xvfb.log &
	export DISPLAY=:99
fi

exec physicalai-lehome-challenge-bridge serve "$@"
