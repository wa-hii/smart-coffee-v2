"""Diagnostic only: inspect USB COM candidates, do not open port or send data."""
import json
from serial.tools import list_ports
from usb_autodetect import discover_port


def main():
    ports = []
    for p in list_ports.comports():
        ports.append({"port": p.device, "description": p.description,
                      "vid_pid": f"{p.vid:04X}:{p.pid:04X}" if p.vid is not None and p.pid is not None else None,
                      "usb_serial": p.serial_number})
    picked = discover_port()
    print(json.dumps({"ports_seen": ports, "selection":picked.port,
                      "reason":picked.reason, "candidates":list(picked.candidates)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
