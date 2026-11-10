"""Static fail-closed QA for Pi/MCU 30-cycle RF result handshake."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/"src/main.cpp").read_text(encoding="utf8")
HEADER=(ROOT/"src/ai_rf30_return.h").read_text(encoding="utf8")


def section(name:str, next_name:str)->str:
    prefix=name+" {"
    assert MAIN.count(prefix)==1,(name,MAIN.count(prefix))
    return MAIN.split(prefix,1)[1].split(next_name,1)[0]


def run():
    assert "#define ENABLE_PI_RF30_RETURN 0" in MAIN
    assert "#define ACQ_DATA_REPETITIONS 30" in MAIN
    assert "#define ACQ_AI_REPETITIONS ACQ_DATA_REPETITIONS" in MAIN
    start=section("void startAcquisition(AcquisitionMode mode)",
                  "\nvoid stopAcquisition()")
    assert start.index("aiRf30Pending = false;") < start.index("acqMode = mode;")
    assert start.index("aiRf30SessionToken =") < start.index(
        'Serial.print(F("{\\"event\\":\\"ACQ_START')
    assert '"ai_session_token"' not in MAIN  # properly escaped C++ JSON
    assert 'ai_session_token' in start
    assert 'if (mode == AcquisitionMode::AI_TEST)' in start
    finish=section("void processAcquisitionState()", "\nvoid setActuators()")
    assert finish.index("printAcquisitionSummary();") < finish.index(
        'AI_AWAITING_RESULT')
    assert finish.index('showNextionPage("pResult");') < finish.index(
        'AI_AWAITING_RESULT')
    assert 'acqTotalSamples == 900' in finish
    assert 'AI_RESULT_UNAVAILABLE' in finish
    assert "#if ENABLE_PI_RF30_RETURN" in finish
    reply=section("void processAiRf30Reply(const char *cmd)",
                  "\nvoid processCommand(")
    assert 'AiRf30Return::decode(cmd, &token, &roast)' in reply
    assert 'token != aiRf30SessionToken' in reply
    assert 'strcmp(nextionPageName, "pResult") != 0' in reply
    assert 'acqState != AcqState::IDLE' in reply
    assert reply.index('aiRf30Pending = false;') < reply.index(
        'updateNextionInferenceResult();')
    assert 'AI_RESULT_ACK' in reply and 'AI_RESULT_NACK' in reply
    assert '"tRConf", "N/A"' in MAIN
    assert '"tOrigin", "N/A"' in MAIN
    assert '"tOConf", "N/A"' in MAIN
    assert 'AI_RF30_REPLY_TIMEOUT_MS = 30000UL' in MAIN
    assert 'AI_RESULT_TIMEOUT' in MAIN
    assert 'case Roast::LIGHT' in HEADER
    assert 'strcmp(name,"medium")' in HEADER
    assert 'token == 0' in HEADER
    assert 'strlen(cmd)' in HEADER
    assert '#rf30:' in HEADER
    assert 'inference.printResult();' in MAIN  # safe legacy default
    print("RF30_FIRMWARE_RESULT_GATE_CONTRACT_PASS")


if __name__=="__main__":
    run()
