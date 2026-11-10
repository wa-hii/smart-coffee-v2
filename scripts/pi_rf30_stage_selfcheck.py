#!/usr/bin/env python3
"""Pure stdlib safety check of isolated Pi RF30 staging files.

Run as `python3 -B -` over SSH stdin; does not open serial or load model.
"""
import json
from pathlib import Path
import sys

STAGE=Path.home()/"smart-coffee-stage7"/"rf30_staging"
assert STAGE.is_dir(), "Pi staging folder missing"
sys.path.insert(0,str(STAGE))

from rf30_pi_result_bridge import (
    BoundedLineFramer, HostSession, ReturnProtocolError, strict_json,
    validate_start, wire_command, BUILD_ID,
)
assert wire_command("B1F503A9","medium")==b"#rf30:B1F503A9:medium;"
assert validate_start({
    "mode":"ai_test","fw_build_id":BUILD_ID,"cycles_total":30,
    "purge_s":25,"collect_s":5,"ai_session_token":"B1F503A9"
})=="B1F503A9"
framer=BoundedLineFramer()
assert framer.feed(b'{"event":"')==[]
assert framer.feed(b'FW_HELLO"}\n')==[b'{"event":"FW_HELLO"}\n']
assert strict_json('{"event":"FW_HELLO"}')["event"]=="FW_HELLO"
try:
    strict_json('{"x":1,"x":2}')
except ReturnProtocolError:
    pass
else:
    raise AssertionError("Duplicate keys were accepted")
session=HostSession()
_,status=session.feed(b"Welcome to SmartCoffee\n")
assert status["status"]=="WAITING_FOR_AI_START"
print("RF30_PI_STAGED_MODULES_OFFLINE_PASS")
