#!/usr/bin/env python3
"""Build-only safety contract for isolated Serial0/Nextion diagnostic."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = (ROOT / "scripts/platformio_uart_nextion_diag.ini").read_text(encoding="utf8")
SRC = (ROOT / "diagnostics/uart_nextion/src/main.cpp").read_text(encoding="utf8")


def run():
    assert "src_dir = diagnostics/uart_nextion/src" in CFG
    assert "-DUSART_BOOT_DIAG_ONLY=1" in CFG
    assert "upload_port" not in CFG and "upload_protocol" not in CFG
    assert 'Serial.begin(115200);' in SRC
    assert 'Serial2.begin(9600);' in SRC
    assert 'F("page pHome")' in SRC
    assert 'F("sendme")' in SRC
    assert "NEXTION_PAGE_REPLY" in SRC
    assert "replyParserState == 5" in SRC
    assert "static constexpr uint32_t HOME_FIRST_MS = 3200UL" in SRC
    assert "static constexpr uint32_t HEARTBEAT_MS = 5000UL" in SRC
    assert 'strcmp(command, "#status")' in SRC
    assert 'stage\\":\\"STATUS_REPLY' in SRC or "STATUS_REPLY" in SRC
    assert "digitalWrite(VALVE_IN3, LOW)" in SRC
    assert "digitalWrite(VALVE_IN4, LOW)" in SRC
    assert SRC.index("digitalWrite(VALVE_IN3, LOW)") < SRC.index(
        "pinMode(VALVE_IN3, OUTPUT)")
    for forbidden in (
        "Wire.", "EEPROM.", "setCollecting", "setPurging",
        "digitalWrite(VALVE_IN3, HIGH)", "digitalWrite(VALVE_IN4, HIGH)",
        "Serial1.", "Serial3.", "#start", "#scan", "#rf30:",
        "analogRead", "SPI.", "system(", "avrdude",
    ):
        assert forbidden not in SRC, forbidden
    print("UART_NEXTION_DIAGNOSTIC_BUILD_ONLY_SAFETY_CONTRACT_PASS")


if __name__ == "__main__":
    run()
