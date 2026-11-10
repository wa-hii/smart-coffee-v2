#!/usr/bin/env python3
"""Candidate Pi 5 -> ATmega -> Nextion RF500 return protocol.

Default: OFFLINE ONLY, no serial port opened and no model loaded.
Recorded firmware streams can be validated with --replay-ndjson.

Only explicit live mode, an isolated trusted model artifact, matching firmware
build/session ID, complete 30x(25+5) capture, and 2 independent opt-ins can
authorize a result transmission. This is an engineering test adapter, NOT a
model release/production service. Never controls pumps or valves.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time
from tempfile import TemporaryDirectory

from roast_rf30_pi_inference import EXPECTED_SHA, predict_capture, verify_artifact
from roast_rf30_pi_stream_replay import collect_firmware_ndjson

ROOT=Path(__file__).resolve().parents[1]
BUILD_ID="take30-ai30-rfhost-20261110"
TIMEOUT_S=1260
MAX_FRAME=4096
LIVE_OPT_IN="I_APPROVE_SUPERVISED_RF30_SERIAL_READ_WRITE"
MODEL_OPT_IN="I_ACCEPT_UNVALIDATED_RF500_FOR_BENCH_ONLY"
TOKEN_RE=re.compile(r"^[0-9A-F]{8}$")
LABELS={"light","medium","dark"}
USB_BY_ID=re.compile(r"^/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_[A-Za-z0-9_-]+-if00-port0$")


class ReturnProtocolError(ValueError):
    """A session or result failed a safety/compatibility check."""


def strict_json(line: str) -> dict:
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:
                raise ReturnProtocolError("duplicate_json_key")
            result[key]=value
        return result
    try:
        obj=json.loads(line,object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(
                           ReturnProtocolError("nonfinite_json_value")))
    except json.JSONDecodeError as e:
        raise ReturnProtocolError("malformed_json") from e
    if not isinstance(obj,dict):
        raise ReturnProtocolError("json_frame_not_object")
    return obj


class BoundedLineFramer:
    """Hold partial UART frames until LF; reject oversized frames (fail closed)."""
    def __init__(self):
        self.buffer=bytearray()
    def feed(self,chunk:bytes):
        lines=[]
        if not isinstance(chunk,bytes):
            raise ReturnProtocolError("invalid_chunk_type")
        for byte in chunk:
            if len(self.buffer)>=MAX_FRAME:
                raise ReturnProtocolError("serial_frame_overflow")
            self.buffer.append(byte)
            if byte==10:
                lines.append(bytes(self.buffer))
                self.buffer.clear()
        return lines


def wire_command(token:str, label:str)->bytes:
    if not TOKEN_RE.fullmatch(token) or token=="00000000" or label not in LABELS:
        raise ReturnProtocolError("invalid_token_or_label")
    return (f"#rf30:{token}:{label};").encode("ascii")


def validate_start(event:dict)->str:
    if (event.get("mode")!="ai_test" or
        event.get("fw_build_id")!=BUILD_ID or
        event.get("cycles_total")!=30 or
        event.get("purge_s")!=25 or
        event.get("collect_s")!=5):
        raise ReturnProtocolError("start_contract_wrong_firmware_or_mode")
    if any(field in event for field in ("roast_level","origin_code",
                                        "sample_id","origin","label")):
        raise ReturnProtocolError("ai_test_ground_truth_leakage")
    token=event.get("ai_session_token")
    if not isinstance(token,str) or not TOKEN_RE.fullmatch(token) or token=="00000000":
        raise ReturnProtocolError("missing_or_invalid_session_token")
    return token


class HostSession:
    def __init__(self):
        self.token=None
        self.capture=[]
        self.samples=0
        self.complete=False
        self.awaiting=False
        self.command=None
        self.acknowledged=False
        self.terminal=False
        self.last_ts=-1
        self.error=None

    def feed(self, line:bytes|str,*,model_path=None,metadata_path=None,
             model=None,allow_predict=False,predictor=None):
        """Feed a COMPLETE newline-terminated UTF-8 JSON firmware frame.

        Returns (optional command bytes, public diagnostic). No side effects.
        Caller may write bytes only after live gates and post-complete ACK.
        """
        if self.terminal:
            return None, {"status":"IGNORED_AFTER_TERMINAL"}
        if isinstance(line,bytes):
            if len(line)>MAX_FRAME or b"\x00" in line:
                raise ReturnProtocolError("invalid_or_oversized_serial_frame")
            try: line=line.decode("utf8")
            except UnicodeDecodeError as e:
                raise ReturnProtocolError("invalid_serial_encoding") from e
        if len(line.encode("utf8"))>MAX_FRAME:
            raise ReturnProtocolError("oversized_serial_frame")
        # Duplicate JSON keys, NaN and non-objects are not acceptable.
        try:
            obj=strict_json(line)
        except Exception as e:
            # Legacy firmware prints a plain-text welcome banner on boot.
            # Before ACQ_START these are not part of a captured session.
            if self.token is None:
                return None, {"status":"WAITING_FOR_AI_START"}
            raise ReturnProtocolError("malformed_serial_json") from e
        event=obj.get("event")
        if self.token is None:
            if event!="ACQ_START":
                return None, {"status":"WAITING_FOR_AI_START"}
            self.token=validate_start(obj)
            self.capture=[line.rstrip("\r\n")]
            return None, {"status":"CAPTURE_STARTED","cycles":30}
        if event=="ACQ_START":
            raise ReturnProtocolError("duplicate_start")
        if event in ("ACQ_STOP","ACQ_TIMING_FAULT"):
            raise ReturnProtocolError("capture_aborted")
        if event=="ACQ_COMPLETE":
            if self.complete or self.samples!=900 or obj.get("cycles")!=30 or obj.get("total_samples")!=900:
                raise ReturnProtocolError("incomplete_30cycle_capture")
            self.complete=True
            self.capture.append(line.rstrip("\r\n"))
            return None,{"status":"CAPTURE_COMPLETE","samples":self.samples}
        if event=="AI_AWAITING_RESULT":
            if (not self.complete or self.awaiting or obj.get("token")!=self.token
                or obj.get("samples")!=900 or obj.get("window_ms")!=30000):
                raise ReturnProtocolError("invalid_awaiting_result_handshake")
            self.awaiting=True
            with TemporaryDirectory(prefix="rf30_host_result_") as t:
                path=Path(t)/"firmware_ai_test.ndjson"
                path.write_text("\n".join(self.capture)+"\n",encoding="utf8")
                # A SECOND independent strict stream validation checks complete
                # 30-cycle ADC data with no inferred/missing samples.
                records=collect_firmware_ndjson(path)
                if len(records)!=900:
                    raise ReturnProtocolError("missing_900_records")
                if not allow_predict:
                    self.terminal=True
                    return None,{"status":"VALIDATED_ONLY_NO_MODEL_TX","samples":900}
                import csv
                from roast_rf30_pi_inference import ADC_COLUMNS
                csv_file=Path(t)/"sensor.csv"
                fields=("timestamp","run_id","phase","sample_idx",*ADC_COLUMNS)
                with csv_file.open("w",newline="",encoding="utf8") as fh:
                    writer=csv.DictWriter(fh,fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(records)
                if predictor is not None:
                    # Explicit model adapter used by the SVM30 bench workflow.
                    # All wire validation above is shared across RF and SVM.
                    candidate=predictor(csv_file)
                else:
                    candidate=predict_capture(csv_file,model_path,metadata_path,
                                              validate_only=False,model=model)
            roast=candidate.get("roast_predicted")
            if roast not in LABELS:
                raise ReturnProtocolError("invalid_model_roast")
            self.command=wire_command(self.token,roast)
            return self.command,{"status":"RESULT_READY_FOR_SUPERVISED_TX",
                                 "roast":roast,"origin":None,
                                 "calibrated_confidence":None,
                                 "training_data_used_as_ground_truth":False}
        if event=="AI_RESULT_ACK":
            if (not self.awaiting or self.command is None or self.acknowledged
                or obj.get("token")!=self.token
                or obj.get("roast")!=self.command.decode().split(":")[-1].rstrip(";")):
                raise ReturnProtocolError("wrong_or_duplicate_result_ack")
            self.acknowledged=True
            self.terminal=True
            return None,{"status":"MCU_ACK_CONFIRMED","roast":obj["roast"],
                         "pi_to_mcu_transmitted":"caller_owned"}
        if event in ("AI_RESULT_TIMEOUT","AI_RESULT_NACK"):
            raise ReturnProtocolError("mcu_denied_or_timed_out")
        if self.complete:
            return None,{"status":"WAITING_FOR_MCU_AWAIT"}
        if event is None and "phase" in obj and "sample_idx" in obj:
            index=self.samples
            if index>=900:
                raise ReturnProtocolError("too_many_samples")
            cycle=index//30+1
            phase="purging" if index%30<25 else "collecting"
            idx=index%30+1 if index%30<25 else index%30-24
            if (obj.get("cycle")!=cycle or obj.get("phase")!=phase or
                obj.get("sample_idx")!=idx):
                raise ReturnProtocolError("bad_cycle_phase_or_index")
            try:
                timestamp=int(obj["timestamp"])
            except (ValueError,TypeError,KeyError) as e:
                raise ReturnProtocolError("invalid_timestamp") from e
            if timestamp<=self.last_ts:
                raise ReturnProtocolError("stale_timestamp")
            self.last_ts=timestamp
            # Enforce full 10-channel ADC contract before appending the frame.
            from roast_rf30_pi_inference import ADC_COLUMNS
            if not all(isinstance(obj.get(k),int) and
                       not isinstance(obj[k],bool) and
                       0<=obj[k]<=32767 for k in ADC_COLUMNS):
                raise ReturnProtocolError("invalid_sensor_adc")
            self.samples+=1
            self.capture.append(line.rstrip("\r\n"))
            return None,{"status":"SAMPLE_ACCEPTED","samples":self.samples}
        if event in ("PHASE_CHANGE","ACQ_PAUSE","ACQ_RESUME"):
            self.capture.append(line.rstrip("\r\n"))
            return None,{"status":"AUXILIARY_EVENT"}
        # Existing firmware may emit INFERENCE N/A before awaiting Pi.
        if event in ("INFERENCE", "FW_HELLO"):
            return None,{"status":"NON_SENSOR_STATUS"}
        raise ReturnProtocolError("unknown_frame_during_capture")


def replay_file(path:Path,*,allow_predict=False,model_path=None,
                metadata_path=None,model=None):
    if not path.is_file():
        raise FileNotFoundError(path)
    session=HostSession()
    status=None
    for raw in path.read_bytes().splitlines():
        _,status=session.feed(raw,allow_predict=allow_predict,model_path=model_path,
                              metadata_path=metadata_path,model=model)
    if not session.awaiting or not session.complete or session.samples!=900:
        raise ReturnProtocolError("replay_incomplete_or_no_mcu_handshake")
    return {"status":status["status"] if status else "UNKNOWN",
            "samples":session.samples,
            "cycles":30,
            "model_loaded":bool(allow_predict),
            "pi_serial_opened":False,
            "mcu_serial_written":False,
            "nextion_physical_updated":False,
            "candidate_roast":session.command.decode().split(":")[-1].rstrip(";")
                if session.command else None}


def live_run(port:Path, expected_serial:str, model_path:Path, metadata_path:Path,
             *, serial_ack:str, model_ack:str, max_seconds:int=TIMEOUT_S):
    if serial_ack!=LIVE_OPT_IN or model_ack!=MODEL_OPT_IN:
        raise ReturnProtocolError("explicit_bench_live_authorization_missing")
    if not USB_BY_ID.fullmatch(str(port)) or expected_serial not in port.name:
        raise ReturnProtocolError("unexpected_usb_by_id_device")
    if not (port.is_symlink() and port.exists() and port.resolve().name.startswith("ttyUSB")):
        raise ReturnProtocolError("usb_device_not_connected")
    if not 905<=max_seconds<=TIMEOUT_S:
        raise ReturnProtocolError("invalid_live_session_timeout")
    # Explicit artifact approval is required BEFORE touching serial/DTR.
    verify_artifact(model_path,metadata_path)
    import sklearn
    from roast_rf30_pi_inference import EXPECTED_SKLEARN_VERSION
    if sklearn.__version__!=EXPECTED_SKLEARN_VERSION:
        raise ReturnProtocolError("wrong_sklearn_version")
    import joblib
    model=joblib.load(model_path)  # only SHA-pinned, trusted model
    import serial
    conn=serial.Serial(port=None,baudrate=115200,timeout=1,rtscts=False,
                       dsrdtr=False,exclusive=True)
    conn.dtr=False;conn.rts=False
    session=HostSession()
    start=time.monotonic()
    last_rx=start
    transmitted=False
    try:
        conn.port=str(port)
        conn.open()  # MAY RESET MCU: call only with onsite supervision/SOP
        print("RF30_SERIAL_LISTENER_READY_SUPERVISED",flush=True)
        framer=BoundedLineFramer()
        while time.monotonic()-start<max_seconds:
            chunk=conn.read(512)
            if chunk:
                last_rx=time.monotonic()
            elif session.token and time.monotonic()-last_rx>=10:
                raise ReturnProtocolError("serial_idle_timeout")
            for line in framer.feed(chunk):
                try:
                    command,status=session.feed(line,allow_predict=True,
                           model_path=model_path,metadata_path=metadata_path,model=model)
                except ReturnProtocolError:
                    raise
                if command is not None:
                    if transmitted:
                        raise ReturnProtocolError("duplicate_tx_attempt")
                    conn.write(command)  # only a 30-cycle session RF result
                    conn.flush()
                    transmitted=True
                if status["status"]=="MCU_ACK_CONFIRMED":
                    return {"status":"SUPERVISED_RF30_MCU_ACK",
                            "roast":status["roast"],"samples":900,
                            "serial_tx":transmitted,
                            "lcd_visual_confirmed":False}
                if status["status"]=="VALIDATED_ONLY_NO_MODEL_TX":
                    return status
        raise ReturnProtocolError("listener_window_expired")
    finally:
        conn.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True)
    g.add_argument("--replay-ndjson",type=Path)
    g.add_argument("--serial-live",type=Path)
    p.add_argument("--model",type=Path)
    p.add_argument("--metadata",type=Path)
    p.add_argument("--expected-ftdi-serial",default="")
    p.add_argument("--ack-serial",default="")
    p.add_argument("--ack-model",default="")
    p.add_argument("--max-seconds",type=int,default=TIMEOUT_S)
    args=p.parse_args(argv)
    if args.replay_ndjson:
        if args.model or args.metadata:
            p.error("Offline mode defaults to validation-only; use Python test harness for mock-model replay")
        result=replay_file(args.replay_ndjson)
    else:
        if not args.model or not args.metadata or not args.expected_ftdi_serial:
            p.error("Live requires model, metadata and expected FTDI serial")
        result=live_run(args.serial_live,args.expected_ftdi_serial,
                        args.model,args.metadata,
                        serial_ack=args.ack_serial,model_ack=args.ack_model,
                        max_seconds=args.max_seconds)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return 0


if __name__=="__main__":
    sys.exit(main())
