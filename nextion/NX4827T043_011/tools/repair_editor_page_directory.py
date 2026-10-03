#!/usr/bin/env python3
"""Repair stale page-directory pointers after Nextion Editor manual saves.

This utility is intentionally conservative. It does not rebuild any existing
page. It:
  * appends a known-good pSplash page blob,
  * repoints 0.pa to that appended pSplash,
  * repoints 2.pa to an already-existing, CRC-valid pTake blob found in the
    current HMI,
  * updates primary/backup directory checksums.

All other page blobs and resources remain byte-for-byte unchanged.
"""
from __future__ import annotations

import importlib.util
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "build_figma_fix_hmi.py"
CANONICAL = ROOT / "project" / "RoastSense_NX4827T043_011_COMPILE_READY.HMI"
SPLASH_SOURCE = ROOT / "project" / "_old_valid.HMI"


def load_generator():
    spec = importlib.util.spec_from_file_location("hmi_builder", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load HMI helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_valid_page_blob(raw: bytes, helper, name: bytes):
    hits = []
    pos = 0
    while True:
        pos = raw.find(name, pos)
        if pos < 0:
            break
        start = pos - 24
        if start >= 0 and start + 16 <= len(raw):
            size = struct.unpack_from("<I", raw, start + 4)[0]
            if 0 < size < 100_000 and start + size <= len(raw):
                blob = raw[start:start + size]
                stored = struct.unpack_from("<I", blob, 0)[0]
                if stored == helper.page_crc(blob):
                    hits.append((start, size, blob))
        pos += 1
    if not hits:
        raise RuntimeError(f"no CRC-valid page blob found for {name!r}")
    # Prefer the latest valid Editor-written copy.
    return hits[-1]


def set_entry(raw: bytearray, helper, filename: str, start: int, size: int):
    _, off, _, _, _, _, tails = helper.find_entry(bytes(raw), filename)
    packed = struct.pack(
        helper.ENTRY_FMT,
        filename.encode().ljust(16, b"\0"),
        start,
        size,
        0,
        tails[0],
        tails[1],
        tails[2],
    )
    raw[off:off + helper.ENTRY_SIZE] = packed
    boff = helper.BACKUP_DIR_OFFSET + off
    raw[boff:boff + helper.ENTRY_SIZE] = packed


def refresh_directory_checksums(raw: bytearray, helper):
    count = struct.unpack_from("<I", raw, 0)[0]
    dir_end = 4 + count * helper.ENTRY_SIZE
    checksum = helper.directory_checksum(bytes(raw[:dir_end]))
    struct.pack_into("<I", raw, dir_end, checksum)
    struct.pack_into("<I", raw, helper.BACKUP_DIR_OFFSET + dir_end, checksum)


def main():
    helper = load_generator()
    raw = bytearray(CANONICAL.read_bytes())

    # Recover pTake from the current, manually edited HMI itself.
    take_start, take_size, take_blob = find_valid_page_blob(bytes(raw), helper, b"pTake")
    assert take_blob[24:40].split(b"\0", 1)[0] == b"pTake"

    # pSplash source is the previously validated root-only page; visuals come
    # from resource 0.i/0.is already patched in CANONICAL.
    splash_raw = SPLASH_SOURCE.read_bytes()
    splash_blob = helper.get_page(splash_raw, 0)
    assert splash_blob[24:40].split(b"\0", 1)[0] == b"pSplash"
    assert struct.unpack_from("<I", splash_blob, 0)[0] == helper.page_crc(splash_blob)

    splash_start = len(raw)
    raw.extend(splash_blob)

    set_entry(raw, helper, "0.pa", splash_start, len(splash_blob))
    set_entry(raw, helper, "2.pa", take_start, take_size)
    refresh_directory_checksums(raw, helper)

    # Strict page-level validation after pointer repair.
    for page_id in range(12):
        page = helper.get_page(bytes(raw), page_id)
        stored = struct.unpack_from("<I", page, 0)[0]
        calculated = helper.page_crc(page)
        if stored != calculated:
            raise AssertionError(
                f"page {page_id} CRC mismatch: stored=0x{stored:08x} "
                f"calculated=0x{calculated:08x}"
            )
        name = page[24:40].split(b"\0", 1)[0].decode("ascii", "replace")
        print(page_id, name, len(page), "CRC_OK")

    CANONICAL.write_bytes(raw)
    print("repaired", CANONICAL)
    print("pTake source", take_start, take_size)
    print("pSplash appended", splash_start, len(splash_blob))


if __name__ == "__main__":
    main()
