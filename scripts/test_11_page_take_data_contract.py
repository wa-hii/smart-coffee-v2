"""Offline guard: 11-page Nextion layout cannot navigate to pDataRun.

No physical UART access or firmware flashing.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    source=(ROOT/'src/main.cpp').read_text(encoding='utf-8')
    assert 'showNextionPage("pDataRun")' not in source
    assert 'nextion.page("pDataRun")' not in source
    assert 'pDataRun.tSensors' not in source
    assert 'strcmp(nextionPageName, "pDataRun")' not in source
    assert 'showNextionPage("pTake")' in source
    assert 'showNextionPage("pDataDone")' in source
    assert 'strcmp(nextionPageName, "pTake") != 0' in source
    assert 'nextion.text("tStat", text)' in source
    assert 'UI_SELECTION_LOCKED_DURING_ACQ' in source
    assert 'nextion.touch("mStart", false)' in source
    assert 'updateNextionRunStatus();' in source
    assert '#define ACQ_DATA_REPETITIONS 30' in source
    assert '#define ACQ_AI_REPETITIONS 5' in source
    assert '#define BASELINE_SAMPLES 60' in source
    print('ELEVEN_PAGE_FIRMWARE_NAVIGATION_SOURCE_QA_PASS')


if __name__=='__main__':
    main()
