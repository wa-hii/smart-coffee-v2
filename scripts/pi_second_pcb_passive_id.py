#!/usr/bin/env python3
"""Diagnosis read-only identitas firmware PCB kedua melalui FT232R Pi 5.

Satu-satunya identitas USB yang diizinkan: FT232R A10KNJBL -> ttyUSB0.
Port tidak pernah ditulisi. DTR dan RTS disetel False SEBELUM open(),
tetapi glitch pada open() oleh driver/hardware tidak dapat dikesampingkan.
Simpan seluruh byte mentah dan ringkasan di direktori privat, bukan Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import time

from serial import Serial

SERIAL_ID = "A10KNJBL"
PORT_LINK = Path(
    "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0")
EXPECTED_DEVICE = Path("/dev/ttyUSB0")
BAUD = 115200  # src/main.cpp:268 — Serial.begin(115200)
DANGEROUS = (b"undervoltage", b"under-voltage", b"brownout", b"overheat")
RESET_MARKERS = (b"fw_hello", b"watchdog reset", b"wdt reset", b"booting")


def kernel_usb_events() -> list[str]:
    """Membaca log kernel, tanpa memodifikasi layanan Pi."""
    p = subprocess.run(
        ["journalctl", "-k", "-b", "--no-pager", "-n", "200"],
        capture_output=True, text=True, errors="replace", timeout=8,
        check=False)
    if p.returncode:
        return []
    return [line for line in p.stdout.splitlines()
            if ("USB disconnect" in line or "usb 3-1:" in line
                or "ttyUSB0" in line) and "usb " in line.lower()]


def claimed_firmware(raw: bytes) -> dict:
    """Mengekstrak penanda yang DIKLAIM firmware, bukan bukti readback Flash."""
    evidence = {"fw_hello_seen": False, "build_ids_claimed": [],
                "startup_messages": []}
    for segment in raw.splitlines():
        if len(segment) > 2048:
            continue
        try:
            item = json.loads(segment.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(item, dict):
            continue
        if item.get("event") == "FW_HELLO":
            evidence["fw_hello_seen"] = True
            if isinstance(item.get("build_id"), str):
                evidence["build_ids_claimed"].append(item["build_id"][:120])
        if any(k in item for k in ("event", "warn", "error", "i2c_scan_done")):
            evidence["startup_messages"].append(
                {key: str(item.get(key))[:150] for key in
                 ("event", "warn", "error", "i2c_scan_done") if key in item})
        if len(evidence["startup_messages"]) >= 20:
            break
    evidence["build_ids_claimed"] = list(
        dict.fromkeys(evidence["build_ids_claimed"]))
    return evidence


def run(out_dir: Path, seconds: int = 45) -> dict:
    if not 10 <= seconds <= 60:
        raise ValueError("DURASI_HANYA_10_SAMPAI_60_DETIK")
    if not PORT_LINK.is_symlink() or PORT_LINK.resolve() != EXPECTED_DEVICE:
        raise RuntimeError("FT232R_A10KNJBL_TIDAK_ADA_ATAU_BERUBAH")
    out_dir.mkdir(parents=True, exist_ok=False)
    raw_path = out_dir / "serial_pasif_mentah.bin"
    summary_path = out_dir / "ringkasan.json"
    before = kernel_usb_events()
    start = time.monotonic()
    read_chunks: list[bytes] = []
    status = "BELUM_DIJALANKAN"
    error = None
    serial = Serial()
    serial.port = str(PORT_LINK)
    serial.baudrate = BAUD
    serial.timeout = 0.5
    serial.write_timeout = 0
    # Penting: tidak menggunakan Serial(port=...) yang langsung membuka.
    serial.dtr = False
    serial.rts = False
    serial.xonxoff = False
    serial.rtscts = False
    serial.dsrdtr = False
    try:
        serial.open()
        status = "SELESAI"
        while time.monotonic() - start < seconds:
            if not PORT_LINK.is_symlink() or PORT_LINK.resolve() != EXPECTED_DEVICE:
                status = "HENTI_USB_TERPUTUS"
                break
            data = serial.read(128)
            if data:
                read_chunks.append(data)
                aggregate = b"".join(read_chunks).lower()
                if any(marker in aggregate for marker in DANGEROUS):
                    status = "HENTI_PESAN_BAHAYA"
                    break
                if sum(aggregate.count(m) for m in RESET_MARKERS) >= 4:
                    status = "HENTI_INDIKASI_RESET_BERULANG"
                    break
                if sum(map(len, read_chunks)) > 256000:
                    status = "HENTI_BATAS_LOG"
                    break
    except Exception as exc:
        error = type(exc).__name__ + ": " + str(exc)[:160]
        status = "HENTI_ERROR_SERIAL"
    finally:
        if serial.is_open:
            serial.close()
    raw = b"".join(read_chunks)
    # File .bin berisi byte identik tanpa perubahan/transformasi.
    raw_path.write_bytes(raw)
    after = kernel_usb_events()
    # Hanya laporkan baris disconnect yang belum muncul pada snapshot awal.
    newly_seen = [line for line in after if line not in before]
    if any("disconnect" in line.lower() for line in newly_seen):
        status = "HENTI_USB_DISCONNECT_BERULANG"
    summary = {
        "waktu_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "target": "FT232R onboard PCB kedua Pi5",
        "serial_usb": SERIAL_ID,
        "baud": BAUD,
        "durasi_target_s": seconds,
        "durasi_aktual_s": round(time.monotonic() - start, 1),
        "rx_bytes": len(raw),
        "raw_log_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_log_filename": raw_path.name,
        "uart_tx_bytes": 0,
        "dtr_pre_open": False,
        "rts_pre_open": False,
        "glitch_dtr_open_tidak_dapat_disingkirkan": True,
        "usb_event_baru_count": len(newly_seen),
        "usb_disconnect_baru": any(
            "disconnect" in line.lower() for line in newly_seen),
        "pesan_error": error,
        "firmware": claimed_firmware(raw),
        "mcu_flash_verified": False,
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print("PI_SECOND_PCB_PASSIVE_ID " +
          json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=45)
    opts = parser.parse_args()
    result = run(opts.out_dir, opts.seconds)
    raise SystemExit(0 if result["status"] == "SELESAI" else 2)
