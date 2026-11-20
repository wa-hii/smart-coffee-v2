#!/usr/bin/env python3
"""Read-only preflight or cron install on Pi #2 for pinned COM5 RF500 listener.

Assumes trusted paired Python modules and the ORIGINAL exact RF500 joblib
have already been placed under ~/smart-coffee-stage7/rf30_staging.
No model replacement/retraining, no firmware writing, no UART TX.
Checks Tailscale IP 100.94.161.96 to prevent accidentally changing Pi #1.

Examples:
  .venv/bin/python com5_integration/always_on/installer.py --check
  .venv/bin/python com5_integration/always_on/installer.py --install
  .venv/bin/python com5_integration/always_on/installer.py --start
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import time

WORK = Path(__file__).resolve().parent
BASE = WORK.parents[1]
EXPECTED_IP = "100.94.161.96"
EXPECTED_USB = Path("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0")
SOURCE_FILES = (
    "rf500_pi_persistent_listener.py", "rf30_pi_result_bridge.py",
    "roast_rf30_pi_inference.py", "rf500_pi_verify_staged_bridge.py",
    "pi_labeled_take_data.py", "roast_rf30_pi_stream_replay.py",
    "boot_supervisor.sh",
)


def command(*args: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True,
                          errors="replace", timeout=timeout)


def check() -> None:
    if os.geteuid() == 0:
        raise RuntimeError("RUN_AS_NORMAL_PI_USER_NOT_ROOT")
    if Path.home() not in WORK.parents:
        raise RuntimeError("INSTALL_LOCATION_OUTSIDE_USERS_HOME")
    if not WORK.samefile(Path.home() / "smart-coffee-stage7/rf30_staging/com5_integration/always_on"):
        raise RuntimeError("COM5_RELEASE_LOCATION_MISMATCH")
    for file in SOURCE_FILES:
        if not (WORK / file).is_file():
            raise RuntimeError("MISSING_DEPLOY_FILE_" + file)
    if not (BASE / "final_model.joblib").is_file() or not (BASE / "final_model_info.json").is_file():
        raise RuntimeError("ORIGINAL_RF500_MODEL_AND_METADATA_MUST_BE_COPIED_FROM_PI1")
    if not (BASE / ".venv/bin/python").is_file():
        raise RuntimeError("RF500_ISOLATED_PYTHON_VENV_MISSING")
    ip = command("tailscale", "ip", "-4")
    if ip.returncode or EXPECTED_IP not in ip.stdout.split():
        raise RuntimeError("NOT_PI2_TAILSCALE_100_94_161_96")
    if not EXPECTED_USB.is_symlink() or not EXPECTED_USB.exists():
        raise RuntimeError("FTDI_COM5_SERIAL_A10KMM3S_NOT_DETECTED_ON_PI")
    target = EXPECTED_USB.resolve()
    if not target.name.startswith("ttyUSB"):
        raise RuntimeError("FTDI_SYMLINK_IS_NOT_TTYUSB")
    if not os.access(target, os.R_OK | os.W_OK):
        raise RuntimeError("FTDI_PERMISSION_DENIED_CHECK_DIALOUT_GROUP")
    p = command("udevadm", "info", "--query=property", "--name", str(target))
    if p.returncode:
        raise RuntimeError("UDEV_FTDI_PROVENANCE_UNAVAILABLE")
    props = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)
    if (props.get("ID_VENDOR_ID", "").lower() != "0403"
            or props.get("ID_MODEL_ID", "").lower() != "6001"
            or props.get("ID_SERIAL_SHORT") != "A10KMM3S"):
        raise RuntimeError("FTDI_VENDOR_PRODUCT_SERIAL_MISMATCH")
    power = command("vcgencmd", "get_throttled")
    if power.returncode or power.stdout.strip() != "throttled=0x0":
        raise RuntimeError("PI5_POWER_THROTTLED")
    # Validate the exact pinned RF500 model, metadata, binary, libraries,
    # bridge API and the target by-id without touching the serial port.
    p = command(str(BASE / ".venv/bin/python"), "-B",
                str(WORK / "rf500_pi_verify_staged_bridge.py"),
                "--serial-live", str(EXPECTED_USB), timeout=35)
    if p.returncode:
        raise RuntimeError("RF500_MODEL_OR_BRIDGE_PREFLIGHT_FAILED: " + (p.stderr or p.stdout)[-350:])
    print("COM5_PI2_READ_ONLY_PREFLIGHT_PASS", str(target), EXPECTED_IP, flush=True)
    print(p.stdout.strip(), flush=True)


def cron_line() -> str:
    lock = shlex.quote(str(WORK / "cron.lock"))
    supervisor = shlex.quote(str(WORK / "boot_supervisor.sh"))
    log = shlex.quote(str(WORK / "supervisor.log"))
    return f"@reboot /usr/bin/flock -n {lock} /bin/bash {supervisor} >> {log} 2>&1"


def install() -> None:
    check()
    if shutil.which("crontab") is None or shutil.which("flock") is None:
        raise RuntimeError("CRON_OR_FLOCK_UNAVAILABLE")
    if command("systemctl", "is-active", "cron.service").stdout.strip() != "active":
        raise RuntimeError("CRON_SERVICE_NOT_ACTIVE")
    old = command("crontab", "-l")
    if old.returncode not in (0, 1):
        raise RuntimeError("UNABLE_TO_READ_CRONTAB")
    if old.returncode == 1 and "no crontab for" not in old.stderr.lower():
        raise RuntimeError("CRONTAB_READ_ERROR")
    lines = old.stdout.splitlines() if old.returncode == 0 else []
    line = cron_line()
    if line not in lines:
        if any("boot_supervisor.sh" in item and "com5_integration" in item for item in lines):
            raise RuntimeError("CONFLICTING_EXISTING_COM5_AUTOSTART")
        p = subprocess.run(["crontab", "-"], input="\n".join((*lines, line, "")),
                           capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError("CRONTAB_WRITE_FAILED: " + p.stderr[:150])
    check_result = command("crontab", "-l")
    if check_result.returncode or line not in check_result.stdout.splitlines():
        raise RuntimeError("COM5_AUTOSTART_VERIFY_FAILED")
    print("COM5_RF500_AUTOSTART_REGISTERED_AND_VERIFIED", flush=True)


def start() -> None:
    check()
    pids = command("fuser", str(EXPECTED_USB.resolve()))
    if pids.returncode != 1 or pids.stdout.strip():
        raise RuntimeError("FTDI_PORT_ALREADY_IN_USE_DO_NOT_START_SECOND_LISTENER")
    # Supervisor detaches, no shell process should retain the SSH terminal.
    log_path = WORK / "supervisor.log"
    previous_log_size = log_path.stat().st_size if log_path.exists() else 0
    log = log_path.open("a", encoding="utf8")
    try:
        process = subprocess.Popen(
            ["/usr/bin/flock", "-n", str(WORK / "cron.lock"),
             "/bin/bash", str(WORK / "boot_supervisor.sh")],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, cwd=WORK)
    finally:
        log.close()
    time.sleep(4)
    status = log_path.read_bytes()[previous_log_size:].decode("utf8", "replace")
    holder = command("fuser", str(EXPECTED_USB.resolve()))
    if (process.poll() is not None or
            "RF500_PERSISTENT_READY" not in status or
            holder.returncode != 0 or not holder.stdout.strip()):
        raise RuntimeError("RF500_LISTENER_NOT_READY_INSPECT_SUPERVISOR_LOG")
    print("COM5_PI2_PERSISTENT_LISTENER_READY", "pid", process.pid, flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    options = cli.add_mutually_exclusive_group(required=True)
    options.add_argument("--check", action="store_true")
    options.add_argument("--install", action="store_true")
    options.add_argument("--start", action="store_true")
    args = cli.parse_args()
    try:
        if args.install:
            install()
        elif args.start:
            start()
        else:
            check()
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print("COM5_PI2_INSTALL_STOP", str(exc), file=sys.stderr)
        sys.exit(2)
