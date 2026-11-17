#!/usr/bin/env python3
"""Offline regression: repeat AI Test without reopening UART; no physical port."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from rf500_pi_persistent_listener import PersistentHandler
from test_rf30_pi_result_bridge import frames


def test_two_successful_sessions() -> None:
    with TemporaryDirectory() as root:
        dest = Path(root) / "recordings"
        calls = []
        def mock_predictor(csv_path: Path) -> dict:
            calls.append(csv_path.read_text(encoding="utf8").count("\n"))
            return {"roast_predicted": "light"}

        controller = PersistentHandler(predictor=mock_predictor, archive_dir=dest)
        data = frames()
        for i in range(2):
            sent = []
            for raw in data:
                command, status = controller.receive(raw)
                if command:
                    sent.append(command)
            assert sent == [b"#rf30:B1F503A9:light;"], sent
            ack = (json.dumps({"event": "AI_RESULT_ACK",
                               "token": "B1F503A9", "roast": "light"}) + "\n").encode()
            command, status = controller.receive(ack)
            assert command is None
            assert status["status"] == "MCU_ACK_CONFIRMED"
            assert controller.session.token is None
            assert controller.quarantine is False
        assert controller.seen_sessions == controller.successful_sessions == 2
        assert calls == [901, 901]  # 900 samples + one CSV header
        captures = list(dest.glob("*.ndjson"))
        manifests = list(dest.glob("*.json"))
        assert len(captures) == len(manifests) == 2
        for summary_file in manifests:
            summary = json.loads(summary_file.read_text())
            assert summary["roast_predicted"] == "light"
            assert summary["samples"] == 900
            raw = (dest / summary["capture_file"]).read_bytes()
            assert len(raw.splitlines()) == 902  # ACQ_START, 900 samples, COMPLETE
            assert not any(b"#rf30:" in line for line in raw.splitlines())
        print("RF500_PERSISTENT_TWO_CONSECUTIVE_AI_TESTS_PASS")


def test_fail_closed() -> None:
    with TemporaryDirectory() as root:
        dest = Path(root) / "recordings"
        called = []
        controller = PersistentHandler(
            predictor=lambda _: (called.append(True) or {"roast_predicted": "dark"}),
            archive_dir=dest)
        data = frames()
        # Corrupt data after ACQ_START: never allow inference/MCU TX.
        controller.receive(data[1])
        _, status = controller.receive(b"\x00\xff\n")
        assert status["status"] == "SESSION_REJECTED_NO_RESULT"
        for raw in data[2:]:
            command, status = controller.receive(raw)
            assert command is None
        assert not called and controller.successful_sessions == 0
        assert not list(dest.glob("*.ndjson"))
        # A subsequent fresh ACQ_START can recover without reopening USB.
        command, status = controller.receive(data[1])
        assert command is None and status["status"] == "CAPTURE_STARTED"
        assert controller.quarantine is False
        print("RF500_PERSISTENT_INVALID_SESSION_BLOCKS_RESULT_AND_RECOVERS_PASS")


if __name__ == "__main__":
    test_two_successful_sessions()
    test_fail_closed()
