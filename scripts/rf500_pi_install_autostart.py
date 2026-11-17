#!/usr/bin/env python3
"""Pi-only, no-sudo cron @reboot registration for RF500 boot supervisor.

Keeps unrelated crontab entries; idempotent; do not write a duplicate line.
Run only after copying and validating the pinned persistent listener.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

BASE = Path.home() / "smart-coffee-stage7/rf30_staging"
WORK = BASE / "com4_integration_20261117/always_on"
ENTRY = (
    "@reboot /usr/bin/flock -n /home/enose-v3/smart-coffee-stage7/"
    "rf30_staging/com4_integration_20261117/always_on/cron.lock "
    "/bin/bash /home/enose-v3/smart-coffee-stage7/rf30_staging/"
    "com4_integration_20261117/always_on/rf500_pi_boot_supervisor.sh "
    ">> /home/enose-v3/smart-coffee-stage7/rf30_staging/"
    "com4_integration_20261117/always_on/supervisor.log 2>&1"
)


def install() -> None:
    if os.geteuid() == 0 or Path.home() != Path("/home/enose-v3"):
        raise RuntimeError("MUST_RUN_AS_PI_ENOSE_V3_USER_NOT_ROOT")
    for name in ("rf500_pi_boot_supervisor.sh", "rf500_pi_persistent_listener.py"):
        if not (WORK / name).is_file():
            raise RuntimeError("PERSISTENT_LISTENER_NOT_STAGED_" + name)
    p = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if p.returncode not in (0, 1):
        raise RuntimeError("CANNOT_READ_EXISTING_CRONTAB")
    current = p.stdout if p.returncode == 0 else ""
    if p.returncode == 1 and "no crontab for" not in p.stderr.lower():
        raise RuntimeError("CRONTAB_READ_FAILURE")
    if ENTRY in current.splitlines():
        print("RF500_CRON_AUTOSTART_ALREADY_PRESENT", flush=True)
        return
    if any("rf500_pi_boot_supervisor.sh" in x for x in current.splitlines()):
        raise RuntimeError("EXISTING_RF500_CRON_ENTRY_MUST_BE_REVIEWED")
    updated = current.rstrip("\n") + ("\n" if current.strip() else "") + ENTRY + "\n"
    saved = subprocess.run(["crontab", "-"], input=updated,
                           text=True, capture_output=True)
    if saved.returncode:
        raise RuntimeError("CRONTAB_INSTALL_FAILED:" + saved.stderr[:140])
    check = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if check.returncode or ENTRY not in check.stdout.splitlines():
        raise RuntimeError("CRONTAB_AUTOSTART_VERIFICATION_FAILED")
    print("RF500_CRON_AUTOSTART_INSTALLED_VERIFIED", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--install", action="store_true",
                        help="Register the idempotent @reboot entry in the user's crontab")
    action.add_argument("--check", action="store_true",
                        help="Read-only status of existing cron entry")
    opts = parser.parse_args()
    try:
        if opts.install:
            install()
        else:
            p = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            if p.returncode == 0 and ENTRY in p.stdout.splitlines():
                print("RF500_CRON_AUTOSTART_PRESENT", flush=True)
            else:
                print("RF500_CRON_AUTOSTART_MISSING", flush=True)
                sys.exit(3)
    except (OSError, RuntimeError) as exc:
        print("RF500_AUTOSTART_INSTALL_STOP", str(exc), file=sys.stderr)
        sys.exit(2)
