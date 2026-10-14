"""Shared bounded newline framing for USB readers (no hardware I/O)."""

from __future__ import annotations

from stage7_bridge import FrameError, MAX_LINE_BYTES, decode_line


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
            except FrameError:
                yield {"event": "TRANSPORT_ERROR", "reason": "malformed_json"}
        if framer.oversized_lines != before:
            yield {"event": "TRANSPORT_ERROR", "reason": "oversized_line"}
        if not chunk:
            yield None
