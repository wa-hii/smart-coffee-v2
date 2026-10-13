"""Stage 8: real-CSV-derived UART byte-stream → Pi parser → fail-closed AI N/A.

Entirely offline: no pyserial, USB/GPIO open, pump, Nextion, model or MCU write.
UART wire frames are reconstructed IN MEMORY from historical raw CSV data;
the bytes are synthetic and MUST NOT be presented as a physical capture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from acquisition_schema import ADC_COLS
from stage7_pi_adapter import receive_serial_chunks
from stage8_offline_e2e import _firmware_samples, read_real_csv
from stage6_release_gate import evaluate as stage6_evaluate

ROOT = Path(__file__).resolve().parents[1]
RAW = (ROOT / "data/raw").resolve()

SCENARIOS = (
    "normal_with_idle_boot", "clean_no_boot", "legacy_ai_test_label_leak",
    "wrong_start_timing", "no_acq_start", "duplicate_acq_start",
    "missing_complete",
    "disconnect_mid_sample", "missing_adc", "duplicate_sensor_idx",
    "stale_timestamp", "malformed_json_midstream",
    "invalid_phase_midstream", "wrong_complete_total",
    "unapproved_inference",
)


def _wire(event: str, **fields) -> bytes:
    return (json.dumps({"event": event, **fields},
                       separators=(",", ":")) + "\n").encode("utf-8")


def make_frames(rows: list[dict], scenario: str) -> list[bytes]:
    """Build a SIMULATED wire stream; originals never leave the input CSV."""
    if scenario not in SCENARIOS:
        raise ValueError("unknown_transport_scenario")
    start = {
        "mode": "ai_test", "phase": "purging", "cycle": 1,
        "cycles_total": 5, "purge_s": 25, "collect_s": 5,
    }
    if scenario == "legacy_ai_test_label_leak":
        start["sample_id"] = "SYNTHETIC_PRIVATE_METADATA"
    if scenario == "wrong_start_timing":
        start["purge_s"] = 24

    frames: list[bytes] = []
    if scenario == "normal_with_idle_boot":
        # Mirrors field *shape* seen on PCB after opening FT232R, NOT a
        # copied UART frame. Never classify IDLE readings as coffee data.
        idle = {
            "phase": "idle", "cycle": 0, "sample_idx": 0,
            "timestamp": int(rows[0]["timestamp"]),
        }
        idle.update({field: int(rows[0][field]) for field in ADC_COLS})
        frames.extend([
            b"ATmega boot banner (simulated)\r\n",
            _wire("DIAGNOSTIC", source="mock_boot"),
            (json.dumps(idle) + "\n").encode(),
        ])
    frames.append(b'{"nextion_event":"EVT:AI_START"}\n')
    if scenario != "no_acq_start":
        frames.append(_wire("ACQ_START", **start))

    injected = False
    count = 0
    for index, kind, raw in _firmware_samples(rows):
        if kind == "sensor":
            count += 1
            if not injected and count == 3:
                injected = True
                if scenario == "duplicate_acq_start":
                    frames.append(_wire("ACQ_START", **start))
                if scenario == "disconnect_mid_sample":
                    frames.append(raw.encode()[:19])
                    break
                if scenario == "missing_adc":
                    obj = json.loads(raw)
                    del obj["adc_mq3"]
                    raw = json.dumps(obj)
                elif scenario == "duplicate_sensor_idx":
                    obj = json.loads(raw)
                    obj["sample_idx"] = 2
                    raw = json.dumps(obj)
                elif scenario == "stale_timestamp":
                    obj = json.loads(raw)
                    obj["timestamp"] = 0
                    raw = json.dumps(obj)
                elif scenario == "malformed_json_midstream":
                    raw = '{"bad":'
                elif scenario == "invalid_phase_midstream":
                    obj = json.loads(raw)
                    obj["phase"] = "idle"
                    raw = json.dumps(obj)
                elif scenario == "unapproved_inference":
                    raw = json.dumps({"event": "INFERENCE", "result": "light"})
        frames.append(raw.encode("utf-8") + b"\n")

    if scenario not in ("missing_complete", "disconnect_mid_sample"):
        expected_total = len([x for x in rows if x["sample_idx"]])
        if scenario == "wrong_complete_total":
            expected_total -= 1
        frames.append(_wire("ACQ_COMPLETE", cycles=5,
                            total_samples=expected_total))
    return frames


def fragmented(frames: list[bytes]):
    """Deterministically simulate arbitrary USB read boundaries/timeouts."""
    wire = b"".join(frames)
    cursor = 0
    sizes = (1, 7, 31, 2, 83, 19, 5)
    part = 0
    while cursor < len(wire):
        take = sizes[part % len(sizes)]
        yield wire[cursor:cursor + take]
        yield b""  # timeout is NOT a frame delimiter
        cursor += take
        part += 1


def run_case(rows: list[dict], scenario: str) -> dict:
    # Fixed fake clock makes a CPU-speed offline replay independent of
    # machine performance. Timing windows are tested in Stage7 unit QA.
    result = receive_serial_chunks(
        fragmented(make_frames(rows, scenario)), monotonic=lambda: 1.0,
    )
    diag = result["diagnostics"]
    terminal = result["final"]
    return {
        "scenario": scenario,
        "quality": terminal["quality"],
        "status": terminal["status"],
        "reason": terminal["reason"],
        "sensor_samples_accepted_by_bridge": terminal.get("sensor_samples", 0),
        "sensor_frames_parsed": diag["valid_sensor_frames_seen"],
        "serial_bytes_simulated": diag["serial_bytes_received"],
        "partial_tail_bytes_discarded": diag["partial_tail_bytes_discarded"],
        "wire_events_seen": diag["wire_events_seen"],
        "nextion_event_categories": diag["nextion_event_categories"],
        "sensor_phase_categories": diag["sensor_like_phase_categories"],
        "invalid_sensor_by_reason": diag["sensor_like_invalid_frames_by_reason"],
        "acq_start_contract_outcomes": diag["acq_start_contract_outcomes"],
        "terminal_event_count": result["terminal_event_count"],
        "listener_transmitted_bytes": diag["listener_transmitted_bytes"],
        "model_invoked": terminal["model_invoked"],
        "actuator_commands_sent": terminal["actuator_commands_sent"],
        "hardware_serial_opened": False,
        "trace_kind": "simulated_uart_from_original_csv",
    }


def evaluate(source: Path) -> dict:
    gate = stage6_evaluate()
    if gate.get("model_promotion_allowed") is not False or gate.get(
        "runtime_ai_test_result"
    ) != "N/A":
        raise ValueError("release_gate_not_safe_for_transport_qa")
    rows, digest = read_real_csv(source)
    cases = [run_case(rows, scenario) for scenario in SCENARIOS]
    normal = cases[0]
    expected_samples = len([x for x in rows if x["sample_idx"]])
    if (normal["quality"] != "COMPLETE_QA" or
            normal["sensor_samples_accepted_by_bridge"] != expected_samples or
            normal["sensor_phase_categories"].get("idle") != 1 or
            normal["nextion_event_categories"].get("EVT:AI_START") != 1 or
            normal["acq_start_contract_outcomes"].get("accepted") != 1 or
            normal["wire_events_seen"].get("ACQ_COMPLETE") != 1):
        raise ValueError("positive_simulated_transport_not_complete")
    for case in cases:
        if case["status"] != "N/A" or case["hardware_serial_opened"] or (
            case["listener_transmitted_bytes"] != 0 or
            case["model_invoked"] or case["actuator_commands_sent"]
        ):
            raise ValueError("unsafe_transport_result")
        if case["scenario"] in ("normal_with_idle_boot", "clean_no_boot"):
            if case["quality"] != "COMPLETE_QA" or case["terminal_event_count"] != 1:
                raise ValueError("positive_case_failed")
        elif case["scenario"] in (
            "no_acq_start", "legacy_ai_test_label_leak",
            "wrong_start_timing",
        ):
            # In current bridge semantics, rejected/absent START means NO
            # session was created. NOT_STARTED is safe (never a PASS).
            if case["quality"] != "NOT_STARTED" or case["terminal_event_count"] != 0:
                raise ValueError("rejected_start_must_not_fake_session")
        elif case["quality"] != "FAIL_CLOSED" or case["terminal_event_count"] != 1:
            raise ValueError("negative_case_must_fail_closed")
    leak = next(c for c in cases if c["scenario"] == "legacy_ai_test_label_leak")
    if leak["acq_start_contract_outcomes"] != {"ai_test_label_leakage": 1}:
        raise ValueError("legacy_label_leak_not_diagnosed")
    return {
        "type": "stage8_transport_integration.v1",
        "status": "PASS_SOFTWARE_TRANSPORT_HARDWARE_NOT_TESTED",
        "source": {"name": source.name, "sha256": digest,
                   "historical_real_adc_used_in_memory": True,
                   "wire_bytes_are_synthetic_not_a_capture": True},
        "cases": cases,
        "checks": {
            "case_count": len(cases),
            "historical_sensor_rows": expected_samples,
            "all_positive_cases_complete": True,
            "all_negative_cases_fail_safe": True,
            "original_csv_read_only": True,
            "data_values_written_to_evidence": False,
            "label_metadata_used_by_inference": False,
            "nextion_physical_event_observed": False,
            "usb_port_opened": False,
            "mcu_written_to": False,
            "pump_or_valve_operated": False,
            "model_loaded_or_invoked": False,
            "physical_G3_verified": False,
        },
        "release": {"model_status": "N/A", "model_promotion_allowed": False,
                    "device_e2e": "NO_GO"},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dest = args.output.resolve()
    if dest.exists():
        raise FileExistsError("transport_evidence_exists")
    if dest == args.input.resolve() or dest == RAW or RAW in dest.parents:
        raise ValueError("cannot_overwrite_original_raw")
    report = evaluate(args.input)
    # The report has no ADC values or private labels, only fixed categories.
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as out:
        json.dump(report, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write("\n")
    print(report["status"])
    for case in report["cases"]:
        print(case["scenario"], case["quality"], case["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
