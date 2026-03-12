#!/bin/bash
# Title: Neon Bikes
# Description: Light cycle arena game - race your neon trail against the CPU
# Author: wickedNull
# Version: 1.1
# Category: Games

PAYLOAD_DIR="/root/payloads/user/games/neon_bikes"
LOG_FILE="/tmp/neon_bikes.log"

cd "$PAYLOAD_DIR" || { LOG "red" "ERROR: $PAYLOAD_DIR not found"; exit 1; }

# ── Locate pagerctl ──────────────────────────────────────────────────────────
PAGERCTL_FOUND=false
for dir in "$PAYLOAD_DIR/lib" \
           "/root/payloads/user/utilities/PAGERCTL" \
           "/mmc/root/payloads/user/utilities/PAGERCTL"; do
    if [ -f "$dir/libpagerctl.so" ] && [ -f "$dir/pagerctl.py" ]; then
        PAGERCTL_DIR="$dir"
        PAGERCTL_FOUND=true
        break
    fi
done

if [ "$PAGERCTL_FOUND" = false ]; then
    LOG "red" "pagerctl not found! Install PAGERCTL utility first."
    WAIT_FOR_INPUT >/dev/null 2>&1
    exit 1
fi

# Copy libs into payload's own lib/ so the .so is always alongside pagerctl.py
if [ "$PAGERCTL_DIR" != "$PAYLOAD_DIR/lib" ]; then
    mkdir -p "$PAYLOAD_DIR/lib" 2>/dev/null
    cp "$PAGERCTL_DIR/libpagerctl.so" "$PAYLOAD_DIR/lib/" 2>/dev/null
    cp "$PAGERCTL_DIR/pagerctl.py"    "$PAYLOAD_DIR/lib/" 2>/dev/null
fi

# ── Environment ──────────────────────────────────────────────────────────────
export PATH="/mmc/usr/bin:/mmc/usr/sbin:$PATH"
export LD_LIBRARY_PATH="$PAYLOAD_DIR/lib:/mmc/usr/lib:/mmc/lib:$LD_LIBRARY_PATH"
export PYTHONPATH="$PAYLOAD_DIR/lib:$PAYLOAD_DIR:$PYTHONPATH"
# Do NOT set PYTHONHOME — breaks MMC python stdlib lookup

PYTHON=$(command -v python3)
if [ -z "$PYTHON" ]; then
    LOG "red" "python3 not found!"
    WAIT_FOR_INPUT >/dev/null 2>&1
    exit 1
fi

# ── Splash ───────────────────────────────────────────────────────────────────
LOG "cyan" "NEON BIKES"
LOG "" "by wickedNull"
LOG "" ""
LOG "green" "Light cycle arena — you vs CPU"
LOG "" ""
LOG "" "  D-PAD  → Steer"
LOG "" "  GREEN  → Start / Restart"
LOG "" "  RED    → Quit / Back"
LOG "" ""
LOG "yellow" "Press GREEN to start..."
WAIT_FOR_INPUT >/dev/null 2>&1

# ── Stop pager service, hand off to Python ───────────────────────────────────
SPINNER_ID=$(START_SPINNER "Loading Neon Bikes...")
/etc/init.d/pineapplepager stop 2>/dev/null
sleep 0.5
STOP_SPINNER "$SPINNER_ID" 2>/dev/null

"$PYTHON" "$PAYLOAD_DIR/neon_bikes.py" "$PAYLOAD_DIR/lib" > "$LOG_FILE" 2>&1
EXIT_CODE=$?

# ── Restore pager service ────────────────────────────────────────────────────
/etc/init.d/pineapplepager start 2>/dev/null

if [ $EXIT_CODE -ne 0 ]; then
    LOG "red" "Neon Bikes exited with error (code $EXIT_CODE)"
    LOG "red" "Check /tmp/neon_bikes.log for details"
    WAIT_FOR_INPUT >/dev/null 2>&1
fi
