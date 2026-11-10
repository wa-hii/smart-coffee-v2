#!/usr/bin/env python3
"""Hardware-safe SSH preflight for Smart Coffee Pi 5.

Read-only OS/sysfs/process inventory. Does not open serial ports, alter
services, load a joblib model, trigger actuators or flash firmware.
Emit only public device metadata; avoid passwords, secrets and user data.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def call(args, timeout=5):
    try:
        p=subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                         errors="replace", check=False)
        return {"returncode":p.returncode, "output":p.stdout[:2800],
                "error":p.stderr[:450]}
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError) as e:
        return {"error":type(e).__name__}


def main():
    print("RF30_PI_READ_ONLY_PREFLIGHT_BEGIN", flush=True)
    serial=Path("/dev/serial/by-id")
    byid={}
    if serial.is_dir():
        for p in sorted(serial.iterdir()):
            if p.is_symlink():
                byid[p.name]=os.path.realpath(str(p))
    roots=[
        Path.home()/"smart-coffee-stage7",
        Path.home()/"smart-coffee-v2",
        Path.home()/"smart-coffee-rf30",
        Path.home()/"smart-coffee",
    ]
    interesting=("final_model.joblib","final_model_info.json",
                 "roast_rf30_pi_inference.py","stage7_pi_adapter.py",
                 "stage7_usb_readonly_probe.py")
    files={}
    for root in roots:
        files[str(root)]={
            "exists":root.exists(),
            "items":{name:[
                {"path":str(x.relative_to(root)),"size":x.stat().st_size}
                for x in list(root.glob("**/"+name))[:6]
                if x.is_file() and not x.is_symlink()
            ] for name in interesting} if root.is_dir() else {},
        }
    tty={name:{"exists":Path("/dev",name).exists()}
         for name in ("ttyUSB0","ttyUSB1","ttyACM0","ttyAMA0")}
    owners={}
    for name in byid.values():
        if Path(name).exists():
            owners[name]=call(["fuser",name])
    services={}
    for svc in ("ModemManager.service","serial-getty@ttyUSB0.service",
                "ssh.service"):
        services[svc]=call(["systemctl","is-active",svc])
    # List only sensor/port-related running process COMMAND NAMES, avoid cmdline.
    running=call(["ps","-eo","pid=,comm="])
    filtered=[]
    for line in running.get("output","").splitlines():
        if re.search(r"python|serial|modem|platformio|screen|picocom",line,re.I):
            filtered.append(line.strip()[:95])
    payload={
        "time":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host":call(["hostname"]).get("output","").strip(),
        "platform":call(["uname","-m"]).get("output","").strip(),
        "pi_model":Path("/proc/device-tree/model").read_bytes().rstrip(b"\0").decode("utf8","replace")
            if Path("/proc/device-tree/model").exists() else "unavailable",
        "uptime":call(["uptime","-s"]).get("output","").strip(),
        "usb_enum":call(["lsusb"]),
        "tty":tty,
        "serial_by_id":byid,
        "port_owners":owners,
        "service_status":services,
        "throttled":call(["vcgencmd","get_throttled"]),
        "kernel_usb_recent":call(["journalctl","-k","-n","45","--no-pager"]),
        "known_project_roots":files,
        "relevant_process_names":filtered[:30],
        "serial_device_opened":False,
        "writes_to_pi":False,
        "model_joblib_loaded":False,
    }
    print(json.dumps(payload,indent=2,ensure_ascii=True),flush=True)
    return 0


if __name__=="__main__":
    sys.exit(main())
