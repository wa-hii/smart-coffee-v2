#!/usr/bin/env python3
"""Pure offline Intel HEX parser negative/positive checks."""
from __future__ import annotations

from pathlib import Path
import tempfile

from svm30_b6_verify_readback import parse_intel_hex


def ihex(kind: int, addr: int, payload: bytes) -> str:
    body=bytes([len(payload),addr>>8,addr&255,kind])+payload
    return ":"+(body+bytes([(-sum(body)) & 0xff])).hex().upper()


def test() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        p=Path(temporary)/"fake.hex"
        a=ihex(0,0,b"\x01\x02")
        b=ihex(1,0,b"")
        p.write_text(a+"\n"+b+"\n",encoding="ascii")
        result=parse_intel_hex(p,2)
        assert result["data_bytes_non_ff"]==2
        assert result["address_coverage_bytes"]==2
        with_suffix=parse_intel_hex(p,5,allow_trimmed_erased_suffix=True)
        assert with_suffix["unrepresented_suffix_bytes"]==3
        assert with_suffix["unrepresented_suffix_assumed_ff_not_measured"]
        corrupt=a[:-2]+"00"
        for source,reason in (
            (a+"\n", "NO_EOF"),
            (corrupt+"\n"+b+"\n", "CHECKSUM"),
            (a+"\n"+a+"\n"+b+"\n","DUPLICATE"),
            (a+"\n"+b+"\n"+a+"\n","AFTER_EOF"),
        ):
            p.write_text(source,encoding="ascii")
            try:
                parse_intel_hex(p,2)
            except ValueError:
                pass
            else:
                raise AssertionError(f"INVALID_IHEX_ACCEPTED:{reason}")
    print("B6_IHEX_VERIFICATION_UNIT_QA_PASS")


if __name__=="__main__":
    test()
