"""Read-only incident report for three independent E-Nose USB receivers.

Never opens COM, drives hardware, sends commands, or changes CSV files.
Can be used DURING Take Data without disturbing the receiver processes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[1]
EVENT_RE = re.compile(
    r'ACQ START|ACQ COMPLETE|ACQ INCOMPLETE|ACQ_COMPLETE|'
    r'Acquisition validation|Timing QA|COM connection unavailable|'
    r'CONNECTED|USB waiting|Sensor payload ditolak|'
    r'host receive timeout|transport error|Reject|Gagal membuat', re.IGNORECASE
)


def read_status(path: Path) -> dict:
    if not path.is_file():
        return {'state': 'status_missing'}
    try:
        content = json.loads(path.read_text(encoding='utf-8'))
        return content if isinstance(content, dict) else {'state': 'status_invalid'}
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return {'state': 'status_unreadable', 'reason': type(exc).__name__}


def recent_events(folder: Path, limit: int = 12) -> list[str]:
    rotated = [folder / f'acquisition_service.log.{i}' for i in (3, 2, 1)]
    files = rotated + [folder / 'acquisition_service.log']
    found: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        try:
            # Logs are rotated at 2 MB, so read-only bounded by policy.
            with path.open(encoding='utf-8', errors='replace') as stream:
                for line in stream:
                    if EVENT_RE.search(line):
                        found.append(line.strip())
                        found = found[-limit:]
        except OSError:
            found.append(f'UNREADABLE LOG: {path.name}')
    return found


def files_summary(folder: Path, pattern: str, limit: int = 6) -> list[dict]:
    if not folder.is_dir():
        return []
    candidates = (p for p in folder.glob(pattern) if p.is_file())
    latest = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [{'name': f.name, 'bytes': f.stat().st_size} for f in latest]


def inspect_root(root: Path, *, ports: list | None = None) -> dict:
    port_list = list_ports.comports() if ports is None else ports
    report = {'root': str(root), 'usb_ports': [
        {'port': p.device, 'serial': p.serial_number,
         'vid_pid': (f'{p.vid:04X}:{p.pid:04X}'
                     if p.vid is not None and p.pid is not None else 'unknown')}
        for p in port_list], 'devices': {}}
    for index in range(1, 4):
        label = f'ALAT_{index}'
        raw = root / 'data' / 'raw' / 'devices' / label
        logs = root / 'logs' / 'devices' / label
        status = read_status(logs / 'acquisition_service.status.json')
        report['devices'][label] = {
            'status': status,
            'final_csv': files_summary(raw, '*.csv'),
            'incomplete_csv': files_summary(raw / 'incomplete', '*_INCOMPLETE.csv'),
            'incoming_partial': files_summary(raw / '.incoming', '*.partial.csv'),
            'recent_events': recent_events(logs),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT,
                        help='Extracted SmartCoffee_Receiver folder')
    parser.add_argument('--output', type=Path,
                        help='Optional explicit location for a report JSON; default stdout')
    args = parser.parse_args()
    report = inspect_root(args.root)
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + '\n', encoding='utf-8')
        print('Read-only incident report saved:', args.output)
    else:
        print(serialized)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
