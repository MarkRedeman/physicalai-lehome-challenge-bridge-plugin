#!/usr/bin/env bash
#
# Start the LeHome challenge bridge inside the sim container.
#
# Usage:
#   docker compose -f sim/docker-compose.yml exec lehome ./sim/scripts/serve.sh [serve args...]
#
# Starts Xvfb (needed because even headless mode imports pynput, which requires
# an X display), then runs the bridge serve CLI. Pass through any extra args.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="/workspace/.venv/bin:$PATH"

# Start a virtual display for pynput / X11-dependent imports. Harmless if the
# container already has a real DISPLAY (Xvfb will just pick an unused :99).
if ! xdpyinfo -display "${DISPLAY:-:0}" >/dev/null 2>&1; then
	Xvfb :99 -screen 0 1920x1080x24 &>/tmp/xvfb.log &
	export DISPLAY=:99
fi

exec physicalai-lehome-challenge-bridge serve "$@"
