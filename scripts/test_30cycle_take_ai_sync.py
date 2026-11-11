"""QA: Take Data and AI Test use the same *active* 30-cycle firmware/Pi contract.

Reads real previously recorded ADC CSV, synthesizes firmware-shaped frames in
memory, never opens a serial port, loads a model or drives Nextion/actuators.
Historical 5-cycle G3 test lives in separate, explicitly legacy fixtures.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re

from stage7_bridge import LegacySessionBridge, replay_csv
from stage7_pi_adapter import EXPECTED_FW_HELLO, MAX_STREAM_SECONDS, receive_serial_chunks
from stage8_offline_e2e import _firmware_samples

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "src/main.cpp"
DATA = ROOT / "data/dataset sorting/b/kept/D-CAT_B70.csv"


def check_firmware_contract():
    text = FW.read_text(encoding="utf8")
    assert "#define ACQ_DATA_REPETITIONS 30" in text
    assert "#define ACQ_AI_REPETITIONS ACQ_DATA_REPETITIONS" in text
    assert "#define ACQ_PURGE_SECONDS 25" in text
    assert "#define ACQ_COLLECTION_SECONDS 5" in text
    assert 'nextion.text("tFw", "DATA30-AI30")' in text
    assert '"EST. REMAINING 15:00"' in text
    assert 'Serial.print(ACQ_AI_REPETITIONS)' in text
    assert 'Serial.print(ACQ_DATA_REPETITIONS)' in text
    assert "nextion.progress(\"jAI\", percent)" in text
    assert "const uint32_t totalSeconds = cycleSeconds * ACQ_REPETITIONS" in text
    assert "const uint32_t totalRunSeconds = cycleSeconds * ACQ_REPETITIONS" in text
    # The opt-in standalone SVM uses a different build identity. The
    # original 30-cycle Pi contract must remain the default (#else).
    marker = re.search(
        r'#if SMART_COFFEE_STANDALONE_SVM30\s*'
        r'#define SMART_COFFEE_BUILD_ID "standalone-svm30-bench-20261111"\s*'
        r'#else\s*#define SMART_COFFEE_BUILD_ID "([^"]+)"\s*#endif', text)
    assert marker and marker.group(1) == EXPECTED_FW_HELLO["build_id"]
    assert EXPECTED_FW_HELLO["data_cycles_total"] == 30
    assert EXPECTED_FW_HELLO["ai_cycles_total"] == 30
    assert MAX_STREAM_SECONDS >= 1100  # 900 active + operator start margin


def stream(mode: str, *, faults: str | None = None):
    with DATA.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 900
    start = {
        "event": "ACQ_START", "mode": mode, "cycle": 1,
        "phase": "purging", "cycles_total": 30,
        "purge_s": 25, "collect_s": 5,
        "fw_build_id": EXPECTED_FW_HELLO["build_id"],
    }
    if mode == "labeled_data":
        # Labeled mode may contain operator metadata, which the Pi bridge
        # must never use as predictor features in ai_test mode.
        start.update({"sample_id": "D-CAT", "roast_level": "dark"})
    if faults == "old5":
        start["cycles_total"] = 5
    messages = [json.dumps(EXPECTED_FW_HELLO),json.dumps(start)]
    counter = 0
    for _, kind, payload in _firmware_samples(rows):
        if kind == "sensor":
            counter += 1
            if faults == "one_missing" and counter == 53:
                continue
        messages.append(payload)
    messages.append(json.dumps({
        "event": "ACQ_COMPLETE",
        "cycles": 5 if faults == "old5" else 30,
        "total_samples": 900,
    }))
    return [(message+"\n").encode("utf8") for message in messages]


def run():
    check_firmware_contract()
    raw = DATA.read_bytes()
    assert len(raw) > 100_000
    # New active Pi default must accept exactly 30x(25+5).
    for mode in ("ai_test", "labeled_data"):
        result = receive_serial_chunks(stream(mode), monotonic=lambda: 1)
        assert result["final"]["quality"] == "COMPLETE_QA",result["final"]
        assert result["final"]["sensor_samples"] == 900
        assert result["final"]["nominal_900_samples"]
        assert result["final"]["status"] == (
            "N/A" if mode == "ai_test" else "ACQUISITION_QA_ONLY"
        )
        assert result["diagnostics"]["physical_g3_compatibility_verified"] is True
        assert result["diagnostics"]["physical_g3_complete_verified"] is True
        assert result["diagnostics"]["valid_sensor_frames_seen"] == 900
        assert result["diagnostics"]["listener_transmitted_bytes"] == 0
        assert result["terminal_event_count"] == 1
        assert result["final"]["model_invoked"] is False
    # A real 900-row historical take-data file can be replayed as ai_test
    # WITHOUT using its actual roast/origin/batch metadata for prediction.
    simulated = replay_csv(DATA,session_factory=lambda:"testai30replay001")
    assert simulated["bridge"]["quality"] == "COMPLETE_QA",simulated["bridge"]
    assert simulated["bridge"]["sensor_samples"] == 900
    assert simulated["bridge"]["nominal_900_samples"]
    # Five-cycle firmware mode and incomplete 900-cycle batches fail closed.
    for fault in ("old5","one_missing"):
        result = receive_serial_chunks(stream("ai_test",faults=fault),
                                       monotonic=lambda: 1)
        assert result["final"]["quality"] != "COMPLETE_QA",result["final"]
        assert not result["diagnostics"]["physical_g3_complete_verified"]
        assert result["diagnostics"]["listener_transmitted_bytes"] == 0
    # No physical side effects, including reads; CSV was never modified.
    assert DATA.read_bytes()==raw
    print("TAKE_DATA_AI_TEST_30CYCLE_CONTRACT_QA_PASS",
          {"modes":2,"cycles_each":30,"samples_each":900,
           "purging_s":25,"collecting_s":5,"duration_s":900,
           "old5_rejected":True,"missing_sensor_rejected":True,
           "usb_opened":False,"model_loaded":False,"nextion_updated":False})


if __name__=="__main__":
    run()
