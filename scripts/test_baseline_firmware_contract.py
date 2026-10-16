"""Static source regression for Nextion baseline mode and corrected R0 arithmetic."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    source = (ROOT/"src/main.cpp").read_text(encoding="utf-8")
    sensor = (ROOT/"src/sensor.cpp").read_text(encoding="utf-8")
    sensor_h = (ROOT/"src/sensor.h").read_text(encoding="utf-8")
    touch = (ROOT/"nextion/NX4827T043_011/nextion_events/pCal.txt").read_text(encoding="utf-8")
    assert 'EVT:CAL_START' in touch and 'mStart' in touch
    branch = source.split('} else if (strcmp(event, "EVT:CAL_START") == 0) {', 1)[1].split('} else if (strcmp(event,', 1)[0]
    assert 'BASELINE_START' in branch
    assert 'baselineCaptureActive = true' in branch
    assert 'actuator.setPurging()' in branch
    assert 'sensors.calibrate()' not in branch
    assert 'EEPROM.write(' not in branch and 'saveR0ToEeprom(' not in branch
    assert '#define BASELINE_SAMPLES 60' in source
    assert 'BASELINE_SAMPLE' in sensor
    assert 'BASELINE_COMPLETE' in source
    assert 'stopBaselineCapture' in source
    assert '#define IS_CALIBRATING_GAS_SENSOR 0' in source
    assert '#define EEPROM_MAGIC_VALUE  0xA6' in sensor_h
    assert sensor.count('= calc_r0 / 10.0f;') == 10
    assert 'saveR0ToEeprom(i, candidates[i]);' in sensor
    assert 'if (!isfinite(candidates[i]) || candidates[i] <= 0.0f)' in sensor
    assert 'r0 / SENSOR_RL' not in sensor
    assert 'EEPROM.write(EEPROM_MAGIC_ADDR, 0);' in sensor
    assert 'EEPROM.write(EEPROM_MAGIC_ADDR, EEPROM_MAGIC_VALUE);' in sensor
    assert '#define USE_ON_DEVICE_INFERENCE 0' in (ROOT/"src/inference.h").read_text(encoding="utf-8")
    print("BASELINE_HMI_AND_SAFE_R0_SOURCE_CONTRACT_PASS")

if __name__ == "__main__":
    main()
