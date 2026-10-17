"""Compile and execute native source timing regression, plus firmware guards."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    main_cpp=(ROOT/'src/main.cpp').read_text(encoding='utf-8')
    nextion=(ROOT/'src/nextion_transport.cpp').read_text(encoding='utf-8')
    assertions={
        'absolute phase transition': 'acqPhaseStartMs = nextPhaseStartMs;' in main_cpp,
        'deadline checked independently of sensor scheduler': 'processAcquisitionState();\n  scheduler.execute();\n  processAcquisitionState();' in main_cpp,
        'only one ADC frame per scheduler tick': 'sensors.printJsonData(acqStateName(), acqCycle, acqSampleIdx);' in main_cpp,
        'ADC does not advance phase': 'processAcquisitionState();' not in main_cpp.split('void adsCallback() {',1)[1],
        'LCD UI is scheduled separately': 'Task taskUi(TASK_INTERVAL_MS_UI, TASK_FOREVER, &uiCallback);' in main_cpp,
        'LCD updates nonblocking': 'nextion.tryText("tRemain", text)' in main_cpp and 'serial_.availableForWrite()' in nextion,
        'fault quarantines partial CSV': 'ACQ_TIMING_FAULT' in main_cpp and 'stopAcquisition(); // listener quarantines' in main_cpp,
        'actual timing reported in completion event': 'elapsed_active_ms' in main_cpp and 'target_active_ms' in main_cpp,
        'baseline preserved': '#define BASELINE_SAMPLES 60' in main_cpp,
        'Take Data preserved': '#define ACQ_DATA_REPETITIONS 30' in main_cpp,
        'AI Test preserved': '#define ACQ_AI_REPETITIONS 5' in main_cpp,
        'Nextion 12 page preserved': 'showNextionPage("pDataRun")' in main_cpp and 'showNextionPage("pDataDone")' in main_cpp,
        'R0 EEPROM guard': '#define IS_CALIBRATING_GAS_SENSOR 0' in main_cpp,
    }
    for name,passed in assertions.items():
        assert passed,name
    with tempfile.TemporaryDirectory() as tmp:
        binary=Path(tmp)/'timing_deadline.exe'
        result=subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror',
                               str(ROOT/'tests/timing_deadline_host.cpp'),'-o',str(binary)],
                              capture_output=True,text=True,timeout=50)
        assert result.returncode==0,result.stderr
        result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=25)
        assert result.returncode==0,result.stdout+'\n'+result.stderr
        print(result.stdout)
    print('FIRMWARE_REALTIME_UI_NONBLOCKING_SOURCE_QA_PASS')

if __name__=='__main__':main()
