#!/usr/bin/env python3
"""Reject corrupt/out-of-application RF30 candidate HEX before MCU restore."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from prepare_rf30_pi_restore_image import validate_pi_rf30_ihex


def record(kind: int, addr: int, data: bytes) -> str:
    content = bytes([len(data), addr >> 8, addr & 0xff, kind]) + data
    return ":" + (content + bytes([(-sum(content)) & 0xff])).hex().upper()


def reject(source: str, file: Path) -> None:
    file.write_text(source, encoding="ascii")
    try:
        validate_pi_rf30_ihex(file)
    except ValueError:
        return
    raise AssertionError("INVALID_RF30_IMAGE_WAS_ACCEPTED")


def main() -> None:
    source = Path(__file__).resolve().parents[1] / (
        ".pio/build/rf30_return_bench/firmware.hex")
    result = validate_pi_rf30_ihex(source)
    assert result["flash_payload_bytes"] == 35748
    assert result["highest_address"] == 35747
    with TemporaryDirectory() as directory:
        file = Path(directory) / "bad.hex"
        original = source.read_text(encoding="ascii")
        lines = original.splitlines()
        reject("\n".join(lines[:-1]) + "\n", file)  # no EOF
        reject("\n".join([lines[0], lines[0], *lines[1:]]) + "\n", file)
        bad_first = lines[0][:-2] + (
            "00" if lines[0][-2:] != "00" else "01")
        reject("\n".join([bad_first, *lines[1:]]) + "\n", file)
        reject("\n".join([
            record(4, 0, b"\x00\x03"),
            record(0, 0xe000, b"\x22"),
            record(1, 0, b""),
        ]) + "\n", file)  # address 0x3E000 is bootloader
    print("PI_RF30_APPLICATION_IMAGE_GUARDS_PASS",
          {"bytes": result["flash_payload_bytes"],
           "bootloader_region_written": False})


if __name__ == "__main__":
    main()
