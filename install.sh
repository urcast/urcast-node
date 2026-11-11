#!/bin/bash
# Installs urcast-node as a systemd service that starts on boot.
# Run this after `python setup_node.py --setup-only` has created .env:
#   chmod +x install.sh
#   ./install.sh

set -euo pipefail

SERVICE_NAME="urcast"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER="${SUDO_USER:-${USER}}"

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

echo "Setting up ${SERVICE_NAME}.service"
echo "  user: $SERVICE_USER"
echo "  path: $REPO_DIR"

if [ "$(uname -s)" != "Linux" ] || ! command -v systemctl >/dev/null 2>&1; then
    echo "This installer needs Linux with systemd." >&2
    exit 1
fi

if [ ! -f "$REPO_DIR/run.py" ] || [ ! -f "$REPO_DIR/start.sh" ]; then
    echo "run.py and start.sh must sit next to install.sh." >&2
    exit 1
fi

if [ ! -x "$REPO_DIR/venv/bin/python" ]; then
    echo "No virtual environment at $REPO_DIR/venv." >&2
    echo "Create it first:" >&2
    echo "  python -m venv venv" >&2
    echo "  source venv/bin/activate" >&2
    echo "  pip install -r requirements.txt" >&2
    exit 1
fi

if [ ! -f "$REPO_DIR/.env" ]; then
    echo "No .env file at $REPO_DIR/.env." >&2
    echo "Run the interactive setup first, then rerun this installer:" >&2
    echo "  python setup_node.py --setup-only" >&2
    exit 1
fi

if [ ! -x "$REPO_DIR/start.sh" ]; then
    if ! chmod +x "$REPO_DIR/start.sh"; then
        echo "start.sh is not executable and could not be chmod'ed." >&2
        echo "Fix it with: chmod +x $REPO_DIR/start.sh" >&2
        exit 1
    fi
fi

TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

cat > "$TMP_FILE" <<EOF
[Unit]
Description=urCast Telemetry Reporter
After=network-online.target time-sync.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$REPO_DIR
ExecStart=$REPO_DIR/start.sh
StandardInput=null
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=10
KillSignal=SIGINT

[Install]
WantedBy=multi-user.target
EOF

$SUDO install -m 0644 "$TMP_FILE" "$SERVICE_FILE"

$SUDO systemctl daemon-reload
$SUDO systemctl enable "$SERVICE_NAME.service"
$SUDO systemctl restart "$SERVICE_NAME.service"

echo
echo "Setup complete. ${SERVICE_NAME}.service is enabled and running."
echo "  status:  systemctl status ${SERVICE_NAME}"
echo "  logs:    journalctl -u ${SERVICE_NAME} -f"
echo "  restart: sudo systemctl restart ${SERVICE_NAME}"
echo "  stop:    sudo systemctl stop ${SERVICE_NAME}"
