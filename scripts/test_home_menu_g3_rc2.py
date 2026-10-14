"""Independent-style offline regression: six Nextion home actions and G3.

Static HMI/source verification plus adversarial in-memory serial tests.
No tty, network, firmware upload, GPIO, pump or valve is accessed.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from stage7_pi_adapter import EXPECTED_FW_HELLO, receive_serial_chunks
from stage8_offline_e2e import _firmware_samples, read_real_csv


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/main.cpp").read_text(encoding="utf-8")
HOME = (ROOT / "nextion/NX4827T043_011/nextion_events/pHome.txt").read_text(
    encoding="utf-8"
)
DISPLAY_ROOT = ROOT / "nextion/NX4827T043_011"


def main() -> int:
    # Confirm exact six-button menu semantics rather than only searching for
    # an event string somewhere in the HMI package.
    actions = {
        "mTest": ("EVT:TEST_START", "pTest"),
        "mData": ("EVT:TAKE_OPEN", "pTake"),
        "mSet": ("EVT:SETTINGS", "pSettings"),
        "mHist": ("EVT:HISTORY", "pHistory"),
        "mCal": ("EVT:CAL_START", "pCal"),
        "mExit": ("EVT:EXIT", None),
    }
    hmi_bytes = (DISPLAY_ROOT / "project/RoastSense_NX4827T043_011_COMPILE_READY.HMI").read_bytes()
    handler = MAIN.split("void handleNextionEvent(const char *event) {", 1)[1]
    handler = handler.split("\nvoid ", 1)[0]
    for button, (event, target) in actions.items():
        pattern = rf"(?ms)^// {re.escape(button)}\s*\nprints \"{re.escape(event)}\",0"
        assert re.search(pattern, HOME), f"wrong HMI touch mapping for {button}"
        assert event.encode() in hmi_bytes, f"missing binary HMI event {event}"
        token = f'strcmp(event, "{event}") == 0'
        assert token in handler, f"missing firmware handler for {event}"
        if target is not None:
            branch = handler.split(token, 1)[1].split('} else if (strcmp(event,', 1)[0]
            assert f'showNextionPage("{target}")' in branch
            assert 'acqState == AcqState::IDLE' in branch, (
                f"{button} must not strand operator away from active stop/cancel"
            )

    # Calibration page navigation must not start sensor calibration. Only a
    # second action from pCal itself can invoke calibrate(), guarded by IDLE.
    cal_token = 'strcmp(event, "EVT:CAL_START") == 0'
    cal = handler.split(cal_token, 1)[1].split('} else if (strcmp(event,', 1)[0]
    assert 'strcmp(nextionPageName, "pCal") != 0' in cal
    assert cal.index('showNextionPage("pCal")') < cal.index('sensors.calibrate()')
    assert 'acqState != AcqState::IDLE' in cal

    exit_branch = handler.split('strcmp(event, "EVT:EXIT") == 0', 1)[1]
    exit_branch = exit_branch.split('} else {', 1)[0]
    assert 'stopAcquisition();' in exit_branch
    assert '"EVT:AI_START"' in handler and '"EVT:DATA_START"' in handler

    # Frozen RC2 has no production ML predictions. The HMI *can* show the
    # layout for roast/origin/confidence without claiming any numeric result.
    inference_h = (ROOT / "src/inference.h").read_text(encoding="utf-8")
    result_body = MAIN.split("void updateNextionInferenceResult() {", 1)[1].split(
        "\nvoid ", 1
    )[0]
    assert "#define USE_ON_DEVICE_INFERENCE 0" in inference_h
    assert 'nextion.text("tMode", "AI NOT VALIDATED")' in MAIN
    assert 'nextion.text("tPi", "LOCAL READY")' not in MAIN
    assert 'nextion.text("tFw", "G3-RC2")' in MAIN
    assert 'nextion.text("tStep4", "LOCAL")' not in MAIN
    assert 'nextion.text("tStep4", "N/A")' in MAIN
    assert 'nextion.text("tRConf", "N/A")' in result_body
    assert 'nextion.text("tOrigin", "N/A")' in result_body
    assert 'nextion.text("tOConf", "N/A")' in result_body
    for key in ("jLight", "jMedium", "jDark"):
        assert f'nextion.progress("{key}", 0)' in result_body

    build = re.search(r'^#define SMART_COFFEE_BUILD_ID "([^"]+)"', MAIN, re.M)
    assert build and build.group(1) == EXPECTED_FW_HELLO["build_id"]
    acq = MAIN.split("void startAcquisition(AcquisitionMode mode) {", 1)[1]
    acq = acq.split("\nvoid stopAcquisition()", 1)[0]
    assert '"fw_build_id"' not in acq  # emitted using escaped C++ JSON
    assert 'fw_build_id' in acq and 'SMART_COFFEE_BUILD_ID' in acq
    assert 'if (mode == AcquisitionMode::LABELED_DATA)' in acq

    # Full five-cycle stream without label and with matching firmware can
    # pass G3, even if the startup FW_HELLO is missed by USB auto-reset.
    csv_file = ROOT / "data/raw/D-GAW_B33.csv"
    rows, _ = read_real_csv(csv_file)
    start = {
        "event": "ACQ_START", "mode": "ai_test", "cycle": 1,
        "phase": "purging", "cycles_total": 5, "purge_s": 25,
        "collect_s": 5, "fw_build_id": build.group(1),
    }
    sensors = [msg.encode() + b"\n" for _, _, msg in _firmware_samples(rows)]
    complete = (json.dumps({"event": "ACQ_COMPLETE", "cycles": 5,
                            "total_samples": 151}).encode() + b"\n")
    def run(start_frame: dict, stream: list[bytes] | None = None) -> dict:
        return receive_serial_chunks(
            [json.dumps(start_frame).encode() + b"\n",
             *(sensors if stream is None else stream), complete],
            monotonic=lambda: 1,
        )

    good = run(start)
    assert good["final"]["quality"] == "COMPLETE_QA"
    assert good["diagnostics"]["physical_g3_complete_verified"] is True
    assert good["final"]["status"] == "N/A"

    # A stale MCU with labels in AI_TEST is never silently accepted.
    leaked = run({**start, "sample_id": "GROUND_TRUTH_NOT_ALLOWED"})
    assert leaked["diagnostics"]["acq_start_contract_outcomes"] == {
        "ai_test_label_leakage": 1,
    }
    assert leaked["diagnostics"]["physical_g3_complete_verified"] is False
    assert "GROUND_TRUTH_NOT_ALLOWED" not in json.dumps(leaked)
    unknown = run({**start, "fw_build_id": "STALE_SOURCE"})
    assert unknown["final"]["quality"] == "COMPLETE_QA"
    assert unknown["diagnostics"]["physical_g3_complete_verified"] is False

    # A physical five-cycle HMI completion cannot mask incomplete Pi data.
    missing = run(start, sensors[:-1])
    assert missing["final"]["quality"] == "FAIL_CLOSED"
    assert missing["diagnostics"]["physical_g3_complete_verified"] is False

    print("HOME_MENU_6_EVENTS_STATIC_PASS")
    print("RC2_G3_IDENTITY_AND_FAIL_CLOSED_ADVERSARIAL_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
