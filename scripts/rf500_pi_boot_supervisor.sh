#!/bin/bash
# Long-lived, single-owner Pi5 RF500 bridge. Designed for user cron @reboot.
# It is NOT a control program: only the Python bridge sends session-bound
# roast results, and only after 900 frames and MCU session handshake.
set -u
BASE=/home/enose-v3/smart-coffee-stage7/rf30_staging
WORK="$BASE/com4_integration_20261117/always_on"
# 25 November: this Pi is now connected to the formerly Windows COM3 board.
# Keep the USB identity pinned; do not auto-select ttyUSB0.
FTDI=/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KN6X9-if00-port0
PYTHON="$BASE/.venv/bin/python"
export PYTHONPATH="$BASE${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$WORK/recordings"
chmod 700 "$WORK" "$WORK/recordings"
exec 9>"$WORK/singleton.lock"
if ! flock -n 9; then
    echo "RF500_SUPERVISOR_ALREADY_RUNNING"
    exit 0
fi
echo "$$" > "$WORK/supervisor.pid"
trap 'rm -f "$WORK/supervisor.pid"; exit 0' TERM INT
attempt=0
while true; do
    if [[ -L "$FTDI" && -e "$FTDI" ]]; then
        echo "$(date -Is) RF500_SUPERVISOR_START_ATTEMPT $((attempt+1))"
        "$PYTHON" -u "$WORK/rf500_pi_persistent_listener.py" \
            --serial-live "$FTDI" \
            --model "$BASE/final_model.joblib" \
            --metadata "$BASE/final_model_info.json" \
            --archive-dir "$WORK/recordings"
        code=$?
        echo "$(date -Is) RF500_SUPERVISOR_CHILD_EXIT $code"
    else
        echo "$(date -Is) RF500_SUPERVISOR_WAIT_FTDI_A10KN6X9"
    fi
    attempt=$((attempt+1))
    # Exponential bounded backoff prevents continuous DTR resets on
    # an unhealthy MCU/serial wiring: 15, 30, 60, 120 seconds.
    case "$attempt" in
        1) delay=15 ;;
        2) delay=30 ;;
        3) delay=60 ;;
        *) delay=120 ;;
    esac
    sleep "$delay" &
    wait $!
done
