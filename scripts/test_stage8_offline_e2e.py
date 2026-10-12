"""Stage8 tests use only original real CSV and in-memory corrupted copies."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys

from stage8_offline_e2e import (
    FAULTS, evaluate, read_real_csv
)

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "data/raw/D-GAW_B33.csv"


def must_raise(call, exc, message: str):
    try:
        call()
    except exc as err:
        assert message in str(err), str(err)
    else:
        raise AssertionError(f"expected exception: {message}")


def main():
    data_before = ORIGINAL.read_bytes()
    rows, digest = read_real_csv(ORIGINAL)
    assert digest == "d5e690f538a3967e2d07ded64903d284a348c1988bcc331a380dd50b0a8be819"
    assert rows and rows[0]["roast_level"] and rows[0]["origin"]
    result = evaluate(ORIGINAL)
    assert len(result["cases"]) == len(FAULTS) + 1
    assert result["status"] == "STAGE8_OFFLINE_CONTRACT_PASS_HARDWARE_NOT_TESTED"
    assert result["scope"]["mcu_live_serial_opened"] is False
    assert result["scope"]["pi_to_mcu_protocol_implemented"] is False
    assert result["stage6"]["ai_result"] == "N/A"
    assert result["device_e2e_release"] == "NO_GO"
    ai = next(c for c in result["cases"] if c["mode"] == "ai_test" and c["injected_fault"] == "none")
    label = next(c for c in result["cases"] if c["mode"] == "labeled_data")
    assert ai["terminal"]["sensor_samples"] == 151
    assert ai["terminal"]["nominal_150_samples"] is False
    assert ai["terminal"]["status"] == "N/A"
    assert label["terminal"]["status"] == "ACQUISITION_QA_ONLY"
    assert label["autosave_simulated_only_no_file_written"] is True
    assert label["autosave_rows_verified_in_memory"] == 151
    assert ai["autosave_rows_verified_in_memory"] == 0
    for c in result["cases"]:
        assert c["terminal_event_count"] == 1
        assert c["model_invocations"] == 0
        assert c["commands_to_atmega"] == 0
        assert c["actuator_operations"] == 0
        assert not c["nextion_presult_mock"]["actual_hmi_updated"]
        if c["injected_fault"] != "none":
            assert c["terminal"]["quality"] == "FAIL_CLOSED"
            assert c["terminal"]["status"] == "N/A"
    assert ORIGINAL.read_bytes() == data_before
    assert evaluate(ORIGINAL) == result
    with TemporaryDirectory() as temp:
        output = Path(temp) / "stage8.json"
        def call_cli(destination):
            return subprocess.run([
                sys.executable, str(ROOT / "scripts/stage8_offline_e2e.py"),
                "--input", str(ORIGINAL), "--output", str(destination),
            ], capture_output=True, text=True, check=False)
        run = call_cli(output)
        assert run.returncode == 0, run.stderr
        assert json.loads(output.read_text(encoding="utf8")) == result
        second = call_cli(output)
        assert second.returncode != 0
        assert "evidence_output_exists" in second.stderr
        direct_raw = call_cli(ORIGINAL)
        assert direct_raw.returncode != 0
        assert "would_modify_original_raw" in direct_raw.stderr
    print("STAGE8_REAL_DATA_OFFLINE_E2E_QA_PASS")


if __name__ == "__main__":
    main()
