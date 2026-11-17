#!/usr/bin/env python3
"""Offline regression: repeat AI Test without reopening UART; no physical port."""
from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from rf500_pi_persistent_listener import (
    PersistentHandler, verify_bridge_compatibility,
)
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


def test_prestart_diagnostics() -> None:
    """Unexpected frames never cause a guessed session or a model TX."""
    with TemporaryDirectory() as root:
        dest = Path(root) / "recordings"
        model_calls = []
        controller = PersistentHandler(
            predictor=lambda _: model_calls.append("ILLEGAL_PREDICTION"),
            archive_dir=dest)
        trace = StringIO()
        with redirect_stdout(trace):
            controller.receive(b"\xff\x00\n")
            controller.receive(
                b'{"timestamp":1,"cycle":1,"phase":"purging","sample_idx":1}\n')
            controller.receive(
                b'{"event":"ACQ_START","mode":"ai_test","fw_build_id":"WRONG","cycles_total":30,"purge_s":25,"collect_s":5,"ai_session_token":"B1F503A9"}\n')
        assert controller.prestart_frames == 3
        assert controller.prestart_non_json == 1
        assert controller.prestart_sensor_frames == 1
        assert controller.prestart_start_rejections == 1
        assert controller.session.token is None
        assert not model_calls
        assert not list(dest.glob("*"))
        printed = trace.getvalue()
        assert "RF500_PRESTART_NONJSON_FRAME" in printed
        assert "RF500_SENSOR_FRAME_WITHOUT_ACQ_START" in printed
        assert "RF500_ACQ_START_FRAME_RECEIVED" in printed
        assert "RF500_PRESTART_FRAME_REJECTED" in printed
        # Valid next ACQ_START still opens a fresh session without serial re-open.
        command, status = controller.receive(frames()[1])
        assert command is None and status["status"] == "CAPTURE_STARTED"
        print("RF500_PERSISTENT_PRESTART_DIAGNOSTICS_FAIL_CLOSED_PASS")


def test_bridge_api_release_gate() -> None:
    # Reject a stale bridge module before opening USB, loading model or
    # running an apparently healthy but unusable listener.
    from unittest.mock import patch
    import rf500_pi_persistent_listener as app
    verify_bridge_compatibility()
    with patch.object(app.bridge_module, "__file__", "/tmp/old_bridge.py"):
        try:
            verify_bridge_compatibility()
        except RuntimeError as exc:
            assert "RF30_BRIDGE_NOT_SAME_RELEASE_DIRECTORY" in str(exc)
        else:
            raise AssertionError("stale_bridge_path_not_rejected")
    class OldFeed:
        @staticmethod
        def feed(self, line):
            return None
    with patch.object(app, "HostSession", OldFeed):
        try:
            verify_bridge_compatibility()
        except RuntimeError as exc:
            assert "RF30_BRIDGE_PREDICTOR_API_MISSING" in str(exc)
        else:
            raise AssertionError("stale_bridge_api_not_rejected")
    print("RF500_PERSISTENT_PINNED_BRIDGE_API_GATE_PASS")


if __name__ == "__main__":
    test_two_successful_sessions()
    test_fail_closed()
    test_prestart_diagnostics()
    test_bridge_api_release_gate()
