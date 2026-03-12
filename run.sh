#!/bin/bash
# PM Newsletter — Weekly cron wrapper
# Runs every Monday at 8:00 AM PT

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/output/cron.log"
VENV="$SCRIPT_DIR/venv/bin/activate"

mkdir -p "$SCRIPT_DIR/output"

echo "=== PM Newsletter Run: $(date) ===" >> "$LOG_FILE"

source "$VENV"
cd "$SCRIPT_DIR"

python generate.py 2>&1 | tee -a "$LOG_FILE"

echo "=== Completed: $(date) ===" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
