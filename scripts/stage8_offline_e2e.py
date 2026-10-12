"""Tahap 8: E2E CONTRACT mock from REAL historical ATmega CSV, never hardware.

Nextion mock -> firmware-shaped frames -> Stage7 bridge -> Stage6 release gate
-> mocked pResult N/A. No dummy dataset, fitted model, serial port, Nextion
command, pump/valve, or source CSV writes. A COMPLETE_QA bridge session is
only a software protocol result; physical E2E and AI remain NO-GO.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable

from acquisition_schema import ADC_COLS, CSV_COLUMNS, sensor_row_from_payload
from stage6_release_gate import evaluate as release_gate
from stage7_bridge import LegacySessionBridge

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = (ROOT / "data/raw").resolve()
FAULTS = (
    "none", "gap", "duplicate", "invalid_json",
    "stale_timestamp", "disconnect", "missing_complete",
    "missing_adc", "unapproved_inference", "premature_complete",
)
MODES = ("ai_test", "labeled_data")


def read_real_csv(path: Path) -> tuple[list[dict], str]:
    """Read-only. Do not silently repair missing/partial sensor data."""
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with path.open(newline="", encoding="utf-8-sig") as reader:
        records = csv.DictReader(reader)
        if records.fieldnames is None or not set(CSV_COLUMNS).issubset(records.fieldnames):
            raise ValueError("real_csv_schema_incomplete")
        rows = list(records)
    if not rows or len(rows) > 20000:
        raise ValueError("real_csv_size_invalid")
    if not any(row["sample_idx"] for row in rows):
        raise ValueError("real_csv_no_sensor_frames")
    return rows, digest


def _event(event: str, **data) -> str:
    return json.dumps({"event": event, **data}, separators=(",", ":"))


def _firmware_samples(rows: Iterable[dict]) -> Iterable[tuple[int, str, str]]:
    """Make firmware-like stream from actual CSV sensor measurements.

    Sample labels are intentionally stripped before parsing in AI_TEST.
    A collector must not infer a roast class from filename/metadata.
    """
    previous = (1, "purging")
    for row in rows:
        if not row["sample_idx"]:
            continue  # CSV event-only marker, not a real sensor frame
        cycle = int(row["run_id"])
        phase = row["phase"]
        if (cycle, phase) != previous:
            yield (-1, "transition", _event(
                "PHASE_CHANGE", cycle=cycle, phase=phase,
            ))
            previous = (cycle, phase)
        sample = {
            "timestamp": int(row["timestamp"]),
            "cycle": cycle,
            "phase": phase,
            "sample_idx": int(row["sample_idx"]),
        }
        sample.update({col: int(row[col]) for col in ADC_COLS})
        # SHT30 readings are retained when numeric; not mandatory for ADC QA.
        for csv_key, wire_key in (
            ("temperature", "temperature_c"), ("humidity", "humidity_rh")
        ):
            if row.get(csv_key):
                sample[wire_key] = float(row[csv_key])
        yield (sample["sample_idx"], "sensor", json.dumps(sample))


def mock_session(rows: list[dict], *, mode: str, fault: str) -> dict:
    if mode not in MODES or fault not in FAULTS:
        raise ValueError("invalid_mode_or_fault")
    bridge = LegacySessionBridge(session_factory=lambda: "stage8realcsv001")
    # Only an abstract Nextion gesture, NOT hardware Nextion events.
    start = {
        "event": "ACQ_START", "mode": mode, "cycle": 1,
        "phase": "purging", "cycles_total": 5, "purge_s": 25, "collect_s": 5,
    }
    if mode == "labeled_data":
        # Only labeled acquisition can include operator metadata. This
        # metadata is unverified provenance, never an AI_TEST input.
        start.update({
            "sample_id": rows[0]["sample_id"],
            "roast_level": rows[0]["roast_level"],
            "origin_code": rows[0]["origin"],
        })
    bridge.feed(json.dumps(start))
    samples = 0
    injected = False
    autosave_rows_in_memory = 0
    physical_rows = [row for row in rows if row["sample_idx"]]
    for sample_index, kind, raw in _firmware_samples(rows):
        if kind == "sensor":
            samples += 1
            if mode == "labeled_data" and fault == "none":
                # Real acquisition payload -> canonical CSV projection.
                # Compare directly with the original sensor rows, but NEVER
                # write a reconstructed CSV into data/raw.
                sample = json.loads(raw)
                stored = sensor_row_from_payload(
                    sample,
                    sample_id=rows[0]["sample_id"],
                    roast_level=rows[0]["roast_level"],
                    origin=rows[0]["origin"],
                    batch_id=rows[0]["batch_id"],
                )
                original = physical_rows[autosave_rows_in_memory]
                for name in ("timestamp", "run_id", "sample_idx", *ADC_COLS):
                    if int(stored[name]) != int(original[name]):
                        raise ValueError("labeled_autosave_projection_mismatch")
                for name in ("sample_id", "roast_level", "origin", "batch_id", "phase"):
                    if str(stored[name]) != str(original[name]):
                        raise ValueError("labeled_autosave_metadata_mismatch")
                autosave_rows_in_memory += 1
            if fault == "gap" and not injected and sample_index == 3:
                injected = True
                continue
            if fault == "duplicate" and not injected and sample_index == 3:
                bridge.feed(raw)
                injected = True
            if fault == "invalid_json" and not injected and sample_index == 3:
                raw = "{invalid json"
                injected = True
            if fault == "missing_adc" and not injected and sample_index == 3:
                obj = json.loads(raw)
                del obj["adc_mq3"]
                raw = json.dumps(obj)
                injected = True
            if fault == "unapproved_inference" and not injected and sample_index == 3:
                # A rogue roast value must not bypass Stage6/Stage7.
                raw = _event("INFERENCE", result="light")
                injected = True
            if fault == "premature_complete" and not injected and sample_index == 3:
                raw = _event("ACQ_COMPLETE", cycles=5, total_samples=2)
                injected = True
            if fault == "stale_timestamp" and not injected and sample_index == 3:
                obj = json.loads(raw)
                obj["timestamp"] = 1
                raw = json.dumps(obj)
                injected = True
            if fault == "disconnect" and not injected and sample_index == 3:
                injected = True
                break
        if bridge.active is not None:
            bridge.feed(raw)
    if fault == "disconnect" and bridge.active is not None:
        bridge.abort("stream_disconnected")
    elif fault == "missing_complete" and bridge.active is not None:
        bridge.abort("stream_eof_or_disconnect")
    elif bridge.active is not None:
        bridge.feed(_event(
            "ACQ_COMPLETE", cycles=5,
            total_samples=sum(bridge.active["counts"].values()),
        ))
    final = bridge.last_final
    if final is None:
        raise RuntimeError("simulation_terminal_missing")
    return {
        "mode": mode, "injected_fault": fault,
        "real_sensor_frames_considered": samples,
        "terminal_event_count": sum(
            entry["type"] == "SESSION_FINAL" for entry in bridge.events
        ),
        "terminal": final,
        "label_supplied_to_ai_model": False,
        "input_roast_used_to_infer_prediction": False,
        "nextion_start": "MOCK_ONLY_NOT_PHYSICAL_EVENT",
        "nextion_presult_mock": {
            "component": "pResult", "text": "N/A",
            "actual_hmi_updated": False,
            "serial_frame_sent_to_mcu": False,
        },
        "autosave_simulated_only_no_file_written": mode == "labeled_data",
        "autosave_rows_verified_in_memory": autosave_rows_in_memory,
        "commands_to_atmega": 0,
        "actuator_operations": 0,
        "model_invocations": 0,
    }


def evaluate(path: Path) -> dict:
    gate = release_gate()
    if gate["model_promotion_allowed"] is not False or gate["runtime_ai_test_result"] != "N/A":
        raise ValueError("unsafe_stage6_model_gate")
    rows, digest = read_real_csv(path)
    cases = [
        mock_session(rows, mode="ai_test", fault=fault)
        for fault in FAULTS
    ] + [mock_session(rows, mode="labeled_data", fault="none")]
    for case in cases:
        final = case["terminal"]
        assert case["terminal_event_count"] == 1
        assert case["commands_to_atmega"] == 0
        assert case["actuator_operations"] == 0
        assert case["model_invocations"] == 0
        assert case["nextion_presult_mock"]["actual_hmi_updated"] is False
        if case["injected_fault"] == "none":
            if final["quality"] != "COMPLETE_QA":
                raise ValueError("real_csv_protocol_did_not_complete")
        else:
            if final["quality"] != "FAIL_CLOSED":
                raise ValueError("negative_test_should_be_fail_closed")
    ai_case = cases[0]
    assert ai_case["terminal"]["status"] == "N/A"
    return {
        "status": "STAGE8_OFFLINE_CONTRACT_PASS_HARDWARE_NOT_TESTED",
        "source": {
            "name": path.name,
            "sha256": digest,
            "real_historical_sensor_csv": True,
            "original_file_not_modified": True,
            "source_roast_origin_are_NOT_approved_ground_truth": True,
        },
        "scope": {
            "mcu_live_serial_opened": False,
            "nextion_actually_controlled": False,
            "actuator_actually_activated": False,
            "ai_model_loaded": False,
            "pi_to_mcu_protocol_implemented": False,
        },
        "stage6": {
            "status": gate["status"],
            "model_promotion_allowed": gate["model_promotion_allowed"],
            "ai_result": gate["runtime_ai_test_result"],
        },
        "cases": cases,
        "blockers": [
            "G0 custom PCB USB-VBUS/backfeed verification",
            "G2 authorized real USB UART read on Pi",
            "G3 authorized supervised physical Nextion acquisition",
            "Two-way Pi→ATmega→Nextion protocol not deployed",
            "Coffee-presence and unknown validation on prospective local data",
        ],
        "device_e2e_release": "NO_GO",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dest = args.output.resolve()
    if dest == args.input.resolve() or dest == RAW_ROOT or RAW_ROOT in dest.parents:
        raise ValueError("would_modify_original_raw")
    if args.output.exists():
        raise FileExistsError("evidence_output_exists")
    result = evaluate(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(result["status"])
    for case in result["cases"]:
        print(case["mode"], case["injected_fault"],
              case["terminal"]["quality"], case["terminal"]["status"],
              case["terminal"]["sensor_samples"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
