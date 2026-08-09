# LeHome Challenge bridge — Isaac Sim simulation container.
#
# Builds Isaac Sim 5.1.0 + the lehome challenge environment + this bridge
# plugin so the sim can be served to PhysicalAI Studio:
#
#     docker compose -f sim/docker-compose.yml build
#     docker compose -f sim/docker-compose.yml up -d
#     docker compose -f sim/docker-compose.yml exec lehome ./scripts/serve.sh
#
# The image contains ONLY the environment (Isaac Sim + deps + lehome + the
# bridge plugin). Assets and datasets are mounted from the host as volumes.

FROM nvidia/cuda:12.8.0-base-ubuntu22.04

ENV OMNI_KIT_ACCEPT_EULA=YES \
    ACCEPT_EULA=Y \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/root/.local/bin:${PATH}"

# System dependencies: GL/EGL/X11 libs + build/media essentials + Xvfb
# (pynput/keyboard import needs an X display even in headless mode).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        build-essential \
        cmake \
        libglu1-mesa \
        libgl1 \
        libegl1 \
        libglvnd0 \
        libvulkan1 \
        libxrandr2 \
        libxinerama1 \
        libxcursor1 \
        libxi6 \
        libxext6 \
        libx11-6 \
        libsndfile1 \
        ffmpeg \
        xvfb \
        xauth \
    && rm -rf /var/lib/apt/lists/*

# uv (Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /workspace

# Bring in the whole repo (workspace) so uv can build the plugin package.
COPY . .

# Python 3.11 + the bridge plugin workspace + the sim deps (Isaac Sim 5.1.0,
# lerobot) as a dependency group. `--no-install-project` keeps the virtual
# workspace root from being built; the plugin is pulled in via the sim group.
# The plugin's Studio-only deps are NOT installed here (they need Python >=3.12
# and belong on the Studio host). UV_HTTP_TIMEOUT is raised because
# pypi.nvidia.com is flaky for the nvidia-*-cu12 wheels.
# A uv cache mount keeps downloads warm across rebuilds.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv python install 3.11 \
    && export UV_HTTP_TIMEOUT=600 \
    && uv sync --python 3.11 --no-dev --group sim --no-install-project

# IsaacLab fork (shallow clone) + editable install of its extensions.
# `-i none` installs the extensions but skips the RL-framework extras.
# TERM is required because isaaclab.sh runs `tabs 4`; `/.dockerenv` makes the
# script detect a docker build and skip its interactive VSCode/EULA setup.
RUN git clone --depth 1 https://github.com/lehome-official/IsaacLab.git third_party/IsaacLab \
    && touch /.dockerenv \
    && bash -c 'export TERM=xterm; source .venv/bin/activate && ./third_party/IsaacLab/isaaclab.sh -i none'

# The `isaaclab.sh -i none` loop silently skips the CORE `isaaclab` package:
# building its pinned `flatdict==4.0.1` fails under uv build isolation because
# that old setup.py imports `pkg_resources` (removed in setuptools>=81). The
# failure is swallowed by `find -exec` (non-propagated exit), so the five
# extension packages install but `import isaaclab` fails. Fix: pin setuptools
# <81 (still ships pkg_resources) and build without isolation.
RUN --mount=type=cache,target=/root/.cache/uv bash -c 'source .venv/bin/activate && \
    uv pip install "setuptools<81" && \
    uv pip install --no-build-isolation -e third_party/IsaacLab/source/isaaclab'

# Match the warp version bundled with Isaac Sim 5.1.0 (omni.warp 1.8.2).
# The unpinned `warp-lang` pulled by the core isaaclab install resolves to
# 1.16.0, whose API breaks isaacsim (warp.types.array was removed). Pin 1.8.1
# (no 1.8.2 pip release exists) which retains the expected API.
RUN --mount=type=cache,target=/root/.cache/uv bash -c 'source .venv/bin/activate && \
    uv pip install --index-strategy unsafe-best-match "warp-lang==1.8.1"'

# Install the lehome challenge environment package from its repo (reference
# only — the challenge itself is not bundled in this image).
RUN git clone --depth 1 https://github.com/lehome-official/lehome-challenge.git lehome-challenge \
    && bash -c 'source .venv/bin/activate && cd lehome-challenge && uv pip install -e ./source/lehome'

# Force torch to the cu128 build Isaac Sim 5.1.0 expects. `uv sync` resolves
# torch==2.7.0 from PyPI (the cu126 wheel). Pin the exact +cu128 local version
# so uv actually swaps the wheel. UV_HTTP_TIMEOUT is raised because
# pypi.nvidia.com is flaky for the nvidia-*-cu12 deps.
RUN --mount=type=cache,target=/root/.cache/uv bash -c 'export UV_HTTP_TIMEOUT=600; source .venv/bin/activate && \
    uv pip install --index-strategy unsafe-best-match "torch==2.7.0+cu128" "torchvision==0.22.0+cu128"'

ENV __GLX_VENDOR_LIBRARY_NAME=nvidia

# Keep the container alive so `docker compose exec lehome ...` works.
CMD ["sleep", "infinity"]
