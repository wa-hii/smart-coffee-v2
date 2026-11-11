#!/usr/bin/env python3
"""Prepare an APP-ONLY legacy firmware recovery HEX from B6 COM5 readback.

No serial access or hardware commands. Preserve complete original readback.
Atmega2560 PlatformIO reports max application region: 253952 bytes,
with bootloader above that boundary. NEVER write bootloader region
through a standard serial application rollback.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from svm30_b6_verify_readback import verify, parse_intel_hex

APP_LIMIT=253952
SOURCE=ROOT/"private/b6_com5_readback/20261111_170948"
OUT=SOURCE/"legacy_app_only_rollback.hex"
MANIFEST=SOURCE/"legacy_app_only_rollback_manifest.json"


def build() -> None:
    if OUT.exists() or MANIFEST.exists():
        raise FileExistsError("rollback_already_exists_no_overwrite")
    evidence=verify(SOURCE)
    if evidence["device_signature"]!="0x1e9801":
        raise ValueError("wrong_mcu_signature")
    src=SOURCE/"flash_readback.hex"
    high=0
    segment=0
    kept=[]
    for line in src.read_text(encoding="ascii").splitlines():
        b=bytes.fromhex(line[1:])
        count=b[0]
        addr=(b[1]<<8)|b[2]
        typ=b[3]
        if typ==4:
            high=int.from_bytes(b[4:-1],"big")
            segment=0
            kept.append(line)
        elif typ==2:
            segment=int.from_bytes(b[4:-1],"big")
            high=0
            kept.append(line)
        elif typ==0:
            absolute=(high<<16)+(segment<<4)+addr
            if absolute>=APP_LIMIT:
                continue
            if absolute+count>APP_LIMIT:
                raise ValueError("image_crosses_application_bootloader_boundary")
            kept.append(line)
        elif typ==1:
            kept.append(line)
        else:
            raise ValueError("unsupported_hex_record")
    if not kept or kept[-1]!=":00000001FF":
        raise ValueError("missing_end_of_file")
    OUT.write_text("\n".join(kept)+"\n",encoding="ascii",newline="")
    try:
        proof=parse_intel_hex(OUT,APP_LIMIT)
        if proof["address_coverage_bytes"]!=APP_LIMIT:
            raise ValueError("application_rollback_incomplete")
    except Exception:
        OUT.unlink(missing_ok=True)
        raise
    result={
        "created_utc":datetime.now(timezone.utc).isoformat(),
        "status":"OFFLINE_PREPARED_NOT_TESTED_ON_DEVICE",
        "source_readback_sha256":evidence["files"]["flash_readback.hex"]["file_sha256"],
        "application_region_size_bytes":APP_LIMIT,
        "preserves_bootloader_area":True,
        "original_readback_unchanged":True,
        "eeprom_restore_not_attempted":True,
        "rollback_hex_sha256":hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "rollback_hex_bytes":OUT.stat().st_size,
        "restorability_not_proven":True,
    }
    MANIFEST.write_text(json.dumps(result,indent=2)+"\n",encoding="utf8")
    print("B6_LEGACY_APP_ROLLBACK_PREPARED",json.dumps(result),flush=True)


if __name__=="__main__":
    build()
