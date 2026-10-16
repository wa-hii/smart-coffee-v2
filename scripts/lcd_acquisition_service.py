"""
Background listener untuk akuisisi E-NOSE yang dimulai langsung dari Nextion.

Alur:
    Nextion START
      -> ATmega2560 startAcquisition()
      -> JSON USB Serial COM (otomatis atau eksplisit)
      -> service ini
      -> data/raw/<sample>_<batch>.csv

Service ini PASSIVE:
  - tidak pernah mengirim #start;
  - hanya merekam mode "labeled_data";
  - AI test tidak disimpan sebagai labeled dataset;
  - pindai COM otomatis saat startup / USB tersambung / port berubah.

File ditulis lebih dulu sebagai .partial.csv. Saat ACQ_COMPLETE diterima,
file dipindahkan atomik menjadi CSV final. Run terputus dipertahankan di
data/raw/incomplete/.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import time
import uuid

from serial import Serial, SerialException

from acquisition_schema import (
    CSV_COLUMNS,
    is_sensor_payload,
    sensor_payload_rejection_reason,
    sensor_row_from_payload,
)
from baseline_recording import BaselineRecording
from baseline_quality import publish_quality
from serial_wire import serial_json_frames
from usb_autodetect import discover_port

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
INCOMING_DIR = RAW_DIR / ".incoming"
INCOMPLETE_DIR = RAW_DIR / "incomplete"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "acquisition_service.log"
STATUS_FILE = LOG_DIR / "acquisition_service.status.json"
LOCK_FILE = LOG_DIR / "acquisition_service.lock"
BASELINE_DIR = ROOT / "data" / "baseline"

DEFAULT_PORT = "auto"
DEFAULT_BAUD = 115200

# Samakan metadata origin dengan dataset yang sudah dipakai 3_collect_data.py.
ORIGIN_BY_SAMPLE = {
    "L-MAN": "Arabika Manglayang Jawa Barat",
    "L-RAT": "Arabika Ratawali Aceh",
    "L-GAY": "Arabika Gayo Aceh",
    "L-MER": "Arabika Merapi",
    "L-TEM": "Arabika Temanggung",
    "L-CAT": "Arabika Catuji Mekarwangi",
    "L-GAW": "Arabika Gayo Wine",
    "L-MING": "Arabika Sumatra Utara",
    "L-TOR": "Arabika Toraja Washed",
    "L-GRB": "Arabika Redbourbon Gayo Aceh Natural",
    "M-MAN": "Arabika Manglayang Jawa Barat",
    "M-RAT": "Arabika Ratawali Aceh",
    "M-TEM": "Arabika Temanggung",
    "M-TIM": "Arabika Timor Leste",
    "M-CAT": "Arabika Catuji Mekarwangi",
    "M-GAW": "Arabika Gayo Wine",
    "M-MING": "Arabika Sumatra Utara",
    "M-TOR": "Arabika Toraja Washed",
    "M-GRB": "Arabika Redbourbon Gayo Aceh Natural",
    "D-MAN": "Arabika Manglayang Jawa Barat",
    "D-RAT": "Arabika Ratawali Aceh",
    "D-GAY": "Arabika Gayo Aceh",
    "D-BAR": "Arabika Jawa Barat",
    "D-TEM": "Arabika Temanggung Mukidi",
    "D-CAT": "Arabika Catuji Mekarwangi",
    "D-GAW": "Arabika Gayo Wine",
    "D-MUK": "Arabika Temanggung Mukidi Roasting Sendiri",
    "D-MING": "Arabika Sumatra Utara",
    "D-TOR": "Arabika Toraja Washed",
    "D-GRB": "Arabika Redbourbon Gayo Aceh Natural",
}

ORIGIN_BY_CODE = {
    "MING": "Arabika Sumatra Utara",
    "MAN": "Arabika Manglayang Jawa Barat",
    "RAT": "Arabika Ratawali Aceh",
    "GAY": "Arabika Gayo Aceh",
    "MER": "Arabika Merapi",
    "TEM": "Arabika Temanggung",
    "CAT": "Arabika Catuji Mekarwangi",
    "GAW": "Arabika Gayo Wine",
    "TIM": "Arabika Timor Leste",
    "BAR": "Arabika Jawa Barat",
    "MUK": "Arabika Temanggung Mukidi",
    "CAW": "CAW",
    "GRB": "Arabika Redbourbon Gayo Aceh Natural",
    "TOR": "Arabika Toraja Washed",
}

SAFE_FILENAME_RE = re.compile(r"^[LMD]-[A-Z0-9]+_B[0-9]+\.csv$")


def configure_logging(verbose: bool = False) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("enose-acquisition")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(file_handler)

    if sys.stdout is not None:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
        logger.addHandler(console)

    return logger


def write_status(**values) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **values,
    }
    tmp = STATUS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, STATUS_FILE)


def acquire_process_lock():
    """Prevent dua background listener membuka COM5 bersamaan."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_FILE, "a+b")
    handle.seek(0)
    handle.write(b"0")
    handle.flush()

    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise RuntimeError(
                "lcd_acquisition_service sudah berjalan"
            ) from exc
    return handle


def sanitize_filename(event: dict) -> str:
    filename = str(event.get("filename", "")).strip().upper()
    if SAFE_FILENAME_RE.fullmatch(filename):
        return filename

    sample_id = str(event.get("sample_id", "")).strip().upper()
    batch_id = str(event.get("batch_id", "")).strip().upper()
    fallback = f"{sample_id}_{batch_id}.csv"
    if not SAFE_FILENAME_RE.fullmatch(fallback):
        raise ValueError(
            f"metadata filename tidak valid: filename={filename!r}, "
            f"sample_id={sample_id!r}, batch_id={batch_id!r}"
        )
    return fallback


def unique_final_path(filename: str) -> Path:
    path = RAW_DIR / filename
    if not path.exists():
        return path
    stamp = time.strftime("%Y%m%d_%H%M%S")
    for number in range(1, 10000):
        suffix = "" if number == 1 else f"_{number}"
        candidate = RAW_DIR / f"{Path(filename).stem}_{stamp}{suffix}.csv"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Too many filename collisions for acquisition")


class AcquisitionSession:
    def __init__(self, event: dict, logger: logging.Logger):
        self.logger = logger
        self.sample_id = str(event.get("sample_id", "")).strip().upper()
        self.roast_level = str(event.get("roast_level", "")).strip().lower()
        self.origin_code = str(event.get("origin_code", "")).strip().upper()
        self.batch_id = str(event.get("batch_id", "")).strip().upper()
        self.filename = sanitize_filename(event)
        self.origin = ORIGIN_BY_SAMPLE.get(
            self.sample_id,
            ORIGIN_BY_CODE.get(self.origin_code, self.origin_code),
        )
        self.rows = 0

        if self.roast_level not in {"light", "medium", "dark"}:
            raise ValueError(f"roast_level tidak valid: {self.roast_level!r}")
        if not self.sample_id or not self.batch_id:
            raise ValueError("sample_id/batch_id kosong pada ACQ_START")
        expected_roast = {"L": "light", "M": "medium", "D": "dark"}.get(
            self.sample_id[:1]
        )
        if self.roast_level != expected_roast:
            raise ValueError("roast_level tidak cocok dengan prefix sample_id")
        if self.origin_code and self.sample_id.split("-", 1)[-1] != self.origin_code:
            raise ValueError("origin_code tidak cocok dengan sample_id")

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        INCOMING_DIR.mkdir(parents=True, exist_ok=True)
        INCOMPLETE_DIR.mkdir(parents=True, exist_ok=True)

        self.final_path = unique_final_path(self.filename)
        self.partial_path = (
            INCOMING_DIR / f"{self.final_path.stem}_{uuid.uuid4().hex}.partial.csv"
        )
        self.file = open(
            self.partial_path,
            "w",
            newline="",
            encoding="utf-8",
        )
        self.writer = csv.DictWriter(self.file, fieldnames=CSV_COLUMNS)
        self.writer.writeheader()
        self.file.flush()
        os.fsync(self.file.fileno())

        self.logger.info(
            "ACQ START sample=%s roast=%s origin=%s batch=%s target=%s",
            self.sample_id,
            self.roast_level,
            self.origin,
            self.batch_id,
            self.final_path.name,
        )

    def write_sensor(self, data: dict) -> bool:
        """Write only a genuine firmware sensor sample.

        PHASE_CHANGE and other event frames can carry phase/cycle metadata but
        do not carry ADC values.  They must never become CSV rows.
        """
        if not is_sensor_payload(data):
            self.logger.warning(
                "Sensor payload ditolak: %s",
                sensor_payload_rejection_reason(data),
            )
            return False

        row = sensor_row_from_payload(
            data,
            sample_id=self.sample_id,
            roast_level=self.roast_level,
            origin=self.origin,
            batch_id=self.batch_id,
        )

        self.writer.writerow(row)
        self.file.flush()
        os.fsync(self.file.fileno())
        self.rows += 1
        return True

    def complete(self) -> Path:
        if not self.file.closed:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
        # Atomic no-clobber publication on the same filesystem: create a new
        # hard link first, then remove the staging name. Unlike os.replace(),
        # os.link() fails when a concurrent writer already created the target.
        for _ in range(100):
            try:
                os.link(self.partial_path, self.final_path)
                break
            except FileExistsError:
                self.final_path = unique_final_path(self.filename)
        else:
            raise RuntimeError("Could not reserve a unique acquisition filename")
        self.partial_path.unlink()
        self.logger.info(
            "ACQ COMPLETE file=%s rows=%d",
            self.final_path,
            self.rows,
        )
        return self.final_path

    def preserve_incomplete(self, reason: str) -> Path | None:
        if not self.file.closed:
            self.file.flush()
            self.file.close()
        if not self.partial_path.exists():
            return None
        # Exclusive create: two incomplete runs within one second must never
        # overwrite each other. Hard-link publication is atomic, same FS.
        dest = INCOMPLETE_DIR / (
            f"{self.final_path.stem}_{uuid.uuid4().hex}_INCOMPLETE.csv"
        )
        os.link(self.partial_path, dest)
        self.partial_path.unlink()
        self.logger.warning(
            "ACQ INCOMPLETE reason=%s rows=%d file=%s",
            reason,
            self.rows,
            dest,
        )
        return dest


class AcquisitionService:
    def __init__(
        self,
        port: str,
        baud: int,
        reconnect_s: float,
        logger: logging.Logger,
        usb_serial: str | None = None,
    ):
        self.port = port
        self.usb_serial = usb_serial
        self.baud = baud
        self.reconnect_s = reconnect_s
        self.logger = logger
        self.stop_requested = False
        self.session: AcquisitionSession | None = None
        self.baseline: BaselineRecording | None = None
        self.last_frame_monotonic = time.monotonic()

    def request_stop(self, *_args) -> None:
        self.stop_requested = True

    def open_serial(self) -> Serial:
        if self.port == 'auto':
            raise RuntimeError('Select a USB device before opening serial')
        return self.open_selected_serial(self.port)

    def open_selected_serial(self, port: str) -> Serial:
        ser = Serial()
        ser.port = port
        ser.baudrate = self.baud
        ser.timeout = 1
        # Hindari reset ATmega yang tidak perlu saat listener membuka port.
        ser.dtr = False
        ser.rts = False
        ser.open()
        return ser

    def handle_event(self, data: dict) -> None:
        event = str(data.get("event", ""))

        if event == "BASELINE_START":
            if self.baseline is not None:
                self.baseline.preserve_incomplete("duplicate baseline start")
                self.baseline = None
            if self.session is not None:
                self.session.preserve_incomplete("unexpected baseline during coffee acquisition")
                self.session = None
                self.logger.error("Reject overlapping BASELINE_START")
                return
            try:
                self.baseline = BaselineRecording(BASELINE_DIR, data)
                self.last_frame_monotonic = time.monotonic()
                self.logger.info("BASELINE START target=%s", self.baseline.final.name)
            except Exception:
                self.logger.exception("Reject BASELINE_START")
            return

        if event == "BASELINE_SAMPLE":
            if self.baseline is None:
                self.logger.warning("BASELINE_SAMPLE without active baseline")
                return
            try:
                self.baseline.add(data)
                self.last_frame_monotonic = time.monotonic()
            except Exception:
                self.logger.exception("Invalid baseline frame, quarantining")
                self.baseline.preserve_incomplete("invalid baseline sample")
                self.baseline = None
            return

        if event == "BASELINE_COMPLETE":
            if self.baseline is None:
                self.logger.warning("BASELINE_COMPLETE without active session")
                return
            try:
                path = self.baseline.complete(data)
                self.logger.info("BASELINE COMPLETE file=%s rows=60", path)
                try:
                    qc_path = publish_quality(path, self.baseline.build_id)
                    self.logger.info("BASELINE QC report=%s", qc_path)
                except Exception:
                    self.logger.exception("Baseline saved but QC sidecar failed")
            except Exception:
                self.logger.exception("BASELINE_COMPLETE rejected")
                self.baseline.preserve_incomplete("baseline completion mismatch")
            finally:
                self.baseline = None
            return

        if event == "BASELINE_ABORT":
            if self.baseline is not None:
                self.baseline.preserve_incomplete("baseline aborted by operator")
                self.baseline = None
            return

        if event == "ACQ_START":
            if self.baseline is not None:
                self.baseline.preserve_incomplete("unexpected coffee start")
                self.baseline = None
                self.logger.error("Reject coffee start overlapping baseline")
                return
            if self.session is not None:
                self.session.preserve_incomplete("another ACQ_START received")
                self.session = None
            if data.get("mode") != "labeled_data":
                self.logger.info(
                    "Mengabaikan ACQ_START mode=%s (bukan labeled_data)",
                    data.get("mode"),
                )
                return
            if (data.get("cycles_total") != 30 or data.get("purge_s") != 25 or
                    data.get("collect_s") != 5 or data.get("cycle") != 1 or
                    data.get("phase") != "purging"):
                self.logger.error("Reject invalid ACQ_START timing/phase contract")
                return
            try:
                self.session = AcquisitionSession(data, self.logger)
                self.last_frame_monotonic = time.monotonic()
            except Exception:
                self.logger.exception("Gagal membuat acquisition session")
                self.session = None
            return

        if event == "ACQ_COMPLETE":
            if self.session is None:
                return
            if (data.get("cycles") != 30 or
                    type(data.get("total_samples")) is not int or
                    data["total_samples"] != self.session.rows):
                self.session.preserve_incomplete("ACQ_COMPLETE count mismatch")
                self.session = None
                return
            # Firmware completion does not itself prove five complete cycles.
            # Validate the staged CSV before publishing it as finished raw.
            from validate_acquisition import validate_file

            issues = validate_file(self.session.partial_path, expected_cycles=30)
            if issues:
                self.logger.error("Incomplete/invalid ACQ_COMPLETE: %s", "; ".join(issues))
                self.session.preserve_incomplete("ACQ_COMPLETE validation failed")
                self.session = None
                return
            final_path = self.session.complete()
            self.session = None
            self.validate_completed_file(final_path)
            return

        if event == "ACQ_STOP":
            if self.session is not None:
                self.session.preserve_incomplete("ACQ_STOP")
                self.session = None
            return

        if event == "TRANSPORT_ERROR":
            if self.baseline is not None:
                self.baseline.preserve_incomplete("serial transport error")
                self.baseline = None
            if self.session is not None:
                self.session.preserve_incomplete("serial frame corrupt or oversized")
                self.session = None
            return

        # Semua frame yang memiliki field event adalah control/status event,
        # bukan sample sensor.  Unknown event juga fail-closed agar event baru
        # di firmware tidak diam-diam masuk sebagai row CSV kosong.
        if event:
            self.logger.debug("Mengabaikan event frame: %s", event)
            return

        if self.session is not None:
            if not self.session.write_sensor(data):
                self.session.preserve_incomplete("invalid sensor payload")
                self.session = None
            else:
                self.last_frame_monotonic = time.monotonic()

    def validate_completed_file(self, path: Path) -> None:
        """Repeat the same strict 30-cycle validation after publication."""
        try:
            from validate_acquisition import file_summary, validate_file

            errors = validate_file(path, expected_cycles=30)
            if errors:
                self.logger.error(
                    "Acquisition validation FAIL %s: %s",
                    path.name,
                    "; ".join(errors),
                )
            else:
                summary = file_summary(path)
                self.logger.info(
                    "Acquisition validation PASS %s "
                    "sensor_rows=%d metadata_rows=%d partial_rows=%d",
                    path.name,
                    summary["sensor_rows"],
                    summary["metadata_rows"],
                    summary["partial_rows"],
                )
        except Exception:
            self.logger.exception(
                "Acquisition validator gagal dijalankan untuk %s",
                path,
            )

    def run(self) -> None:
        # Data directories are present even on a fresh laptop before the USB
        # device is connected. Never erase or overwrite prior recordings.
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        INCOMING_DIR.mkdir(parents=True, exist_ok=True)
        INCOMPLETE_DIR.mkdir(parents=True, exist_ok=True)
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        last_discovery = None
        write_status(
            state="starting",
            port=self.port,
            baud=self.baud,
            pid=os.getpid(),
        )

        while not self.stop_requested:
            ser: Serial | None = None
            selected_port = self.port
            if self.port == 'auto':
                found = discover_port(serial_number=self.usb_serial)
                if found.port is None:
                    state = (found.reason, found.candidates)
                    if state != last_discovery:
                        self.logger.info('USB waiting: %s; candidates=%s',
                                         found.reason, ', '.join(found.candidates))
                    last_discovery = state
                    write_status(state='waiting_for_device', port=None,
                                 baud=self.baud, pid=os.getpid(),
                                 reason=found.reason,
                                 candidates=list(found.candidates))
                    time.sleep(self.reconnect_s)
                    continue
                selected_port = found.port
                if last_discovery != ('connected_candidate', selected_port):
                    self.logger.info('USB detected -> %s (passive receive)', selected_port)
                last_discovery = ('connected_candidate', selected_port)
            try:
                self.logger.info(
                    "Membuka %s @ %d untuk passive LCD acquisition",
                    selected_port,
                    self.baud,
                )
                ser = (self.open_selected_serial(selected_port) if self.port == 'auto'
                       else self.open_serial())
                self.logger.info("CONNECTED %s", selected_port)
                write_status(
                    state="connected",
                    port=selected_port,
                    baud=self.baud,
                    pid=os.getpid(),
                )

                for data in serial_json_frames(ser):
                    if self.stop_requested:
                        break
                    if data is None:
                        if (self.session is not None and
                                time.monotonic() - self.last_frame_monotonic > 12):
                            self.session.preserve_incomplete("host receive timeout")
                            self.session = None
                        if (self.baseline is not None and
                                time.monotonic() - self.last_frame_monotonic > 12):
                            self.baseline.preserve_incomplete("baseline receive timeout")
                            self.baseline = None
                        continue
                    self.handle_event(data)

            except (SerialException, OSError):
                self.logger.warning(
                    "COM connection unavailable; retry %.1fs",
                    self.reconnect_s,
                    exc_info=True,
                )
                write_status(
                    state="waiting_for_port",
                    port=selected_port,
                    baud=self.baud,
                    pid=os.getpid(),
                )
                if self.session is not None:
                    self.session.preserve_incomplete("serial disconnected")
                    self.session = None
                if self.baseline is not None:
                    self.baseline.preserve_incomplete("serial disconnected")
                    self.baseline = None
            except Exception:
                self.logger.exception("Unexpected service error")
                if self.session is not None:
                    self.session.preserve_incomplete("service error")
                    self.session = None
                if self.baseline is not None:
                    self.baseline.preserve_incomplete("service error")
                    self.baseline = None
            finally:
                if ser is not None and ser.is_open:
                    ser.close()

            if not self.stop_requested:
                time.sleep(self.reconnect_s)

        if self.session is not None:
            self.session.preserve_incomplete("service stopped")
            self.session = None
        if self.baseline is not None:
            self.baseline.preserve_incomplete("service stopped")
            self.baseline = None
        write_status(
            state="stopped",
            port=self.port,
            baud=self.baud,
            pid=os.getpid(),
        )
        self.logger.info("Service stopped")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Passive autosave listener untuk akuisisi via Nextion"
    )
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument('--usb-serial', default=None,
                        help='Optional USB bridge serial number if multiple supported adapters are plugged in')
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--reconnect-s", type=float, default=2.0)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logging(args.verbose)
    try:
        lock_handle = acquire_process_lock()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2

    service = AcquisitionService(
        port=args.port,
        baud=args.baud,
        reconnect_s=args.reconnect_s,
        logger=logger,
        usb_serial=args.usb_serial,
    )
    signal.signal(signal.SIGINT, service.request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, service.request_stop)

    try:
        service.run()
    finally:
        lock_handle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
