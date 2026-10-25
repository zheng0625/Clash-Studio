#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source "$HOME/.cargo/env"
python3 -m venv .venv-linux
.venv-linux/bin/pip install 'fastapi==0.159.1' 'uvicorn==0.54.0' 'httpx==0.28.1' 'ruamel.yaml==0.19.1' pytest packaging
.venv-linux/bin/python -B scripts/fetch-linux-core.py
pkg-config --modversion webkit2gtk-4.1 gtk+-3.0 ayatana-appindicator3-0.1
export CARGO_BUILD_JOBS=4
cargo test --manifest-path src-tauri/Cargo.toml --release
cargo build --manifest-path src-tauri/Cargo.toml --release
.venv-linux/bin/python -B scripts/build-linux-portable.py
