#!/usr/bin/env python3
"""Permanent RF500 Pi 5 listener for successive Nextion AI Tests.

Single UART open across sessions: NO serial reconnect, DTR-reset or
service exit after a successful 30-cycle classification.
The ONLY UART TX after 900 validated samples is a session-bound
#rf30:<token>:<light|medium|dark>; reply. Never drives pump/valve or
uploads firmware. Sensor frames are archived only after MCU ACK.

Deploy in an isolated trusted venv with a SHA256 pinned RF500 model.
Run under a single-instance boot supervisor. This is an experimental
classifier, not proof of calibration or accuracy across roast/origin.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import inspect
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

import rf30_pi_result_bridge as bridge_module
from rf30_pi_result_bridge import (
    BoundedLineFramer, BUILD_ID, HostSession, ReturnProtocolError,
    USB_BY_ID, strict_json,
)
from roast_rf30_pi_inference import (
    EXPECTED_SKLEARN_VERSION, predict_capture, verify_artifact,
)
from pi_labeled_take_data import LabeledTakeRecorder, LabeledDataError

# Explicitly pinned FT232RL bridges for tested E-Nose boards. Windows appends
# interface suffix 'A' to these Linux FTDI IDs (e.g. COM3 A10KN6X9A).
# Never choose the first /dev/ttyUSB* blindly.
SERIAL_PORTS = {
    "A10KMZQJ": Path("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMZQJ-if00-port0"),
    "A10KMM3S": Path("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0"),
    "A10KN6X9": Path("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KN6X9-if00-port0"),
}
PORT = SERIAL_PORTS["A10KMZQJ"]  # Backward-compatible first-Pi default.
FTDI_SERIAL = "A10KMZQJ"
BAUD = 115200
MAX_IDLE_ACTIVE_S = 12
MAX_ARCHIVE_RECORDS = 1100
ALLOWED_FRAME_ERRORS = 8


def verify_bridge_compatibility() -> None:
    """Prevent old staged RF30 module silently rejecting every AI Test.

    Prior incident: listener in always_on imported an older bridge from
    rf30_staging root that lacked HostSession.feed(predictor=...), causing
    every frame to be discarded and the LCD to show N/A after 30 cycles.
    """
    expected_dir = Path(__file__).resolve().parent
    actual_module = Path(bridge_module.__file__).resolve()
    if actual_module.parent != expected_dir:
        raise RuntimeError("RF30_BRIDGE_NOT_SAME_RELEASE_DIRECTORY")
    if "predictor" not in inspect.signature(HostSession.feed).parameters:
        raise RuntimeError("RF30_BRIDGE_PREDICTOR_API_MISSING")
    if bridge_module.BUILD_ID != "take30-ai30-rfhost-20261110":
        raise RuntimeError("RF30_BRIDGE_BUILD_ID_INCOMPATIBLE")


def verify_host(port: Path, model: Path, metadata: Path) -> None:
    verify_bridge_compatibility()
    if (port not in SERIAL_PORTS.values()
            or not USB_BY_ID.fullmatch(port.as_posix())):
        raise RuntimeError("WRONG_USB_FTDI_TARGET_STOP")
    if (not port.is_symlink() or not port.exists()
            or not re.fullmatch(r"ttyUSB\d+", port.resolve().name)):
        raise RuntimeError("PINNED_USB_FTDI_NOT_CONNECTED")
    p = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                       text=True, timeout=5, check=False)
    if p.returncode or p.stdout.strip() != "throttled=0x0":
        raise RuntimeError("PI_POWER_THROTTLED_STOP")
    # SHA-pinned user-supplied model is deserialized only after validation.
    verify_artifact(model, metadata)
    import sklearn
    if sklearn.__version__ != EXPECTED_SKLEARN_VERSION:
        raise RuntimeError("SKLEARN_VERSION_NOT_PINNED")


def archive_complete_session(archive_dir: Path, capture: list[str],
                             token: str, roast: str) -> dict:
    """Atomic private log: raw complete firmware frames plus summary."""
    if not re.fullmatch(r"[0-9A-F]{8}", token) or roast not in ("light", "medium", "dark"):
        raise ValueError("INVALID_ARCHIVE_TOKEN_OR_ROAST")
    if not 902 <= len(capture) <= MAX_ARCHIVE_RECORDS:
        raise ValueError("ARCHIVE_CAPTURE_RECORD_COUNT_INVALID")
    archive_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = ("\n".join(capture) + "\n").encode("utf8")
    if len(data) > 1_000_000:
        raise ValueError("ARCHIVE_TOO_LARGE")
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ") + "_" + token
    capture_path = archive_dir / (tag + ".ndjson")
    info_path = archive_dir / (tag + ".json")
    from hashlib import sha256
    info = {
        "status": "MCU_ACK_CONFIRMED",
        "roast_predicted": roast,
        "ai_session_token": token,
        "samples": 900,
        "firmware_build_id": BUILD_ID,
        "model_kind": "RF500_30cycle",
        "origin_predicted": None,
        "model_accuracy_evaluated": False,
        "capture_sha256": sha256(data).hexdigest(),
        "capture_file": capture_path.name,
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
    }
    # File names are unique and unguessable by later sessions due to timestamp.
    # Exclusive opens protect against accidental replacements.
    with capture_path.open("xb") as fh:
        os.chmod(capture_path, 0o600)
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    with info_path.open("x", encoding="utf8") as fh:
        os.chmod(info_path, 0o600)
        json.dump(info, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    return info


class PersistentHandler:
    def __init__(self, *, predictor, archive_dir: Path,
                 take_data_dir: Path | None = None):
        self.predictor = predictor
        self.archive_dir = archive_dir
        self.labeled = LabeledTakeRecorder(
            take_data_dir if take_data_dir is not None
            else archive_dir.parent / "take_data")
        self.session = HostSession()
        self.quarantine = False
        self.seen_sessions = 0
        self.successful_sessions = 0
        self.bad_frames = 0
        self.last_sensor_time = time.monotonic()
        self.prestart_frames = 0
        self.prestart_non_json = 0
        self.prestart_sensor_frames = 0
        self.prestart_start_rejections = 0
        self.last_prestart_event = None

    def abandon(self, reason: str) -> dict:
        if self.session.token is not None:
            self.quarantine = True
            print("RF500_SESSION_DISCARDED", json.dumps({
                "reason": reason, "samples": self.session.samples,
                "no_result_sent": True,
            }), flush=True)
        else:
            # No session started; garbage is not grounds to reset the MCU.
            self.session = HostSession()
        return {"status": "SESSION_REJECTED_NO_RESULT", "reason": reason}

    def receive(self, raw: bytes) -> tuple[bytes | None, dict]:
        """Return optional vetted result command. Caller alone owns UART TX."""
        # Two disjoint protocols share ONE long-lived UART FD. Do not give
        # labeled training rows to the AI predict/inference path.
        if self.labeled.active:
            try:
                obj = strict_json(raw.decode("utf8"))
            except (ValueError, UnicodeError):
                obj = None
            if isinstance(obj, dict) and obj.get("event") == "ACQ_START":
                old = self.labeled.abort("new_acq_start_before_prior_complete")
                print("TAKE_DATA_INCOMPLETE", json.dumps(old), flush=True)
                if obj.get("mode") == "labeled_data":
                    try:
                        ready = self.labeled.start(obj)
                        print("TAKE_DATA_CAPTURE_STARTED", json.dumps(ready), flush=True)
                        return None, ready
                    except (LabeledDataError, OSError) as exc:
                        print("TAKE_DATA_START_REJECTED", str(exc)[:180], flush=True)
                        return None, {"status": "LABELED_START_REJECTED"}
                # AI mode may start only after the old labeled session is
                # quarantined; then use the existing strict AI gates below.
            else:
                status = self.labeled.receive(raw)
                if status["status"] == "LABELED_SAMPLE_ACCEPTED" and self.labeled.rows % 30 == 0:
                    print("TAKE_DATA_CYCLE_COMPLETE", self.labeled.rows // 30, "/30", flush=True)
                elif status["status"] == "LABELED_CSV_SAVED_900_VALID":
                    print("TAKE_DATA_CSV_SAVED_900_VALID", json.dumps(status), flush=True)
                elif status["status"] == "LABELED_INCOMPLETE_QUARANTINED":
                    print("TAKE_DATA_INCOMPLETE", json.dumps(status), flush=True)
                return None, status

        if self.session.token is None:
            try:
                probe = strict_json(raw.decode("utf8"))
            except (ValueError, UnicodeError):
                probe = None
            if (isinstance(probe, dict) and probe.get("event") == "ACQ_START"
                    and probe.get("mode") == "labeled_data"):
                try:
                    # Recover from previously failed AI session only on a new,
                    # validated explicit labeled start.
                    status = self.labeled.start(probe)
                    self.quarantine = False
                    self.session = HostSession()
                    print("TAKE_DATA_CAPTURE_STARTED", json.dumps(status), flush=True)
                    return None, status
                except (LabeledDataError, OSError) as exc:
                    print("TAKE_DATA_START_REJECTED", str(exc)[:180], flush=True)
                    return None, {"status": "LABELED_START_REJECTED"}
        # Diagnostic only: show WHY a real acquisition was not recognized.
        # Do not forward any unvalidated frames to the model or ATmega.
        if not self.quarantine and self.session.token is None:
            self.prestart_frames += 1
            try:
                start_probe = strict_json(raw.decode("utf8"))
                event = start_probe.get("event")
                if isinstance(event, str):
                    self.last_prestart_event = event[:48]
                if event == "ACQ_START":
                    print("RF500_ACQ_START_FRAME_RECEIVED", json.dumps({
                        "mode": start_probe.get("mode"),
                        "fw_build_id": start_probe.get("fw_build_id"),
                        "cycles_total": start_probe.get("cycles_total"),
                        "purge_s": start_probe.get("purge_s"),
                        "collect_s": start_probe.get("collect_s"),
                        "token_present": bool(start_probe.get("ai_session_token")),
                    }), flush=True)
                elif event in ("FW_HELLO", "ACQ_STOP", "ACQ_COMPLETE",
                               "AI_AWAITING_RESULT", "AI_RESULT_TIMEOUT",
                               "ACQ_TIMING_FAULT", "AI_RESULT_UNAVAILABLE"):
                    print("RF500_PRESTART_FIRMWARE_EVENT", event, flush=True)
                elif event is None and "phase" in start_probe and "sample_idx" in start_probe:
                    self.prestart_sensor_frames += 1
                    if self.prestart_sensor_frames <= 3 or self.prestart_sensor_frames % 100 == 0:
                        print("RF500_SENSOR_FRAME_WITHOUT_ACQ_START", json.dumps({
                            "count": self.prestart_sensor_frames,
                            "cycle": start_probe.get("cycle"),
                            "phase": start_probe.get("phase"),
                            "sample_idx": start_probe.get("sample_idx"),
                        }), flush=True)
            except (ValueError, UnicodeError, TypeError):
                self.prestart_non_json += 1
                if self.prestart_non_json <= 3 or self.prestart_non_json % 100 == 0:
                    print("RF500_PRESTART_NONJSON_FRAME", self.prestart_non_json, flush=True)
        if self.quarantine:
            # A new explicit, contract-valid ACQ_START is the sole way
            # to recover, without reopening serial/causing DTR reset.
            try:
                obj = strict_json(raw.decode("utf8"))
            except (ValueError, UnicodeError):
                return None, {"status": "QUARANTINE_OLD_SESSION"}
            if obj.get("event") != "ACQ_START":
                return None, {"status": "QUARANTINE_OLD_SESSION"}
            from rf30_pi_result_bridge import validate_start
            try:
                validate_start(obj)
            except ReturnProtocolError:
                return None, {"status": "QUARANTINE_REJECTED_START"}
            self.session = HostSession()
            self.quarantine = False

        # MCU reboot mid-collection invalidates the stream.
        if self.session.token is not None:
            try:
                obj = strict_json(raw.decode("utf8"))
                if obj.get("event") == "FW_HELLO":
                    return None, self.abandon("MCU_RESET_DURING_CAPTURE")
            except (ValueError, UnicodeError):
                pass
        try:
            command, status = self.session.feed(
                raw, allow_predict=True, predictor=self.predictor)
        except (ReturnProtocolError, KeyError, TypeError, ValueError) as exc:
            if self.session.token is None:
                self.prestart_start_rejections += 1
                print("RF500_PRESTART_FRAME_REJECTED", json.dumps({
                    "count": self.prestart_start_rejections,
                    "reason": type(exc).__name__ + ":" + str(exc)[:120],
                    "last_event": self.last_prestart_event,
                }), flush=True)
            return None, self.abandon(type(exc).__name__ + ":" + str(exc)[:120])
        state = status["status"]
        if state == "CAPTURE_STARTED":
            self.seen_sessions += 1
            self.last_sensor_time = time.monotonic()
            print("RF500_LIVE_CAPTURE_STARTED", self.seen_sessions, flush=True)
        elif state == "SAMPLE_ACCEPTED":
            self.last_sensor_time = time.monotonic()
            if self.session.samples % 30 == 0:
                print("RF500_CYCLE_COMPLETE", self.session.samples // 30, "/30", flush=True)
        elif state == "CAPTURE_COMPLETE":
            print("RF500_LIVE_CAPTURE_COMPLETE_900", flush=True)
        elif state == "RESULT_READY_FOR_SUPERVISED_TX":
            print("RF500_RESULT_READY_FOR_MCU_ACK", flush=True)
        elif state == "MCU_ACK_CONFIRMED":
            token = self.session.token
            roast = status["roast"]
            try:
                archived = archive_complete_session(
                    self.archive_dir, self.session.capture, token, roast)
                print("RF500_CAPTURE_ARCHIVED", archived["capture_file"], flush=True)
            except (OSError, ValueError) as exc:
                print("RF500_ARCHIVE_FAILED", str(exc)[:150], flush=True)
            self.successful_sessions += 1
            print("RF500_MCU_ACK_CONFIRMED", json.dumps({
                "roast": roast, "samples": 900,
                "success_count": self.successful_sessions,
                "serial_kept_open": True,
            }), flush=True)
            self.session = HostSession()
            self.last_sensor_time = time.monotonic()
        return command, status


def listen_forever(port: Path, model_path: Path, metadata_path: Path,
                   archive_dir: Path, take_data_dir: Path) -> None:
    verify_host(port, model_path, metadata_path)
    import joblib
    clf = joblib.load(model_path)
    def predict(csv_file: Path) -> dict:
        return predict_capture(csv_file, model_path, metadata_path, model=clf)

    import serial
    conn = serial.Serial(port=None, baudrate=BAUD, timeout=0.6,
                         rtscts=False, dsrdtr=False, exclusive=True)
    conn.dtr = False
    conn.rts = False
    handler = PersistentHandler(predictor=predict, archive_dir=archive_dir,
                                take_data_dir=take_data_dir)
    recovered = handler.labeled.recover_stale_partials()
    print("TAKE_DATA_RECOVERY_STARTUP", json.dumps({
        "previous_partial_files_quarantined": recovered,
        "take_data_csv_root": str(take_data_dir),
    }), flush=True)
    rx_bytes_total = 0
    rx_frames_total = 0
    last_any_rx = time.monotonic()
    last_heartbeat = time.monotonic()
    stop = False
    def request_stop(_sig, _frame):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        conn.port = str(port)
        conn.open()  # FT232R open may trigger ONE reset at startup.
        print("RF500_PERSISTENT_READY", json.dumps({
            "port": str(port), "baud": BAUD,
            "serial_open_once": True, "model_verified": True,
            "receiver_mode": "consecutive_30cycle_tests",
        }), flush=True)
        framer = BoundedLineFramer()
        while not stop:
            data = conn.read(512)
            now = time.monotonic()
            if data:
                rx_bytes_total += len(data)
                last_any_rx = now
            if now - last_heartbeat >= 45:
                print("RF500_TRANSPORT_HEARTBEAT", json.dumps({
                    "rx_bytes_total": rx_bytes_total,
                    "rx_frames_total": rx_frames_total,
                    "last_rx_age_s": round(now - last_any_rx, 1),
                    "active_capture": handler.session.token is not None,
                    "quarantine": handler.quarantine,
                    "prestart_frames": handler.prestart_frames,
                    "prestart_non_json": handler.prestart_non_json,
                    "prestart_sensor_frames": handler.prestart_sensor_frames,
                    "prestart_start_rejections": handler.prestart_start_rejections,
                    "last_prestart_event": handler.last_prestart_event,
                    "successful_sessions": handler.successful_sessions,
                    "take_data_active": handler.labeled.active,
                    "take_data_rows": handler.labeled.rows,
                }), flush=True)
                last_heartbeat = now
            if not data:
                stale = handler.labeled.check_timeout(now)
                if stale is not None:
                    print("TAKE_DATA_INCOMPLETE", json.dumps(stale), flush=True)
                if (handler.session.token and not handler.quarantine
                    and now-handler.last_sensor_time > MAX_IDLE_ACTIVE_S):
                    handler.abandon("UART_SENSOR_IDLE_TIMEOUT")
                continue
            try:
                lines = framer.feed(data)
            except ReturnProtocolError:
                handler.abandon("SERIAL_FRAMER_OVERFLOW")
                framer = BoundedLineFramer()
                continue
            for line in lines:
                rx_frames_total += 1
                command, status = handler.receive(line)
                if command is not None:
                    # No arbitrary command may be sent; only session-bound
                    # result packet generated AFTER verified 900 samples.
                    if not re.fullmatch(rb"#rf30:[0-9A-F]{8}:(?:light|medium|dark);", command):
                        handler.abandon("INVALID_OUTBOUND_COMMAND_BLOCKED")
                        continue
                    conn.write(command)
                    conn.flush()
                    print("RF500_RESULT_SENT_AWAIT_MCU_ACK", flush=True)
    finally:
        if handler.labeled.active:
            print("TAKE_DATA_INCOMPLETE", json.dumps(
                handler.labeled.abort("listener_process_stopping")), flush=True)
        if conn.is_open:
            conn.close()
        print("RF500_PERSISTENT_LISTENER_STOPPED", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial-live", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--take-data-dir", type=Path,
                        default=Path.home() / "smart-coffee-stage7/data/raw")
    args = parser.parse_args()
    try:
        listen_forever(args.serial_live, args.model, args.metadata,
                       args.archive_dir, args.take_data_dir)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print("RF500_PERSISTENT_START_OR_IO_FAILED", type(exc).__name__, str(exc)[:180],
              flush=True)
        return 3


if __name__ == "__main__":
    sys.exit(main())
