"""RF30 Pi<->MCU protocol regression. NO serial, no joblib, no actuators."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rf30_pi_result_bridge import (
    BUILD_ID,HostSession,ReturnProtocolError,replay_file,
    validate_start,wire_command,LIVE_OPT_IN,MODEL_OPT_IN,live_run,
)
from roast_rf30_pi_inference import ADC_COLUMNS

ROOT=Path(__file__).resolve().parents[1]
CSV=ROOT/"data/dataset sorting/b/kept/D-CAT_B70.csv"
SOURCE=(ROOT/"src/main.cpp").read_text(encoding="utf8")
TOKEN="B1F503A9"


def frames():
    with CSV.open(newline="",encoding="utf-8-sig") as fh:
        rows=list(csv.DictReader(fh))
    assert len(rows)==900
    out=[b'Welcome Smart Coffee (plain-text boot)\n']
    start={"event":"ACQ_START","mode":"ai_test","fw_build_id":BUILD_ID,
           "phase":"purging","cycle":1,"cycles_total":30,
           "purge_s":25,"collect_s":5,"ai_session_token":TOKEN}
    out.append((json.dumps(start)+"\n").encode("utf8"))
    for row in rows:
        sample={"timestamp":int(row["timestamp"]),"cycle":int(row["run_id"]),
                "phase":row["phase"],"sample_idx":int(row["sample_idx"])}
        sample.update({col:int(row[col]) for col in ADC_COLUMNS})
        out.append((json.dumps(sample)+"\n").encode("utf8"))
    out.append(b'{"event":"ACQ_COMPLETE","cycles":30,"total_samples":900}\n')
    out.append((json.dumps({"event":"AI_AWAITING_RESULT","token":TOKEN,
                            "samples":900,"window_ms":30000})+"\n").encode())
    return out


def fail(fn, code):
    try:
        fn()
    except ReturnProtocolError as err:
        assert code in str(err),(str(err),code)
    else:
        raise AssertionError("Expected failure: "+code)


def main():
    assert b"#rf30:B1F503A9:medium;"==wire_command(TOKEN,"medium")
    for token,label in [("0","medium"),("00000000","dark"),
                        (TOKEN,"UNKNOWN"),("b1f503a9","light")]:
        fail(lambda token=token,label=label:wire_command(token,label),
             "invalid_token_or_label")
    message=frames()
    assert len(message)==904
    with TemporaryDirectory() as root:
        output=Path(root)/"rf30_offline.ndjson"
        output.write_bytes(b"".join(message))
        result=replay_file(output)
        assert result["samples"]==900 and result["status"]=="VALIDATED_ONLY_NO_MODEL_TX"
        assert not result["mcu_serial_written"] and not result["pi_serial_opened"]
        assert result["candidate_roast"] is None
        # A three-feature mock ONLY tests the host/MCU wire handshake.
        # This does NOT load or assess the external RF500 model.
        with patch("rf30_pi_result_bridge.predict_capture",
                   return_value={"roast_predicted":"medium"}) as simulated:
            session=HostSession()
            commands=[]
            for raw in message:
                command,_=session.feed(raw,allow_predict=True)
                if command:
                    commands.append(command)
            assert commands==[b"#rf30:B1F503A9:medium;"]
            assert simulated.call_count==1
            _,ack=session.feed((json.dumps({"event":"AI_RESULT_ACK","token":TOKEN,
                                          "roast":"medium"})+"\n").encode())
            assert ack["status"]=="MCU_ACK_CONFIRMED" and session.acknowledged
            _,dup=session.feed(message[-1])
            assert dup["status"]=="IGNORED_AFTER_TERMINAL"
        # Session-bound rejects: wrong build, metadata leak, missing sample,
        # old five-cycle firmware, wrong token, duplicate session, no reply.
        wrong=json.loads(message[1])
        wrong["fw_build_id"]="old"
        fail(lambda:validate_start(wrong),"wrong_firmware")
        wrong=json.loads(message[1]);wrong["roast_level"]="dark"
        fail(lambda:validate_start(wrong),"ground_truth_leakage")
        wrong=json.loads(message[1]);wrong["cycles_total"]=5
        fail(lambda:validate_start(wrong),"wrong_firmware")
        not_started=HostSession()
        _,status=not_started.feed(message[0])
        assert status["status"]=="WAITING_FOR_AI_START"
        fail(lambda:_bad(message[:53]+message[54:]),"bad_cycle_phase_or_index")
        wrong_await=json.loads(message[-1]);wrong_await["token"]="00000001"
        fail(lambda:_bad(message[:-1]+[(json.dumps(wrong_await)+"\n").encode()]),
             "invalid_awaiting_result")
        fail(lambda:_bad(message[:2]+[message[1]]+message[2:]),
             "duplicate_start")
        # Live opt-ins are checked before opening a port/loading joblib.
        fail(lambda:live_run(Path("/dev/ttyUSB0"),"A10KNJBL",Path("none"),
                             Path("none"),serial_ack="",model_ack=""),
             "authorization_missing")
        assert not Path("/dev/ttyUSB0").exists() or sys.platform!="linux"
        # A source-level assertion prevents any accidental promotion in this
        # test: only a separately approved build can display Pi RF results.
        assert "#define ENABLE_PI_RF30_RETURN 0" in SOURCE
        assert 'Serial.print(F("{\\"event\\":\\"AI_RESULT_ACK' in SOURCE
    print("RF30_PI_RETURN_BRIDGE_OFFLINE_QA_PASS",
          {"real_csv_rows":900,"model_deserialized":False,
           "usb_opened":False,"uart_write":False,
           "native_ack_mock":"medium","reply_bytes":len(commands[0])})


def _bad(stream):
    receiver=HostSession()
    for line in stream:
        receiver.feed(line)
    if not receiver.awaiting or not receiver.complete:
        raise ReturnProtocolError("incomplete_stream")


if __name__=="__main__":
    main()
