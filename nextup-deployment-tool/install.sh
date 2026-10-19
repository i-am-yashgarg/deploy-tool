#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE_DIR"

echo "========================================"
echo "NEXTUP ROBOTICS DEPLOYMENT TOOL"
echo "INSTALLER"
echo "========================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: Python 3 is not installed."
    exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
    echo "ERROR: Python venv support is missing."
    echo "Install python3-venv using your normal system process."
    exit 1
fi

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

chmod +x run.sh

DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_DIR/nextup-deployment-tool.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Nextup Robotics Deployment Tool
Comment=Robot deployment launcher
Exec=$BASE_DIR/run.sh
Path=$BASE_DIR
Terminal=false
Categories=Utility;
EOF

chmod +x "$DESKTOP_DIR/nextup-deployment-tool.desktop"

echo ""
echo "INSTALLATION COMPLETE"
echo "Launch from the application menu:"
echo "Nextup Robotics Deployment Tool"
