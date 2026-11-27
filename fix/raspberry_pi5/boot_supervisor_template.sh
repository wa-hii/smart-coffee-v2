#!/bin/bash
# Portable template, not the exact deployed host-specific supervisor.
# Run only after exclusive ownership and hardware/operator approval.
set -eu
if [[ $# -ne 6 || ( "$1" != --check && "$1" != --run ) ]]; then
  echo 'Usage: bash boot_supervisor_template.sh --check|--run FTDI_ID PYTHON MODEL METADATA DATA_ROOT' >&2
  exit 2
fi
ACTION=$1; ID=$2; PYTHON=$3; MODEL=$4; META=$5; DATA=$6
case "$ID" in A10KMZQJ|A10KMM3S|A10KN6X9) ;; *) echo 'UNKNOWN_FTDI_STOP' >&2; exit 2;; esac
BASE="$(cd -- "$(dirname -- "$0")" && pwd)"
PORT="/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_${ID}-if00-port0"
[[ -x "$PYTHON" && -f "$MODEL" && -f "$META" && -d "$DATA" ]] || { echo 'MISSING_REQUIRED_PATH_STOP'; exit 2; }
export PYTHONPATH="$BASE/runtime"
check() {
  "$PYTHON" -P -B -c 'from pathlib import Path; import sys; from rf500_pi_persistent_listener import verify_host; verify_host(*map(Path,sys.argv[1:])); print("READ_ONLY_PREFLIGHT_PASS")' "$PORT" "$MODEL" "$META"
}
if [[ "$ACTION" == --check ]]; then check; exit; fi
STATE="$HOME/.local/state/smart-coffee-waveform-v5/$ID"
mkdir -p "$STATE/recordings"; chmod 700 "$STATE" "$STATE/recordings"
exec 9>"$STATE/singleton.lock"; flock -n 9 || { echo 'SUPERVISOR_ALREADY_RUNNING'; exit 2; }
child=''
stop() { if [[ -n "$child" ]]; then kill -TERM "$child" 2>/dev/null || true; wait "$child" 2>/dev/null || true; fi; exit 0; }
trap stop TERM INT
delay=15
while true; do
  if [[ -L "$PORT" && -e "$PORT" ]]; then
    # Do not contend with an existing serial reader. Linux exclusive open
    # inside the unchanged listener is the second ownership guard.
    if ! command -v fuser >/dev/null; then echo 'FUSER_MISSING_STOP'; exit 2; fi
    if fuser "$PORT" >/dev/null 2>&1; then echo "$(date -Is) PORT_BUSY_STOP"; exit 2; fi
    if ! check; then echo 'PREFLIGHT_FAILED_STOP'; exit 2; fi
    echo "$(date -Is) RF500_TEMPLATE_START $ID"
    "$PYTHON" -B -u "$BASE/runtime/rf500_pi_persistent_listener.py" --serial-live "$PORT" --model "$MODEL" --metadata "$META" --archive-dir "$STATE/recordings" --take-data-dir "$DATA" &
    child=$!; wait "$child" || true; child=''
  else
    echo "$(date -Is) RF500_TEMPLATE_WAIT_FTDI_$ID"
  fi
  sleep "$delay" & child=$!; wait "$child" || true; child=''
  if [[ "$delay" -lt 120 ]]; then delay=$((delay*2)); fi
done
