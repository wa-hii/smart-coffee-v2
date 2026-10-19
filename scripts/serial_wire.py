"""Shared bounded newline framing for USB readers (no hardware I/O)."""

from __future__ import annotations

import json

from stage7_bridge import FrameError, MAX_LINE_BYTES, decode_line


def describe_invalid_line(line: bytes, err: FrameError) -> dict:
    """Structural, bounded fault context; never output the raw sensor frame.

    Python's strict decoder wraps JSONDecodeError / UnicodeDecodeError into
    FrameError. The exception cause retains the parser location, which is
    essential to distinguish truncated serial lines from invalid UTF-8.
    """
    context = {
        "detail": str(err),
        "frame_bytes": len(line),
        "ends_with_newline": line.endswith(b"\n"),
        "ends_with_brace": line.rstrip(b"\r\n \t").endswith(b"}"),
    }
    cause = err.__cause__
    if isinstance(cause, json.JSONDecodeError):
        context.update(
            fault_class="json_syntax",
            json_error_pos=cause.pos,
            json_error_message=cause.msg[:100],
            json_error_at_end=(cause.pos >= len(cause.doc.rstrip())),
        )
    elif isinstance(cause, UnicodeDecodeError):
        context.update(
            fault_class="invalid_utf8",
            invalid_byte_offset=cause.start,
            invalid_byte_reason=cause.reason[:100],
        )
    else:
        context["fault_class"] = str(err)
    return context


class SerialLineFramer:
    """Preserve partial lines across timeouts; drop an oversized line as one."""

    def __init__(self):
        self.buffer = bytearray()
        self.overflow = False
        self.oversized_lines = 0

    def feed(self, chunk: bytes) -> list[bytes]:
        if not isinstance(chunk, bytes):
            raise TypeError("serial_data_must_be_bytes")
        lines = []
        for byte in chunk:
            if self.overflow:
                if byte == 10:
                    self.overflow = False
                continue
            if len(self.buffer) >= MAX_LINE_BYTES:
                self.buffer.clear()
                self.oversized_lines += 1
                self.overflow = byte != 10
                continue
            self.buffer.append(byte)
            if byte == 10:
                lines.append(bytes(self.buffer))
                self.buffer.clear()
        return lines


def serial_json_frames(port, *, chunk_size: int = 256):
    """Read bytes, yield strict objects or synthetic TRANSPORT_ERROR markers.

    A zero-length read is a timeout, not a newline. The caller decides how
    long an active session can remain without a valid sample. Boot banners
    before a session are harmless; an error during a session must quarantine.
    """
    if not 1 <= chunk_size <= 4096:
        raise ValueError("invalid_serial_chunk_size")
    framer = SerialLineFramer()
    while True:
        chunk = port.read(chunk_size)
        before = framer.oversized_lines
        for line in framer.feed(chunk):
            if not line.lstrip().startswith(b"{"):
                # Firmware boot banner. Do not reinterpret as sensor values.
                continue
            try:
                yield decode_line(line)
            except FrameError as err:
                # Preserve the original failure class for safe diagnosis.
                # Do not log raw sensor bytes; a malformed packet cannot be
                # promoted to valid sensor rows by the receiver.
                yield {"event": "TRANSPORT_ERROR", "reason": "malformed_json",
                       **describe_invalid_line(line, err)}
        if framer.oversized_lines != before:
            yield {"event": "TRANSPORT_ERROR", "reason": "oversized_line",
                   "limit_bytes": MAX_LINE_BYTES}
        if not chunk:
            yield None
