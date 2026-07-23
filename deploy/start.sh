#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_DIR="$(pwd)"

# Calling the venv's python binary directly gives the same isolation as `source
# .venv/bin/activate` without needing an interactive-shell step first.
exec "$PROJECT_DIR/.venv/bin/python" -m bot.main
