#!/usr/bin/env python3
"""Offline QA for the locked Figma -> Nextion -> ATmega contract.

This test intentionally does not need a physical LCD. It validates that the
canonical HMI contains the locked Figma pixels, the expected model/page/event
structure, and that every HMI EVT:* message is handled by the production
ATmega firmware.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
import struct
from pathlib import Path

from PIL import Image


SCRIPT = Path(__file__).resolve()
DISPLAY_ROOT = SCRIPT.parents[1]
REPO_ROOT = SCRIPT.parents[3]
GENERATOR = DISPLAY_ROOT / "tools" / "build_figma_fix_hmi.py"
HMI = DISPLAY_ROOT / "project" / "RoastSense_NX4827T043_011_FIXED.HMI"
ASSETS = DISPLAY_ROOT / "backgrounds_clean_png"
MOCKUPS = DISPLAY_ROOT / "mockups_png"
MAIN_CPP = REPO_ROOT / "src" / "main.cpp"

NAMES = [
    "00_Splash",
    "01_Home",
    "02_TakeData",
    "03_DataRun",
    "04_DataDone",
    "05_StartTest",
    "06_TestRun",
    "07_TestResult",
    "08_Calibration",
    "09_Settings",
    "10_History",
    "11_Alert",
]

# SHA-256 prefixes from the locked Figma page fix, exported at 1x on
# 2026-10-03. These make accidental fallback to an older mockup fail loudly.
FIGMA_SHA256_PREFIX = {
    "00_Splash": "943c7e59a9f48abc",
    "01_Home": "959efaad1342993e",
    "02_TakeData": "a6311a4c93e444f6",
    "03_DataRun": "925875797c74504c",
    "04_DataDone": "9c68140e26ae3212",
    "05_StartTest": "8b49a4cd60c47b9e",
    "06_TestRun": "496e8570b6edbd36",
    "07_TestResult": "7f3bbf43daf0bf45",
    "08_Calibration": "9f0c3a652924f006",
    "09_Settings": "e67198882bf27412",
    "10_History": "1c34a77a6cde31f0",
    "11_Alert": "0b9fb3623121b519",
}


def load_generator():
    spec = importlib.util.spec_from_file_location("hmi_builder", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load HMI generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_rgb565(image: Image.Image, rgb565) -> bytes:
    pixels = bytearray()
    for red, green, blue in image.convert("RGB").getdata():
        pixels += struct.pack("<H", rgb565((red, green, blue)))
    return bytes(pixels)


def main() -> int:
    generator = load_generator()
    raw = HMI.read_bytes()
    qa = generator.verify(raw)

    for picture_id, name in enumerate(NAMES):
        png_path = ASSETS / f"{name}.png"
        mockup_path = MOCKUPS / f"{name}.png"
        image = Image.open(png_path)
        assert image.size == (480, 272), f"{png_path}: {image.size}"

        digest = hashlib.sha256(png_path.read_bytes()).hexdigest()
        assert digest.startswith(FIGMA_SHA256_PREFIX[name]), (
            f"{name}: not the locked Figma export ({digest})"
        )
        assert hashlib.sha256(mockup_path.read_bytes()).digest() == hashlib.sha256(
            png_path.read_bytes()
        ).digest(), f"{name}: mockup/background mismatch"

        _, _, _, start, size, _, _ = generator.find_entry(raw, f"{picture_id}.i")
        encoded = raw[start + 24 : start + size]
        assert encoded == expected_rgb565(image, generator.rgb565), (
            f"{name}: HMI RGB565 resource differs from locked Figma frame"
        )

    hmi_events = {
        item.decode("ascii") for item in re.findall(rb"EVT:[A-Z_]+", raw)
    }
    source = MAIN_CPP.read_text(encoding="utf-8")
    firmware_events = set(re.findall(r"EVT:[A-Z_]+", source))
    missing_handlers = sorted(hmi_events - firmware_events)
    assert not missing_handlers, f"HMI events without ATmega handler: {missing_handlers}"

    assert "NextionTransport nextion(Serial2);" in source
    assert "#define NEXTION_BAUD 9600UL" in source
    assert "NextionTransport nextion(Serial1);" not in source

    print("PASS: locked Figma assets =", len(NAMES))
    print("PASS: HMI model =", qa["model_crc"])
    print("PASS: HMI pages =", len(qa["pages"]))
    print("PASS: HMI events =", len(hmi_events))
    print("PASS: all HMI events are represented in ATmega handler")
    print("PASS: production link = Serial2 @ 9600 baud")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
