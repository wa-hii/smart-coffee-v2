"""Regresi offline urutan fase, metadata AI_TEST, dan pengaman diagnostik.

Membaca firmware secara statis dan menyimulasikan waktu ideal 1 Hz. Tes ini
tidak menjalankan MCU, menulis data mentah, ataupun membuka port serial.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/main.cpp").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    assert MAIN.count(start) == 1, f"Penanda kode tidak unik: {start}"
    return MAIN.split(start, 1)[1].split(end, 1)[0]


def test_event_order_and_sampling() -> None:
    callback = section("void adsCallback() {", "\n}")
    ordered = (
        "sensors.readAll();",
        "++acqSampleIdx;",
        "sensors.printJsonData(acqStateName(), acqCycle, acqSampleIdx);",
    )
    positions = [callback.index(token) for token in ordered]
    assert positions == sorted(positions), "Sampel harus terkirim sebelum transisi/COMPLETE"
    # Current firmware resolves absolute deadlines in loop(), independently
    # of ADS callback to avoid changing the phase before the final sample.
    loop = section("void loop() {", "\n}")
    assert loop.count("processAcquisitionState();") == 2
    assert loop.index("scheduler.execute();") > loop.index("processAcquisitionState();")
    assert "if (acqState == AcqState::COLLECTING || acqState == AcqState::PURGING)" in callback
    # Clean-air calibration has a distinct baseline JSON path.
    assert callback.count("sensors.printJsonData(acqStateName()") == 1

    # Model perilaku yang diharapkan jika callback berjalan ideal setiap 1s.
    cycle = 1
    phase = "purging"
    phase_start = 0
    sample_idx = 0
    events = []
    # Both active modes now run 30 cycles (900 total 1 Hz observations).
    for now in range(1000, 901000, 1000):
        sample_idx += 1
        events.append(("SENSOR", cycle, phase, sample_idx))
        seconds = 25 if phase == "purging" else 5
        if now - phase_start >= seconds * 1000:
            if phase == "purging":
                phase = "collecting"
            elif cycle == 30:
                events.append(("ACQ_COMPLETE", 30, "complete", 0))
                break
            else:
                cycle += 1
                phase = "purging"
            phase_start = now
            sample_idx = 0
            events.append(("PHASE_CHANGE", cycle, phase, 0))

    samples = [event for event in events if event[0] == "SENSOR"]
    assert len(samples) == 900
    assert events[-1][0] == "ACQ_COMPLETE"
    assert samples[-1] == ("SENSOR", 30, "collecting", 5)
    counts = Counter((e[1], e[2]) for e in samples)
    assert counts == {
        (cycle_id, ph): count
        for cycle_id in range(1, 31)
        for ph, count in (("purging", 25), ("collecting", 5))
    }, counts
    for i, event in enumerate(events):
        if event[0] == "PHASE_CHANGE":
            assert events[i - 1][0] == "SENSOR"
    print("STAGE1_EVENT_ORDER_OFFLINE_PASS")


def test_ai_labels_and_host_compatibility() -> None:
    start = section("void startAcquisition(AcquisitionMode mode) {",
                    "\nvoid stopAcquisition()")
    label_guard = "if (mode == AcquisitionMode::LABELED_DATA) {"
    assert start.count(label_guard) == 1
    before, _, after = start.partition(label_guard)
    labeled, _, common = after.partition('  Serial.print(F(",\\\"cycles_total\\\":"));')
    assert labeled and common
    for field in ('sample_id', 'roast_level', 'origin_code', 'batch_id', 'filename'):
        assert field in labeled, field
        assert field not in before and field not in common, f"Label bocor: {field}"
    assert 'F("ai_test")' in start and 'F("labeled_data")' in start
    assert "#define ACQ_DATA_REPETITIONS 30" in MAIN
    assert "#define ACQ_AI_REPETITIONS ACQ_DATA_REPETITIONS" in MAIN
    assert 'nextion.text("tFw", "DATA30-AI30")' in MAIN
    assert '"ai_cycles_total":5' not in MAIN

    service = (ROOT / "scripts/lcd_acquisition_service.py").read_text(encoding="utf-8")
    assert 'if data.get("mode") != "labeled_data":' in service
    print("STAGE1_AI_TEST_NO_GROUND_TRUTH_CONTRACT_PASS")


def test_unsafe_commands_disabled() -> None:
    assert "#define ENABLE_MANUAL_ACTUATOR_TESTS 0" in MAIN
    command = section("void processCommand(const char *cmd) {",
                      "\n// ═══════════════════════════════════════════════════════════════════════════════\n//  ADS CALLBACK")
    assert 'F("{\\\"error\\\":\\\"PIN_SCAN_DISABLED\\\"}")' in command
    assert "scanPins" not in command and "pinMode(" not in command
    assert command.count("#if ENABLE_MANUAL_ACTUATOR_TESTS") == 3
    assert command.count('MANUAL_ACTUATOR_DISABLED') == 3
    assert 'if (sensorsReady && sensors.allAdcAvailable())' in command
    assert 'I2C scan disabled during acquisition' in command
    print("STAGE1_SAFE_COMMANDS_OFFLINE_PASS")


def main() -> int:
    test_event_order_and_sampling()
    test_ai_labels_and_host_compatibility()
    test_unsafe_commands_disabled()
    print("STAGE1_FIRMWARE_CONTRACT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
