#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PATH="${VENV_PATH:-$ROOT_DIR/.venv}"
PY_BIN="$VENV_PATH/bin/python"

if [ ! -d "$VENV_PATH" ]; then
  python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"

pip install -r "$ROOT_DIR/backend/requirements.txt"

export FLASK_APP=backend.app
export STORAGE_DIR="${STORAGE_DIR:-$ROOT_DIR/backend/storage}"
PORT="${PORT:-5000}"

exec gunicorn app:app --chdir "$ROOT_DIR/backend" --bind "0.0.0.0:$PORT"
