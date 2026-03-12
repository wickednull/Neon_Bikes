#!/bin/bash
# Title: Neon Bikes
# Description: Neon Bikes — Leave your trail, own the grid. Go head-to-head against a CPU light cycle in this retro arcade game built for the WiFi Pineapple Pager. Dodge walls, outlast your opponent, and light up the arena. Steer with the D-Pad. GREEN to start. RED to quit. Game on.
# Author: wickedNull
# Version: 1.2
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

PYTHON=$(command -v python3)
if [ -z "$PYTHON" ]; then
    LOG "red" "python3 not found!"
    exit 1
fi

# ── Stop pager service, hand off to Python ───────────────────────────────────
/etc/init.d/pineapplepager stop 2>/dev/null
sleep 0.5

"$PYTHON" "$PAYLOAD_DIR/neon_bikes.py" "$PAYLOAD_DIR/lib" > "$LOG_FILE" 2>&1
EXIT_CODE=$?

# ── Restore pager service ────────────────────────────────────────────────────
/etc/init.d/pineapplepager start 2>/dev/null

if [ $EXIT_CODE -ne 0 ]; then
    LOG "red" "Neon Bikes crashed (code $EXIT_CODE)"
    LOG "red" "Check /tmp/neon_bikes.log"
fi
