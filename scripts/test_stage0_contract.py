"""Pemeriksaan statis lintas modul untuk baseline Tahap 0 (tanpa akses serial).

Tes ini memeriksa konstanta dan pemetaan yang harus konsisten; tidak mengganti
pengujian firmware, hardware, dataset, atau HMI melalui Nextion Editor.
"""

from __future__ import annotations

import ast
from pathlib import Path
import re

from acquisition_schema import ADC_COLS, CSV_COLUMNS


ROOT = Path(__file__).resolve().parents[1]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def require(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"PASS {label}")


def macro_value(text: str, name: str) -> int:
    result = re.search(
        rf"^#define\s+{re.escape(name)}\s+(\d+)(?:UL?|\s|$)",
        text, re.MULTILINE
    )
    if result is None:
        raise AssertionError(f"Makro tidak ditemukan: {name}")
    return int(result.group(1))


def literal_assignment(file: str, name: str) -> dict:
    tree = ast.parse(source(file))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} tidak ditemukan pada {file}")


def main() -> None:
    main_cpp = source("src/main.cpp")
    sensor_h = source("src/sensor.h")
    sensor_cpp = source("src/sensor.cpp")
    nextion = source("nextion/NX4827T043_011/README_NEXTION_EDITOR.md")

    require(
        (
            macro_value(main_cpp, "ACQ_PURGE_SECONDS"),
            macro_value(main_cpp, "ACQ_COLLECTION_SECONDS"),
            macro_value(main_cpp, "ACQ_REPETITIONS"),
            macro_value(main_cpp, "TASK_INTERVAL_MS_ADS"),
        ) == (25, 5, 5, 1000),
        "kontrak 5 siklus × (25 detik purging + 5 detik collecting), sampling 1 s",
    )
    require(
        "Serial.begin(115200)" in main_cpp
        and "NextionTransport nextion(Serial2)" in main_cpp
        and macro_value(main_cpp, "NEXTION_BAUD") == 9600,
        "Serial USB 115200 dan Nextion Serial2 9600",
    )

    indices = [
        (int(num), f"adc_{name.lower()}")
        for name, num in re.findall(
            r"^#define\s+SENSOR_([A-Z0-9]+)\s+(\d+)\s*$",
            sensor_h, re.MULTILINE,
        )
    ]
    require(
        [field for _, field in sorted(indices)] == ADC_COLS
        and len(indices) == 10,
        "urutan kanal sensor.h konsisten dengan skema CSV",
    )
    print_json = sensor_cpp.split("void SensorArray::printJsonData(", 1)[1]
    emitted = re.findall(r'adc_[a-z0-9]+', print_json.split("#if USE_PPM", 1)[0])
    require(emitted == ADC_COLS, "urutan payload JSON konsisten dengan skema CSV")
    require(
        CSV_COLUMNS[-2:] == ["temperature", "humidity"],
        "kolom hasil CSV memiliki suhu dan kelembapan",
    )
    require(
        "Serial.print(F(\",\\\"temperature_c\\\":\"))" in sensor_cpp
        and "Serial.print(F(\",\\\"humidity_rh\\\":\"))" in sensor_cpp,
        "payload SHT30 memakai kunci temperature_c dan humidity_rh",
    )

    addresses = {
        int(num): int(addr, 16)
        for num, addr in re.findall(
            r"^#define\s+I2C_ADDR_ADS(\d+)\s+(0x[0-9A-Fa-f]+)",
            sensor_h, re.MULTILINE,
        )
    }
    require(
        addresses == {1: 0x48, 2: 0x49, 3: 0x4A, 4: 0x4B},
        "alamat ADS1115 0x48–0x4B",
    )
    require(
        "PH0/RXD2 TQFP pin 12" in main_cpp
        and "PH1/TXD2 TQFP pin 13" in main_cpp
        and "TQFP-100 **12**" in nextion
        and "TQFP-100 **13**" in nextion,
        "pin kemasan TQFP Nextion konsisten dengan datasheet Microchip",
    )
    require(
        (ROOT / "nextion/NX4827T043_011/project/"
         "RoastSense_NX4827T043_011_COMPILE_READY.HMI").is_file(),
        "HMI acuan ditemukan",
    )

    # Perbandingan metadata tanpa impor serial, tanpa membuka COM5.
    manual = literal_assignment("scripts/3_collect_data.py", "KNOWN_SAMPLES")
    listener = literal_assignment("scripts/lcd_acquisition_service.py", "ORIGIN_BY_SAMPLE")
    mismatches = {
        key: (manual[key]["origin"], listener[key])
        for key in sorted(manual.keys() & listener.keys())
        if manual[key]["origin"] != listener[key]
    }
    require(not mismatches, f"pemetaan metadata yang sama antarkolektor: {mismatches}")
    print(f"INFO metadata preset: manual={len(manual)}, listener={len(listener)}")
    print(f"INFO hanya kolektor manual: {sorted(manual.keys() - listener.keys())}")
    print(f"INFO hanya listener LCD: {sorted(listener.keys() - manual.keys())}")
    print("INFO D-TEM, D-MUK, TEM/MUK dan CAW tetap perlu tinjauan semantik bersama operator")
    print("INFO UART Serial1 ke Raspberry Pi masih rancangan; bukan tes hardware")
    print("STAGE0_STATIC_CONTRACT_PASS")


if __name__ == "__main__":
    main()
