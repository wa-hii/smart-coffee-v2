"""
Background listener untuk akuisisi E-NOSE yang dimulai langsung dari Nextion.

Alur:
    Nextion START
      -> ATmega2560 startAcquisition()
      -> JSON USB Serial COM5
      -> service ini
      -> data/raw/<sample>_<batch>.csv

Service ini PASSIVE:
  - tidak pernah mengirim #start;
  - hanya merekam mode "labeled_data";
  - AI test tidak disimpan sebagai labeled dataset;
  - reconnect otomatis jika COM5 terputus.

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

from serial import Serial, SerialException


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
INCOMING_DIR = RAW_DIR / ".incoming"
INCOMPLETE_DIR = RAW_DIR / "incomplete"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "acquisition_service.log"
STATUS_FILE = LOG_DIR / "acquisition_service.status.json"
LOCK_FILE = LOG_DIR / "acquisition_service.lock"

DEFAULT_PORT = "COM5"
DEFAULT_BAUD = 115200

ADC_COLS = [
    "adc_tgs822",
    "adc_mq135",
    "adc_mq3",
    "adc_tgs2611",
    "adc_tgs2620",
    "adc_tgs2600",
    "adc_tgs2602",
    "adc_mq8",
    "adc_tgs813",
    "adc_tgs816",
]

CSV_COLUMNS = [
    "timestamp",
    "sample_id",
    "roast_level",
    "origin",
    "batch_id",
    "run_id",
    "phase",
    "sample_idx",
] + ADC_COLS + ["temperature", "humidity"]

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
    return RAW_DIR / f"{Path(filename).stem}_{stamp}.csv"


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

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        INCOMING_DIR.mkdir(parents=True, exist_ok=True)
        INCOMPLETE_DIR.mkdir(parents=True, exist_ok=True)

        self.final_path = unique_final_path(self.filename)
        self.partial_path = (
            INCOMING_DIR / f"{self.final_path.stem}.partial.csv"
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

    def write_sensor(self, data: dict) -> None:
        phase = str(data.get("phase", ""))
        if phase not in {"purging", "collecting"}:
            return

        row = {
            "timestamp": data.get("timestamp"),
            "sample_id": self.sample_id,
            "roast_level": self.roast_level,
            "origin": self.origin,
            "batch_id": self.batch_id,
            "run_id": data.get("cycle"),
            "phase": phase,
            "sample_idx": data.get("sample_idx"),
            "temperature": data.get(
                "temperature_c",
                data.get("temperature", data.get("temp")),
            ),
            "humidity": data.get(
                "humidity_rh",
                data.get("humidity"),
            ),
        }
        for col in ADC_COLS:
            row[col] = data.get(col)

        self.writer.writerow(row)
        self.file.flush()
        os.fsync(self.file.fileno())
        self.rows += 1

    def complete(self) -> Path:
        if not self.file.closed:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
        os.replace(self.partial_path, self.final_path)
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
        stamp = time.strftime("%Y%m%d_%H%M%S")
        dest = INCOMPLETE_DIR / (
            f"{self.final_path.stem}_{stamp}_INCOMPLETE.csv"
        )
        shutil.move(str(self.partial_path), str(dest))
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
    ):
        self.port = port
        self.baud = baud
        self.reconnect_s = reconnect_s
        self.logger = logger
        self.stop_requested = False
        self.session: AcquisitionSession | None = None

    def request_stop(self, *_args) -> None:
        self.stop_requested = True

    def open_serial(self) -> Serial:
        ser = Serial()
        ser.port = self.port
        ser.baudrate = self.baud
        ser.timeout = 1
        # Hindari reset ATmega yang tidak perlu saat listener membuka port.
        ser.dtr = False
        ser.rts = False
        ser.open()
        return ser

    def handle_event(self, data: dict) -> None:
        event = str(data.get("event", ""))

        if event == "ACQ_START":
            if data.get("mode") != "labeled_data":
                self.logger.info(
                    "Mengabaikan ACQ_START mode=%s (bukan labeled_data)",
                    data.get("mode"),
                )
                return
            if self.session is not None:
                self.session.preserve_incomplete("new ACQ_START received")
                self.session = None
            try:
                self.session = AcquisitionSession(data, self.logger)
            except Exception:
                self.logger.exception("Gagal membuat acquisition session")
                self.session = None
            return

        if event == "ACQ_COMPLETE":
            if self.session is None:
                return
            final_path = self.session.complete()
            batch_id = self.session.batch_id
            self.session = None
            self.validate_if_b32(final_path, batch_id)
            return

        if event == "ACQ_STOP":
            if self.session is not None:
                self.session.preserve_incomplete("ACQ_STOP")
                self.session = None
            return

        if self.session is not None:
            self.session.write_sensor(data)

    def validate_if_b32(self, path: Path, batch_id: str) -> None:
        if batch_id != "B32":
            return
        try:
            from validate_b32_acquisition import validate_file

            errors = validate_file(path)
            if errors:
                self.logger.error(
                    "B32 validation FAIL %s: %s",
                    path.name,
                    "; ".join(errors),
                )
            else:
                self.logger.info("B32 validation PASS %s", path.name)
        except Exception:
            self.logger.exception(
                "B32 validator gagal dijalankan untuk %s",
                path,
            )

    def run(self) -> None:
        write_status(
            state="starting",
            port=self.port,
            baud=self.baud,
            pid=os.getpid(),
        )

        while not self.stop_requested:
            ser: Serial | None = None
            try:
                self.logger.info(
                    "Membuka %s @ %d untuk passive LCD acquisition",
                    self.port,
                    self.baud,
                )
                ser = self.open_serial()
                self.logger.info("CONNECTED %s", self.port)
                write_status(
                    state="connected",
                    port=self.port,
                    baud=self.baud,
                    pid=os.getpid(),
                )

                while not self.stop_requested:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("{"):
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        self.logger.debug("Invalid JSON: %s", line[:200])
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
                    port=self.port,
                    baud=self.baud,
                    pid=os.getpid(),
                )
                if self.session is not None:
                    self.session.preserve_incomplete("serial disconnected")
                    self.session = None
            except Exception:
                self.logger.exception("Unexpected service error")
                if self.session is not None:
                    self.session.preserve_incomplete("service error")
                    self.session = None
            finally:
                if ser is not None and ser.is_open:
                    ser.close()

            if not self.stop_requested:
                time.sleep(self.reconnect_s)

        if self.session is not None:
            self.session.preserve_incomplete("service stopped")
            self.session = None
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
