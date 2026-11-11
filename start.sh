#!/bin/bash
# Runs the urcast sensor loop from this repository's virtual environment.
# This is what urcast.service executes on boot, so it must never prompt or wait
# for a terminal. Logs go to the systemd journal.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$REPO_DIR/venv/bin/python"

cd "$REPO_DIR"

# Never block on an interactive prompt, even if run from a terminal.
exec </dev/null

if [ ! -x "$PYTHON" ]; then
    echo "urcast: no virtual environment at $REPO_DIR/venv" >&2
    echo "urcast: create it with:" >&2
    echo "  python -m venv venv" >&2
    echo "  source venv/bin/activate" >&2
    echo "  pip install -r requirements.txt" >&2
    exit 1
fi

if [ ! -f "$REPO_DIR/.env" ]; then
    echo "urcast: no .env at $REPO_DIR/.env" >&2
    echo "urcast: run 'python setup_node.py --setup-only' as the service user" >&2
    exit 1
fi

# -u keeps the timestamped sample lines flushing to the journal as they happen
# instead of sitting in a pipe buffer.
exec "$PYTHON" -u "$REPO_DIR/run.py"
