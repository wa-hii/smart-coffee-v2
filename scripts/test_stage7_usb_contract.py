"""Offline source contract: board USB hosts Serial0, Nextion reserves Serial2.

No USB/tty opened. These assertions do not prove installed firmware or
the physical FT232R wiring on a custom ATmega board.
"""

from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    main_cpp = (ROOT / "src/main.cpp").read_text(encoding="utf-8")
    sources = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "src").glob("*.cpp")
    )
    adapter = (ROOT / "scripts/stage7_pi_adapter.py").read_text(
        encoding="utf-8"
    )
    sop = (ROOT / "docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md").read_text(
        encoding="utf-8"
    )
    nextion_wiring = (
        ROOT / "nextion/NX4827T043_011/ATMEGA2560_USART2_WIRING.txt"
    ).read_text(encoding="utf-8")

    assert re.search(r"\bSerial\.begin\s*\(\s*115200\s*\)", main_cpp)
    assert "NextionTransport nextion(Serial2)" in main_cpp
    assert re.search(r"NEXTION_BAUD\s+9600UL", main_cpp)
    assert "nextion.begin(NEXTION_BAUD)" in main_cpp
    assert not re.search(r"\bSerial1\s*\.", sources)
    assert not re.search(r"\bSerial3\s*\.", sources)

    assert "I_APPROVE_USB_SERIAL_READONLY" in adapter
    assert "exclusive=True" in adapter
    assert "port_obj.dtr = False" in adapter
    assert "port_obj.rts = False" in adapter
    assert '"^/dev/(?:serial/by-id/' in adapter
    assert "ttyAMA" not in adapter
    assert "port_obj.write(" not in adapter
    assert "G0" in sop and "G2" in sop and "G3" in sop
    assert "G2 dan G3 BELUM DIIZINKAN" in sop
    assert "physical MCU pin 12 = PH0 / RXD2" in nextion_wiring
    assert "physical MCU pin 13 = PH1 / TXD2" in nextion_wiring
    print("STAGE7_USB_SERIAL0_NEXTION_SERIAL2_CONTRACT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
