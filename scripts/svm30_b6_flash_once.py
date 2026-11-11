#!/usr/bin/env python3
"""ONE explicitly approved ATmega2560 standalone SVM30 firmware flash.

Never modifies EEPROM or Nextion TFT; it writes the existing pinned
application HEX via verified COM5/Wiring bootloader (and avrdude -D).
No blind retry/rollback. Evidence is stored only in gitignored private/.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from svm30_b6_readonly_backup import preflight as validate_com
from svm30_b6_verify_readback import verify, parse_intel_hex

APP_LIMIT=253952
EXPECTED_IMAGE_SHA="6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2"
EXPECTED_MODEL_SHA="d71e74a037860b0c7d7da241c448dcda65a2b736c343577a62307baed3cb1e33"
APPROVAL="I_APPROVE_COM5_SVM30_FLASH_WITH_VERIFICATION"
BACKUP=ROOT/"private/b6_com5_readback/20261111_170948"
CANDIDATE=ROOT/"private/svm30_standalone_firmware.hex"
MANIFEST=ROOT/"private/svm30_standalone_firmware_manifest.json"
DEPLOY_DIR=ROOT/"private/b6_com5_svm30_deployment"


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_ihex_app(path:Path)->dict:
    """Verify candidate record checksums/addresses; allow sparse app suffix."""
    addresses=set()
    high=0
    eof=False
    bytes_seen=0
    for line in path.read_text(encoding="ascii").splitlines():
        if eof or not line.startswith(":"):
            raise ValueError("HEX_INVALID_OR_DATA_AFTER_EOF")
        b=bytes.fromhex(line[1:])
        if len(b)<5 or b[0]!=len(b)-5 or sum(b)%256:
            raise ValueError("HEX_INVALID_SIZE_OR_CHECKSUM")
        n=b[0]
        addr=b[1]*256+b[2]
        kind=b[3]
        if kind==4:
            if n!=2 or addr:
                raise ValueError("INVALID_EXT_ADDRESS")
            high=int.from_bytes(b[4:-1],"big")
        elif kind==0:
            first=(high<<16)+addr
            if first+n>APP_LIMIT:
                raise ValueError("BOOTLOADER_ADDRESS_FORBIDDEN")
            for a in range(first,first+n):
                if a in addresses:
                    raise ValueError("DUPLICATE_HEX_ADDRESS")
                addresses.add(a)
            bytes_seen+=n
        elif kind==1:
            if n or addr:
                raise ValueError("INVALID_EOF")
            eof=True
        else:
            raise ValueError("UNSUPPORTED_HEX_RECORD")
    if not eof or bytes_seen<40000 or min(addresses)!=0:
        raise ValueError("CANDIDATE_MISSING_OR_INCOMPLETE")
    return {"flash_payload_bytes":bytes_seen,
            "highest_address":max(addresses),"app_limit":APP_LIMIT}


def flash(approval:str, timeout_s:int=180)->int:
    if approval!=APPROVAL:
        raise PermissionError("SPECIFIC_COM5_FLASH_PERMISSION_REQUIRED")
    if not 45<=timeout_s<=240:
        raise ValueError("UNSAFE_TIMEOUT")
    hw=validate_com() # checks identity and receiver stopped, never opens COM
    original=verify(BACKUP)
    if original["device_signature"]!="0x1e9801":
        raise ValueError("BACKUP_WRONG_DEVICE")
    if original["files"]["eeprom_readback.hex"]["address_coverage_bytes"]!=4096:
        raise ValueError("EEPROM_BACKUP_INCOMPLETE")
    rollback=BACKUP/"legacy_app_only_rollback.hex"
    rollback_meta=BACKUP/"legacy_app_only_rollback_manifest.json"
    if not rollback.is_file() or not rollback_meta.is_file():
        raise ValueError("RECOVERY_IMAGE_NOT_PREPARED")
    rb=json.loads(rollback_meta.read_text(encoding="utf8"))
    if sha(rollback)!=rb.get("rollback_hex_sha256") or rb.get("application_region_size_bytes")!=APP_LIMIT:
        raise ValueError("ROLLBACK_HASH_INVALID")
    parse_intel_hex(rollback,APP_LIMIT)
    model=json.loads(MANIFEST.read_text(encoding="utf8"))
    if (model.get("profile")!="svm30_standalone" or
            model.get("status")!="COMPILE_ONLY_NOT_FLASHED" or
            model.get("model_sha256")!=EXPECTED_MODEL_SHA or
            model.get("firmware_flashed") is not False or
            model.get("firmware_hex_sha256")!=EXPECTED_IMAGE_SHA or
            sha(CANDIDATE)!=EXPECTED_IMAGE_SHA):
        raise ValueError("USER_SVM30_CANDIDATE_IDENTITY_FAILED")
    image=validate_ihex_app(CANDIDATE)
    if DEPLOY_DIR.exists():
        raise FileExistsError("EXISTING_DEPLOYMENT_EVIDENCE_NO_RETRY")
    DEPLOY_DIR.mkdir(parents=True)
    release_copy=DEPLOY_DIR/"svm30_candidate.hex"
    shutil.copy2(CANDIDATE,release_copy)
    if sha(release_copy)!=EXPECTED_IMAGE_SHA:
        raise RuntimeError("CANDIDATE_COPIED_WITH_HASH_MISMATCH")
    exe=Path(hw["avrdude_path"])
    conf=Path(hw["avrdude_config"])
    # -D disables automatic CHIP erase; Wiring bootloader performs page
    # programming for application section only.  Do NOT pass -V, which would
    # disable automatic verification.  Do not write EEPROM or bootloader.
    argv=[str(exe),"-C",str(conf),"-p","m2560","-c","wiring",
          "-P","COM5","-b","115200","-D",
          "-U","flash:w:svm30_candidate.hex:i"]
    assert not any(arg=="-e" or arg=="-V" or "eeprom:" in arg
                   or "fuse" in arg or "lock" in arg for arg in argv)
    event={
      "started_utc":datetime.now(timezone.utc).isoformat(),
      "status":"STARTED_RESULT_UNKNOWN",
      "operator_permission":"EXPLICIT_CHAT_APPROVAL_FOR_FLASH",
      "target":"COM5",
      "ftdi_serial":"A10KMM3SA",
      "avr_chip":"ATmega2560",
      "wiring_bootloader_readback_previously_passed":True,
      "image_sha256":EXPECTED_IMAGE_SHA,
      "model_sha256":EXPECTED_MODEL_SHA,
      "application_region":image,
      "rollback_sha256":sha(rollback),
      "eeprom_preserve_intended":True,
      "eeprom_written_by_command":False,
      "bootloader_region_written_by_command":False,
      "binary_from_existing_compile_only_build":True,
      "attempts":1,
      "command_args_excluding_executable":argv[1:],
    }
    (DEPLOY_DIR/"deployment_manifest.json").write_text(
        json.dumps(event,indent=2)+"\n",encoding="utf8")
    began=time.monotonic()
    try:
        result=subprocess.run(argv,capture_output=True,text=True,
                              cwd=DEPLOY_DIR,timeout=timeout_s,
                              errors="replace")
        log="STDOUT\n"+result.stdout+"\nSTDERR\n"+result.stderr
        event["avrdude_exit_code"]=result.returncode
    except subprocess.TimeoutExpired as exc:
        log="AVRDUDE_TIMEOUT\n"+str(exc)
        event["avrdude_exit_code"]="TIMEOUT"
    event["duration_seconds"]=round(time.monotonic()-began,2)
    (DEPLOY_DIR/"avrdude_flash_once.log").write_text(log,encoding="utf8")
    low=log.lower()
    event["device_signature_confirmed"]="device signature = 0x1e9801" in low
    event["flash_verify_confirmed"]=("bytes of flash verified" in low or
                                       "flash verified" in low)
    event["success"]=bool(event["avrdude_exit_code"]==0 and
                           event["device_signature_confirmed"] and
                           event["flash_verify_confirmed"])
    event["status"]="FLASH_WRITE_AND_AVRDUDE_VERIFY_PASS" if event["success"] else "UPLOAD_FAILED_OR_UNVERIFIED_NO_AUTO_RETRY"
    event["finished_utc"]=datetime.now(timezone.utc).isoformat()
    (DEPLOY_DIR/"deployment_manifest.json").write_text(
        json.dumps(event,indent=2)+"\n",encoding="utf8")
    print("B6_STANDALONE_UPLOAD_RESULT",json.dumps({
        "status":event["status"],
        "exit_code":event["avrdude_exit_code"],
        "device_signature_confirmed":event["device_signature_confirmed"],
        "flash_verify_confirmed":event["flash_verify_confirmed"],
        "duration_seconds":event["duration_seconds"],
        "target":"COM5",
        "eeprom_written_by_command":False,
        "bootloader_written_by_command":False,
        "evidence_dir":str(DEPLOY_DIR),
    }),flush=True)
    print("AVRDUDE_LOG_TAIL",log.encode("ascii","backslashreplace").decode()[-2400:],flush=True)
    return 0 if event["success"] else 3


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve",required=True)
    parser.add_argument("--timeout",type=int,default=180)
    args=parser.parse_args()
    raise SystemExit(flash(args.approve,args.timeout))
