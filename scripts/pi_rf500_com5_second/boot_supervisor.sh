#!/usr/bin/env bash
# Pi 5 #2 (Tailscale 100.94.161.96): persistent, COM5-serial-pinned RF500.
# Only returns validated roast result to ATmega after 900 sensor frames.
set -u
WORK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(cd "$WORK/../.." && pwd)"
PYTHON="$BASE/.venv/bin/python"
FTDI="/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0"
mkdir -p "$WORK/recordings"
chmod 700 "$WORK" "$WORK/recordings"
export PYTHONPATH="$WORK"
exec 9>"$WORK/singleton.lock"
if ! flock -n 9; then
    echo "COM5_RF500_SUPERVISOR_ALREADY_RUNNING"
    exit 0
fi
echo "$$" > "$WORK/supervisor.pid"
trap 'rm -f "$WORK/supervisor.pid"; exit 0' TERM INT
attempt=0
while true; do
    if [[ -L "$FTDI" && -e "$FTDI" ]]; then
        echo "$(date -Is) COM5_RF500_START_ATTEMPT $((attempt+1))"
        "$PYTHON" -u "$WORK/rf500_pi_persistent_listener.py" \
            --serial-live "$FTDI" \
            --model "$BASE/final_model.joblib" \
            --metadata "$BASE/final_model_info.json" \
            --archive-dir "$WORK/recordings"
        code=$?
        echo "$(date -Is) COM5_RF500_CHILD_EXIT $code"
    else
        echo "$(date -Is) COM5_RF500_WAIT_FTDI_A10KMM3S"
    fi
    attempt=$((attempt+1))
    case "$attempt" in
        1) delay=15 ;;
        2) delay=30 ;;
        3) delay=60 ;;
        *) delay=120 ;;
    esac
    sleep "$delay" &
    wait $!
done
