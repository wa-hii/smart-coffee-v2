"""Diagnostic only: inspect USB COM candidates, do not open port or send data.

Use --expect-port COM11 --usb-serial A10KNJBLA for PCB kedua FT232RL onboard.
The expected serial identifies the *USB bridge*, not the MCU/bootloader.
"""
import argparse
import json
from serial.tools import list_ports
from usb_autodetect import discover_port


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expect-port', help='Expected Windows COM port, e.g. COM11')
    parser.add_argument('--usb-serial', help='Expected FTDI USB serial identity')
    args = parser.parse_args(argv)
    ports = []
    for p in list_ports.comports():
        ports.append({"port": p.device, "description": p.description,
                      "vid_pid": f"{p.vid:04X}:{p.pid:04X}" if p.vid is not None and p.pid is not None else None,
                      "usb_serial": p.serial_number})
    picked = discover_port(serial_number=args.usb_serial)
    matching_port = args.expect_port is None or (
        picked.port is not None and picked.port.casefold() == args.expect_port.casefold()
    )
    if args.expect_port is None and args.usb_serial is None:
        # Preserve the existing generic diagnostic: an unplugged board is
        # normal during setup, so report rather than returning an error.
        status = 'OBSERVATION_ONLY'
    else:
        status = ('PASS_USB_BRIDGE_ONLY' if picked.port is not None and matching_port
                  else 'TARGET_PORT_OR_USB_SERIAL_MISMATCH')
    print(json.dumps({"ports_seen": ports, "selection":picked.port,
                      "reason":picked.reason, "candidates":list(picked.candidates),
                      "expected_port": args.expect_port, "expected_usb_serial": args.usb_serial,
                      "status": status, "mcu_bootloader_verified": False,
                      "serial_port_opened": False},
                     ensure_ascii=False, indent=2))
    return 0 if status in ('PASS_USB_BRIDGE_ONLY', 'OBSERVATION_ONLY') else 2


if __name__ == '__main__':
    raise SystemExit(main())
