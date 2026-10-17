"""Static read-only contract: firmware Take Data uses 12-page Nextion layout."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'nextion/NX4827T043_011/tools'
sys.path.insert(0,str(TOOLS))
from recover_editor_saved_datarun_20261017 import OUTPUT, validate, hmi_helper
import hashlib
import subprocess


def main():
    source=(ROOT/'src/main.cpp').read_text(encoding='utf-8')
    assert 'showNextionPage("pDataRun")' in source
    assert 'showNextionPage("pDataDone")' in source
    assert 'strcmp(nextionPageName, "pDataRun") != 0' in source
    for item in ('"tSample"','"tCycle"','"jCycle"','"tPhase"',
                 '"tRemain"','"tTemp"','"tHum"','"tSensors"'):
        assert item in source, item
    assert 'nextion.tryProgress("jCycle",' in source
    assert 'updateNextionSensorSnapshot()' in source
    assert 'UI_SELECTION_LOCKED_DURING_ACQ' in source
    assert '#define ACQ_DATA_REPETITIONS 30' in source
    assert '#define ACQ_AI_REPETITIONS 5' in source
    assert '#define BASELINE_SAMPLES 60' in source
    assert '#define IS_CALIBRATING_GAS_SENSOR 0' in source
    assert '#define USE_ON_DEVICE_INFERENCE 0' in (ROOT/'src/inference.h').read_text(encoding='utf-8')
    try:
        raw=OUTPUT.read_bytes()
    except PermissionError:
        # Nextion Editor locks opened HMI files for exclusive access. Verify
        # the exact last-committed bytes; never close the user's unsaved UI.
        relative=OUTPUT.relative_to(ROOT).as_posix()
        raw=subprocess.check_output(['git','show',f'HEAD:{relative}'],cwd=ROOT)
        print('INFO_HMI_EDITOR_FILE_LOCK_USING_LAST_COMMITTED_SNAPSHOT')
    assert hashlib.sha256(raw).hexdigest()=='4c117d6508506bb8a4a57331d47100b60b251849faa81e39dcd6a47c7a9a8c5a'
    validate(raw,hmi_helper())
    print('TWELVE_PAGE_NEXTION_TAKE30_AI5_BASELINE60_QA_PASS')


if __name__=='__main__':
    main()
