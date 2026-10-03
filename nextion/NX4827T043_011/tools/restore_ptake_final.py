#!/usr/bin/env python3
"""Restore only pTake from the known-good final-layout HMI.

All other pages/resources in the canonical Editor-managed HMI are preserved
byte-for-byte. The replacement pTake is the 15-component final-layout page
containing separate roast/origin previous+next controls, batch -/+, status,
and final Figma geometry.
"""
from pathlib import Path
import importlib.util
import hashlib
import struct

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "build_figma_fix_hmi.py"
CANONICAL = ROOT / "project" / "RoastSense_NX4827T043_011_COMPILE_READY.HMI"
SOURCE = ROOT / "project" / "RoastSense_UI_FIX_QA.HMI"


def load_helper():
    spec = importlib.util.spec_from_file_location("hmi_builder", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load HMI helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_final_ptake(raw: bytes, helper):
    candidates = []
    pos = 0
    while True:
        pos = raw.find(b"pTake", pos)
        if pos < 0:
            break
        start = pos - 24
        if start >= 0:
            size = struct.unpack_from("<I", raw, start + 4)[0]
            count = struct.unpack_from("<I", raw, start + 12)[0]
            if 0 < size < 100_000 and start + size <= len(raw):
                blob = raw[start:start + size]
                if (
                    struct.unpack_from("<I", blob, 0)[0] == helper.page_crc(blob)
                    and count == 15
                ):
                    names = {
                        helper.component_name(rec)
                        for *_, rec in helper.component_records(blob)
                    }
                    required = {
                        "pTake", "tRoast", "tOrigin", "tBatch", "tCycles",
                        "tFile", "tStat", "mRoast", "mRNext", "mOrigin",
                        "mOrgNxt", "mBatch", "mBInc0", "mBack", "mStart",
                    }
                    if required <= names:
                        candidates.append((start, size, blob))
        pos += 1
    if not candidates:
        raise RuntimeError("15-component final pTake not found")
    return candidates[-1]


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


def refresh_checksum(raw: bytearray, helper):
    count = struct.unpack_from("<I", raw, 0)[0]
    dir_end = 4 + count * helper.ENTRY_SIZE
    checksum = helper.directory_checksum(bytes(raw[:dir_end]))
    struct.pack_into("<I", raw, dir_end, checksum)
    struct.pack_into("<I", raw, helper.BACKUP_DIR_OFFSET + dir_end, checksum)


def main():
    helper = load_helper()
    canonical = bytearray(CANONICAL.read_bytes())
    source = SOURCE.read_bytes()

    # Snapshot every non-pTake page before the repair.
    before = {
        pid: hashlib.sha256(helper.get_page(bytes(canonical), pid)).hexdigest()
        for pid in range(12)
        if pid != 2
    }

    _, _, ptake = find_final_ptake(source, helper)
    new_start = len(canonical)
    canonical.extend(ptake)
    set_entry(canonical, helper, "2.pa", new_start, len(ptake))
    refresh_checksum(canonical, helper)

    # Verify all non-pTake pages are byte-for-byte unchanged.
    for pid, digest in before.items():
        current = hashlib.sha256(helper.get_page(bytes(canonical), pid)).hexdigest()
        if current != digest:
            raise AssertionError(f"page {pid} changed unexpectedly")

    page = helper.get_page(bytes(canonical), 2)
    names = [helper.component_name(rec) for *_, rec in helper.component_records(page)]
    if len(names) != 15:
        raise AssertionError(f"pTake component count is {len(names)}, expected 15")

    CANONICAL.write_bytes(canonical)
    print("RESTORED pTake only")
    print("components:", names)
    print("pTake sha256:", hashlib.sha256(page).hexdigest())
    print("all pages except pTake unchanged")


if __name__ == "__main__":
    main()
