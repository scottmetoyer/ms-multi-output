#!/usr/bin/env bash
# Build the .syx packer this project depends on.
#
# elektron-firmware-tool (MIT, Marcel Bierling) unpacks, repacks and re-signs
# Elektron OS images. It is cloned rather than vendored so you get it from the
# author, at whatever version upstream is on, with its own licence attached.
set -euo pipefail
cd "$(dirname "$0")"

REPO=https://github.com/mischa85/elektron-firmware-tool.git
DIR=vendor/elektron-firmware-tool

if [ ! -d "$DIR" ]; then
    echo "[setup] cloning elektron-firmware-tool"
    git clone -q --depth 1 "$REPO" "$DIR"
fi

echo "[setup] building"
make -s -C "$DIR"

if [ ! -x "$DIR/elektron-firmware-tool" ]; then
    echo "!! build produced no binary at $DIR/elektron-firmware-tool" >&2
    exit 1
fi

echo
echo "ok: $DIR/elektron-firmware-tool"
echo
echo "Next: download model-samples_OS1.13.zip from elektron.se, unzip it, then"
echo "      python3 build.py --syx model-samples_OS1.13.syx"
