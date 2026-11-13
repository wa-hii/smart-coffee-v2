#!/usr/bin/env python3
"""QA offline untuk parser dan persyaratan DTR/RTS pada listener Pi."""
from pathlib import Path

import pi_second_pcb_passive_id as app


def run():
    hello = (b'{"event":"FW_HELLO","build_id":"take30-ai30-rfhost-20261110"}\n'
             b'{"warn":"ADS1115 #1 tidak terdeteksi"}\n')
    parsed = app.claimed_firmware(hello)
    assert parsed["fw_hello_seen"] is True
    assert parsed["build_ids_claimed"] == ["take30-ai30-rfhost-20261110"]
    assert len(parsed["startup_messages"]) == 2
    assert not app.claimed_firmware(b"\xff\xfe garbage\r\n")["fw_hello_seen"]
    assert app.BAUD == 115200
    source = Path(app.__file__).read_text(encoding="utf8")
    assert source.index("serial.dtr = False") < source.index("serial.open()")
    assert source.index("serial.rts = False") < source.index("serial.open()")
    assert "serial.write(" not in source
    print("PI_SECOND_PCB_PASSIVE_ID_NO_TX_QA_PASS")


if __name__ == "__main__":
    run()
