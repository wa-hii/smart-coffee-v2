"""Safely recover completed 30-cycle CSV from an old portable receiver.

Default is dry-run. --apply copies *validated final CSV only*, preserves both
source and any existing destination, and verifies SHA256 on each side.
Does not touch serial ports, logs, partial/incomplete acquisitions or hardware.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import uuid

from validate_acquisition import validate_file

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def recover(source: Path, dest: Path, *, apply: bool = False) -> dict:
    source, dest = source.resolve(), dest.resolve()
    if source == dest:
        raise ValueError('Source and destination are the same directory')
    if not source.is_dir():
        raise FileNotFoundError(f'Source raw folder not found: {source}')
    if apply:
        dest.mkdir(parents=True, exist_ok=True)

    results = {'valid': 0, 'invalid_skipped': 0, 'identical_skipped': 0,
               'copied': [], 'would_copy': [], 'invalid': []}
    for file in sorted(source.glob('*.csv')):
        errors = validate_file(file, expected_cycles=30)
        if errors:
            results['invalid_skipped'] += 1
            results['invalid'].append({'name': file.name, 'reasons': errors})
            continue
        results['valid'] += 1
        sha = digest(file)
        # Only finished, validated CSV, never .incoming, incomplete or partial.
        candidates = sorted(dest.glob(f'{file.stem}*.csv')) if dest.is_dir() else []
        if any(digest(existing) == sha for existing in candidates):
            results['identical_skipped'] += 1
            continue
        if not apply:
            results['would_copy'].append(file.name)
            continue
        # Stage in destination filesystem; publish atomically without replacing
        # any existing file, even if another process creates it concurrently.
        stage = dest / f'.recover_{uuid.uuid4().hex}.tmp'
        try:
            with file.open('rb') as inp, stage.open('xb') as out:
                shutil.copyfileobj(inp, out)
                out.flush()
                os.fsync(out.fileno())
            if digest(file) != sha or digest(stage) != sha:
                raise RuntimeError(f'Source changed during copy: {file.name}')
            target = dest / file.name
            for i in range(1000):
                try:
                    os.link(stage, target)
                    break
                except FileExistsError:
                    # A collision must not overwrite or silently discard data.
                    target = dest / f'{file.stem}_RECOVERED_{i + 1:03}.csv'
            else:
                raise RuntimeError(f'Cannot allocate safe filename: {file.name}')
            if digest(target) != sha or validate_file(target, expected_cycles=30):
                raise RuntimeError(f'Post-copy validation failed: {target}')
            results['copied'].append({'name': target.name, 'sha256': sha})
        finally:
            stage.unlink(missing_ok=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Old receiver data/raw folder')
    parser.add_argument('--dest', type=Path, default=PROJECT_ROOT / 'data/raw')
    parser.add_argument('--apply', action='store_true', help='Copy files after validation')
    args = parser.parse_args()
    import json
    print(json.dumps(recover(args.source, args.dest, apply=args.apply),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
