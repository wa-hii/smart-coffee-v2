"""Tahap 7 protocol/state negative tests. No real ports, no model fitting."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from stage7_bridge import (
    ADC_COLS, FrameError, LegacySessionBridge, V1SequenceGuard,
    decode_line, replay_csv, validate_v1_envelope,
)


def event(name: str, **data) -> str:
    return json.dumps({"event": name, **data})


def start(mode="ai_test", **fields):
    return event("ACQ_START", mode=mode, phase="purging", cycle=1,
                 cycles_total=5, purge_s=25, collect_s=5, **fields)


def sensor(cycle=1, phase="purging", sample_idx=1, timestamp=1000):
    return json.dumps({
        "cycle": cycle, "phase": phase, "sample_idx": sample_idx,
        "timestamp": timestamp,
        **{col: 1000+i for i, col in enumerate(ADC_COLS)},
    })


def fail(action, phrase):
    try:
        action()
    except (FrameError, ValueError) as err:
        assert phrase in str(err), str(err)
    else:
        raise AssertionError("Expected failure " + phrase)


def fixture_bridge(collect_samples=5, pause=False):
    # Protocol fixture only, NOT a synthetic dataset for model training.
    bridge = LegacySessionBridge(session_factory=lambda: "stage7fixture001")
    bridge.feed(start())
    ts = 0
    for cycle in range(1, 6):
        for phase, n in (("purging", 25), ("collecting", collect_samples)):
            if not (cycle == 1 and phase == "purging"):
                bridge.feed(event("PHASE_CHANGE", cycle=cycle, phase=phase))
            if pause and cycle == 1 and phase == "purging":
                bridge.feed(event("ACQ_PAUSE", phase="paused"))
                bridge.feed(event("ACQ_RESUME", phase="purging"))
            for index in range(1, n + 1):
                ts += 1000
                assert bridge.feed(sensor(
                    cycle=cycle, phase=phase,
                    sample_idx=index, timestamp=ts,
                )) == []
    assert len(bridge.feed(event(
        "ACQ_COMPLETE", cycles=5,
        total_samples=(25+collect_samples)*5,
    ))) == 1
    return bridge


def v1_message(kind="ACQ_START", seq=1, uptime=100,
               mode="ai_test", payload=None, **overrides):
    data = {
        "version": 1, "type": kind, "device_id": "enose_mcu_1",
        "session_id": "session_12345678",
        "message_seq": seq, "emitted_uptime_ms": uptime,
        "mode": mode, "payload": payload or {},
    }
    return {**data, **overrides}


def main() -> int:
    assert decode_line('{"hello":1}') == {"hello": 1}
    for raw, reason in (
        ('{"event":"A","event":"B"}', "duplicate_json_key"),
        ('{"x":NaN}', "nonfinite_json_number"),
        ('[1,2]', "frame_not_object"),
        (b"\xff", "invalid_json_or_encoding"),
        ('{"x":"' + "a"*4097 + '"}', "line_size_or_nul_invalid"),
    ):
        fail(lambda raw=raw: decode_line(raw), reason)
    msg = v1_message()
    guard = V1SequenceGuard()
    ack = guard.accept(msg)
    assert ack["type"] == "ACK" and ack["transmit_allowed"] is False
    fail(lambda: guard.accept(msg), "duplicate_stale_or_out_of_order_v1")
    assert guard.accept(v1_message(
        "SENSOR_SAMPLE", seq=2, uptime=110
    ))["ack_seq"] == 2
    fail(lambda: guard.accept(v1_message(
        "SENSOR_SAMPLE", seq=3, uptime=80
    )), "duplicate_stale_or_out_of_order_v1")
    assert guard.simulate_receive('{"bad json"')["type"] == "NACK"
    fail(lambda: guard.accept(v1_message(
        "SENSOR_SAMPLE", seq=3, uptime=120, mode="labeled_data"
    )), "mode_changed_within_session")
    guard.accept(v1_message("ACQ_COMPLETE", seq=3, uptime=120))
    fail(lambda: guard.accept(v1_message(
        "SENSOR_SAMPLE", seq=4, uptime=130
    )), "session_already_final")
    fail(lambda: V1SequenceGuard().accept(v1_message(
        "SENSOR_SAMPLE", seq=1
    )), "v1_session_must_start")
    fail(lambda: validate_v1_envelope(v1_message(
        mode="ai_test", payload={"roast_level": "light"}
    )), "ai_test_label_leakage")
    fail(lambda: validate_v1_envelope(v1_message(
        "INFERENCE_RESULT", payload={"result": "light"}
    )), "unvalidated_model_result_forbidden")
    fail(lambda: validate_v1_envelope(v1_message(
        "INFERENCE_RESULT", payload={"result": "N/A", "confidence": 0.9}
    )), "uncalibrated_confidence_forbidden")
    fail(lambda: validate_v1_envelope(v1_message(version=2)),
         "unsupported_protocol_version")

    good = fixture_bridge()
    assert good.last_final["status"] == "N/A"
    assert good.last_final["quality"] == "COMPLETE_QA"
    assert good.last_final["reason"] == "five_cycles_checked_no_approved_model"
    assert good.last_final["sensor_samples"] == 150
    assert good.last_final["nominal_150_samples"]
    assert not good.last_final["sent_to_atmega"]
    assert len([r for r in good.events if r["type"] == "SESSION_FINAL"]) == 1
    assert good.feed(event("ACQ_COMPLETE", cycles=5, total_samples=150))[0][
        "type"
    ] == "IGNORED"
    six = fixture_bridge(collect_samples=6, pause=True)
    assert six.last_final["quality"] == "COMPLETE_QA"
    assert not six.last_final["nominal_150_samples"]
    assert six.last_final["sensor_samples"] == 155

    b = LegacySessionBridge(session_factory=lambda: "session_good001")
    b.feed(start())
    b.feed(sensor())
    assert b.abort()["reason"] == "stream_disconnected"
    assert b.abort()["type"] == "IGNORED"
    assert b.last_final["status"] == "N/A"
    b.feed(start())
    assert b.timeout_if_idle(elapsed_seconds=9) is None
    timeout = b.timeout_if_idle(elapsed_seconds=10)
    assert timeout["reason"] == "host_receive_timeout"
    assert timeout["quality"] == "FAIL_CLOSED"
    assert b.timeout_if_idle(elapsed_seconds=11) is None

    b = LegacySessionBridge()
    b.feed(start())
    b.feed(sensor())
    assert b.feed(sensor())[0]["reason"] == "duplicate_or_gapped_sample_idx"
    b.feed(start())
    assert b.feed(sensor(sample_idx=2))[0]["reason"] == "duplicate_or_gapped_sample_idx"
    b.feed(start())
    assert b.feed(sensor(phase="collecting"))[0]["reason"] == (
        "out_of_order_cycle_or_phase"
    )
    b.feed(start())
    assert b.feed('{"event":"ACQ_COMPLETE","cycles":5,"total_samples":0}')[0][
        "quality"
    ] == "FAIL_CLOSED"
    b.feed(start())
    assert b.feed("NOT JSON")[0]["reason"] == "invalid_json_or_encoding"
    b.feed(start())
    assert b.feed(event("ACQ_PAUSE")) == []
    assert b.feed(sensor())[0]["reason"] == "sensor_during_pause"
    assert b.feed(start(origin="known"))[0]["reason"] == "ai_test_label_leakage"
    assert b.active is None
    b.feed(start())
    assert b.feed(start())[0]["reason"] == "new_start_preempted_incomplete"
    assert b.active is not None

    # Real historical recording, read-only; labels MUST NOT be replayed.
    actual = Path(__file__).resolve().parents[1] / "data/raw/D-GAW_B33.csv"
    if actual.exists():
        before = actual.read_bytes()
        replay = replay_csv(actual, session_factory=lambda: "realplay001")
        assert replay["bridge"]["status"] == "N/A"
        assert replay["bridge"]["quality"] == "COMPLETE_QA"
        assert replay["source_sha256"]
        assert actual.read_bytes() == before
        assert replay["bridge"]["mode"] == "ai_test"
        assert "roast_level" not in replay["bridge"]
        assert "origin" not in replay["bridge"]

    with TemporaryDirectory() as temp:
        dummy = Path(temp) / "not_sensor.csv"
        dummy.write_text("unknown\nxxx\n", encoding="utf-8")
        fail(lambda: replay_csv(dummy), "not_canonical_mq3_csv")

    print("STAGE7_BRIDGE_PROTOCOL_QA_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
