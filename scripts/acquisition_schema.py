"""Canonical acquisition schema shared by serial collectors and validators.

This module intentionally contains no serial I/O.  Its job is to define what
counts as a real sensor sample so event messages such as PHASE_CHANGE can never
be mistaken for CSV sensor rows.
"""

from __future__ import annotations

from typing import Any


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

VALID_PHASES = {"purging", "collecting"}

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

# Environment readings are deliberately NOT required.  SHT30 can fail for one
# sample while all ten gas channels remain valid, and that gas sample should be
# preserved.  The required keys below identify a genuine firmware sensor frame.
SENSOR_REQUIRED_KEYS = [
    "timestamp",
    "cycle",
    "sample_idx",
] + ADC_COLS


def is_sensor_payload(data: Any) -> bool:
    """Return True only for a complete gas-sensor sample payload.

    Event frames are explicitly rejected even if they carry a valid phase.
    This is the key guard that prevents PHASE_CHANGE from becoming an empty
    CSV row.
    """
    if not isinstance(data, dict):
        return False
    if data.get("event"):
        return False
    if str(data.get("phase", "")).strip().lower() not in VALID_PHASES:
        return False
    return all(data.get(key) is not None for key in SENSOR_REQUIRED_KEYS)


def sensor_payload_rejection_reason(data: Any) -> str:
    """Human-readable reason for diagnostics when a payload is rejected."""
    if not isinstance(data, dict):
        return "payload is not a JSON object"
    event = str(data.get("event", "")).strip()
    if event:
        return f"event frame: {event}"
    phase = str(data.get("phase", "")).strip().lower()
    if phase not in VALID_PHASES:
        return f"invalid phase: {phase!r}"
    missing = [key for key in SENSOR_REQUIRED_KEYS if data.get(key) is None]
    if missing:
        return "missing required sensor keys: " + ", ".join(missing)
    return "unknown sensor payload mismatch"


def environment_values(data: dict) -> tuple[Any, Any]:
    """Read current canonical keys while keeping backward compatibility."""
    temperature = data.get(
        "temperature_c",
        data.get("temperature", data.get("temp")),
    )
    humidity = data.get(
        "humidity_rh",
        data.get("humidity"),
    )
    return temperature, humidity


def sensor_row_from_payload(
    data: dict,
    *,
    sample_id: str,
    roast_level: str,
    origin: str,
    batch_id: str,
) -> dict:
    """Convert one verified firmware sensor payload into canonical CSV form."""
    if not is_sensor_payload(data):
        raise ValueError(sensor_payload_rejection_reason(data))

    temperature, humidity = environment_values(data)
    row = {
        "timestamp": data["timestamp"],
        "sample_id": sample_id,
        "roast_level": roast_level,
        "origin": origin,
        "batch_id": batch_id,
        "run_id": data["cycle"],
        "phase": str(data["phase"]).strip().lower(),
        "sample_idx": data["sample_idx"],
        "temperature": temperature,
        "humidity": humidity,
    }
    for column in ADC_COLS:
        row[column] = data[column]
    return row
