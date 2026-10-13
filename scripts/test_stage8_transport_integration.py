"""QA of physical-SAFE, deterministic byte-level integration from real CSV."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from stage8_transport_integration import SCENARIOS, evaluate, run_case
from stage8_offline_e2e import read_real_csv

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/D-GAW_B33.csv"


def main() -> None:
    pristine = SOURCE.read_bytes()
    rows, _ = read_real_csv(SOURCE)
    report = evaluate(SOURCE)
    assert len(report["cases"]) == len(SCENARIOS) == 15
    assert report["status"] == "PASS_SOFTWARE_TRANSPORT_HARDWARE_NOT_TESTED"
    assert report["source"]["wire_bytes_are_synthetic_not_a_capture"]
    assert report["checks"]["usb_port_opened"] is False
    assert report["checks"]["nextion_physical_event_observed"] is False
    assert report["checks"]["physical_G3_verified"] is False
    assert report["release"] == {
        "model_status": "N/A", "model_promotion_allowed": False,
        "device_e2e": "NO_GO",
    }
    good = report["cases"][0]
    assert good["quality"] == "COMPLETE_QA"
    assert good["sensor_samples_accepted_by_bridge"] == 151
    assert good["sensor_phase_categories"]["idle"] == 1
    assert good["sensor_phase_categories"]["collecting"] >= 20
    assert good["sensor_phase_categories"]["purging"] >= 120
    assert good["invalid_sensor_by_reason"] == {"invalid_phase": 1}
    assert good["nextion_event_categories"] == {"EVT:AI_START": 1}
    assert good["acq_start_contract_outcomes"] == {"accepted": 1}
    leak = next(x for x in report["cases"]
                if x["scenario"] == "legacy_ai_test_label_leak")
    assert leak["quality"] == "NOT_STARTED"  # safe reject before session
    assert leak["acq_start_contract_outcomes"] == {"ai_test_label_leakage": 1}
    absent = next(x for x in report["cases"] if x["scenario"] == "no_acq_start")
    assert absent["quality"] == "NOT_STARTED"
    assert absent["terminal_event_count"] == 0
    disconnect = next(x for x in report["cases"]
                      if x["scenario"] == "disconnect_mid_sample")
    assert disconnect["quality"] == "FAIL_CLOSED"
    assert disconnect["partial_tail_bytes_discarded"] > 0
    duplicate = next(x for x in report["cases"]
                     if x["scenario"] == "duplicate_acq_start")
    assert duplicate["quality"] == "FAIL_CLOSED"
    assert duplicate["terminal_event_count"] == 1
    assert duplicate["reason"] == "duplicate_start_while_active"
    assert "SYNTHETIC_PRIVATE_METADATA" not in json.dumps(report)
    assert "adc_tgs822\": " not in json.dumps(report)
    assert evaluate(SOURCE) == report  # deterministic, no random session ids
    assert SOURCE.read_bytes() == pristine
    try:
        run_case(rows, "not_a_scenario")
    except ValueError as exc:
        assert str(exc) == "unknown_transport_scenario"
    else:
        raise AssertionError("must_reject_unknown_scenario")
    with TemporaryDirectory() as temp:
        dst = Path(temp) / "transport.json"
        def cli(out):
            return subprocess.run([
                sys.executable,
                str(ROOT / "scripts/stage8_transport_integration.py"),
                "--input", str(SOURCE), "--output", str(out),
            ], capture_output=True, text=True, check=False)
        first = cli(dst)
        assert first.returncode == 0, first.stderr
        assert json.loads(dst.read_text(encoding="utf-8")) == report
        assert "PASS_SOFTWARE_TRANSPORT_HARDWARE_NOT_TESTED" in first.stdout
        assert cli(dst).returncode != 0  # no accidental overwrite
        raw_path = cli(SOURCE)
        assert raw_path.returncode != 0
    assert SOURCE.read_bytes() == pristine
    print("STAGE8_TRANSPORT_REAL_CSV_INTEGRATION_PASS")


if __name__ == "__main__":
    main()
