#!/usr/bin/env bash
#
# Downloads LeHome Challenge data onto the HOST, where the compose setup
# mounts it as volumes (Assets/, Datasets/). Nothing is baked into the image.
#
#   - simulation assets -> ../Assets
#   - example dataset   -> ../Datasets
#
# Safe to re-run: `hf download` resumes partial files.
#
# Requirements: the HuggingFace CLI (`hf`) — install with:
#   pip install -U "huggingface_hub[cli]"
#
# Usage:
#   ./download-assets.sh              # assets + example dataset (default)
#   ./download-assets.sh -a           # assets only
#   ./download-assets.sh -d           # dataset only

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ASSETS_DIR="$REPO_ROOT/Assets"
DATASETS_DIR="$REPO_ROOT/Datasets"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[download]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
die() {
	echo -e "${RED}[error]${NC} $*" >&2
	exit 1
}

usage() {
	cat <<EOF
Usage: ./download-assets.sh [OPTIONS]

Downloads the LeHome Challenge resources into the repo (../Assets, ../Datasets).

Options:
  -a, --assets      Simulation assets -> Assets/
  -d, --dataset     Example demonstration dataset -> Datasets/example/
  -h, --help        Show this help and exit

If no flags are given, downloads the simulation assets and the example dataset.
EOF
}

DO_ASSETS=0
DO_DATASET=0

while [[ $# -gt 0 ]]; do
	case "$1" in
	-a | --assets) DO_ASSETS=1 ;;
	-d | --dataset) DO_DATASET=1 ;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		warn "Unknown option: $1"
		usage
		exit 1
		;;
	esac
	shift
done

# Default: assets + example dataset.
if [[ $DO_ASSETS -eq 0 && $DO_DATASET -eq 0 ]]; then
	DO_ASSETS=1
	DO_DATASET=1
fi

command -v hf >/dev/null 2>&1 || die "The 'hf' CLI is required. Install it with: pip install -U 'huggingface_hub[cli]'"

mkdir -p "$ASSETS_DIR" "$DATASETS_DIR"

if [[ $DO_ASSETS -eq 1 ]]; then
	log "Downloading simulation assets -> $ASSETS_DIR"
	hf download lehome/asset_challenge --repo-type dataset --local-dir "$ASSETS_DIR"
fi

if [[ $DO_DATASET -eq 1 ]]; then
	log "Downloading example dataset -> $DATASETS_DIR/example"
	hf download lehome/dataset_challenge_merged --repo-type dataset --local-dir "$DATASETS_DIR/example"
fi

log "Done."
