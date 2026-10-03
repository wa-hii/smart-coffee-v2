#!/usr/bin/env python3
"""Build the NX4827T043_011 HMI from the locked 480x272 ENOSE Figma screens.

The existing, Editor-generated HMI is used as the model-valid container.  This
tool replaces its per-page picture resources, moves the existing dynamic
components/hotspots onto the locked Figma geometry, and expands pTake with the
separate previous/next and minus/plus hit targets required by the UI.

The patcher is intentionally idempotent: an already-generated final HMI can be
used as the next baseline without duplicating cloned components or growing page
blobs when their size is unchanged.

It deliberately does not modify the Figma source design.
"""
from __future__ import annotations

import argparse
import io
import struct
from pathlib import Path

from PIL import Image

ENTRY_SIZE = 28
ENTRY_FMT = "<16sIIBBBB"
BACKUP_DIR_OFFSET = 0x00080000
PCH_BASE = 0x38
PCH_SIZE = 12
EXPECTED_MODEL_CRC = 0xCA296EB1  # NX4827T043_011 from the Editor-generated container

REQUIRED_COMPONENTS = {
    0: set(),
    1: {"mTest", "mData", "mSet", "mHist", "mCal", "mExit"},
    2: {
        "tRoast", "tOrigin", "tBatch", "tCycles", "tFile", "tStat",
        "mRoast", "mRNext", "mOrigin", "mOrgNxt", "mBatch", "mBInc0",
        "mBack", "mStart",
    },
    3: {
        "tSample", "tRemain", "tTemp", "tHum", "tPhase", "tCycle",
        "tSensors", "jCycle", "mPause", "mCancel",
    },
    4: {"tFile", "tDone", "mNew", "mHome"},
    5: {"tTestId", "tMode", "tAtmega", "tPi", "tSensors", "mBack", "mStart"},
    6: {
        "tTestId", "tPi", "jAI", "tStep1", "tStep2", "tStep3", "tStep4",
        "tEta", "mCancel",
    },
    7: {
        "tRoast", "tRConf", "tOrigin", "tOConf", "jLight", "jMedium",
        "jDark", "tLight", "tMedium", "tDark", "mSave", "mHome",
    },
    8: {"tSensors", "tChamber", "tPump", "tBase", "mStart", "mHome"},
    9: {"tWifi", "tDuration", "tBright", "tLang", "tDevId", "tFw", "mReset", "mHome"},
    10: {"tH0", "tH1", "tH2", "tH3", "mClear", "mHome"},
    11: {"tAlert", "tMsg", "tAction", "mRetry", "mHome"},
}

REQUIRED_EVENTS = {
    "EVT:AI_CANCEL", "EVT:AI_START", "EVT:BATCH_DEC", "EVT:BATCH_INC",
    "EVT:CAL_START", "EVT:DATA_CANCEL", "EVT:DATA_PAUSE", "EVT:DATA_START",
    "EVT:EXIT", "EVT:HISTORY", "EVT:HISTORY_CLEAR", "EVT:HOME",
    "EVT:NEW_BATCH", "EVT:ORIGIN_NEXT", "EVT:ORIGIN_PREV", "EVT:RESET",
    "EVT:RESULT_SAVE", "EVT:RETRY", "EVT:ROAST_NEXT", "EVT:ROAST_PREV",
    "EVT:SETTINGS", "EVT:TAKE_OPEN", "EVT:TEST_START",
}


def _make_table():
    table = []
    for i in range(256):
        crc = i << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7 if crc & 0x80000000 else crc << 1) & 0xFFFFFFFF
        table.append(crc)
    return table


TAB256 = _make_table()


def crc32_bytewise(seed: int, data: bytes) -> int:
    r = seed & 0xFFFFFFFF
    for b in data:
        r ^= b
        for _ in range(4):
            r = ((r << 8) & 0xFFFFFFFF) ^ TAB256[(r >> 24) & 0xFF]
    return r & 0xFFFFFFFF


def crc32_t(seed: int, data: bytes) -> int:
    if len(data) % 4:
        return seed & 0xFFFFFFFF
    r = seed & 0xFFFFFFFF
    for i in range(0, len(data), 4):
        r ^= int.from_bytes(data[i:i+4], "little")
        for _ in range(4):
            r = ((r << 8) & 0xFFFFFFFF) ^ TAB256[(r >> 24) & 0xFF]
    return r & 0xFFFFFFFF


def directory_checksum(directory: bytes) -> int:
    return crc32_t(0xFFFFFFFF, directory + b"ADEC")


def page_crc(blob: bytes) -> int:
    crc = crc32_bytewise(0xFFFFFFFF, blob[4:])
    crc = crc32_bytewise(crc, blob[4:8])
    crc = crc32_bytewise(crc, blob[0x0C:0x10])
    crc = crc32_bytewise(crc, blob[0x14:0x15])
    crc = crc32_bytewise(crc, blob[0x15:0x16])
    return crc


def rgb565(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def entries(raw: bytes):
    count = struct.unpack_from("<I", raw, 0)[0]
    for i in range(count):
        off = 4 + i * ENTRY_SIZE
        name_raw, start, size, deleted, t0, t1, t2 = struct.unpack_from(ENTRY_FMT, raw, off)
        name = name_raw.split(b"\0", 1)[0].decode("latin1")
        yield i, off, name, start, size, deleted, (t0, t1, t2)


def find_entry(raw: bytes, name: str):
    for item in entries(raw):
        if item[2] == name and not item[5]:
            return item
    raise KeyError(name)


def get_page(raw: bytes, page_id: int) -> bytes:
    _, _, _, start, size, _, _ = find_entry(raw, f"{page_id}.pa")
    return raw[start:start+size]


def rewrite_page(raw: bytes, page_id: int, pa: bytes) -> bytes:
    idx, off, _, old_start, old_size, _, tails = find_entry(raw, f"{page_id}.pa")
    out = bytearray(raw)
    if len(pa) == old_size:
        # Keep the file stable on repeat builds whenever the generated page
        # has the same size as the current live page.
        start = old_start
        out[start:start + old_size] = pa
    else:
        # Structural changes (for example the first creation of pTake's
        # independent selector hotspots) require a new page payload.
        start = len(out)
        out.extend(pa)
    struct.pack_into(
        ENTRY_FMT, out, off,
        f"{page_id}.pa".encode().ljust(16, b"\0"), start, len(pa), 0,
        tails[0], tails[1], tails[2],
    )
    out[BACKUP_DIR_OFFSET+off:BACKUP_DIR_OFFSET+off+ENTRY_SIZE] = out[off:off+ENTRY_SIZE]
    count = struct.unpack_from("<I", out, 0)[0]
    dir_end = 4 + count * ENTRY_SIZE
    csum = directory_checksum(bytes(out[:dir_end]))
    struct.pack_into("<I", out, dir_end, csum)
    struct.pack_into("<I", out, BACKUP_DIR_OFFSET + dir_end, csum)
    return bytes(out)


def component_records(pa: bytes):
    n = struct.unpack_from("<I", pa, 12)[0]
    for i in range(n):
        start, size, third = struct.unpack_from("<III", pa, PCH_BASE + i * PCH_SIZE)
        physical = PCH_BASE + start
        yield i, start, size, third, physical, pa[physical:physical+size]


def _find_attr(rec: bytes | bytearray, name: str):
    key = name.encode().ljust(8, b"\0")[:8]
    for off in range(0, len(rec) - 20):
        tb = rec[off]
        if (tb & 0xF0) != 0x10 or rec[off+1:off+4] != b"\0\0\0":
            continue
        if rec[off+4:off+12] == key and rec[off+12:off+20] == b"\0" * 8:
            return off + 20, tb & 0x0F
    return None


def attr_bytes(rec: bytes, name: str):
    found = _find_attr(rec, name)
    if not found:
        return None
    off, width = found
    return rec[off:off+width]


def component_name(rec: bytes) -> str | None:
    value = attr_bytes(rec, "objname")
    if value is None:
        return None
    return value.split(b"\0", 1)[0].decode("latin1", "replace")


def find_component(pa: bytes, name: str):
    for item in component_records(pa):
        if component_name(item[5]) == name:
            return item
    raise KeyError(f"component {name!r}")


def _put_attr(rec: bytearray, name: str, value):
    found = _find_attr(rec, name)
    if not found:
        return False
    off, width = found
    if isinstance(value, str):
        buf = value.encode("ascii", "replace")[:width].ljust(width, b"\0")
    elif isinstance(value, (bytes, bytearray)):
        buf = bytes(value)[:width].ljust(width, b"\0")
    else:
        buf = int(value).to_bytes(width, "little", signed=False)
    rec[off:off+width] = buf
    return True


def patch_record(rec: bytes, *, x=None, y=None, w=None, h=None, name=None,
                 comp_id=None, font=None, bco=None, pco=None, sta=None,
                 txt_maxl=None, xcen=None, ycen=None, event_replace=None):
    out = bytearray(rec)
    if name is not None:
        _put_attr(out, "objname", name)
    if comp_id is not None:
        _put_attr(out, "id", comp_id)
    if x is not None: _put_attr(out, "x", x)
    if y is not None: _put_attr(out, "y", y)
    if w is not None: _put_attr(out, "w", w)
    if h is not None: _put_attr(out, "h", h)
    if x is not None and w is not None: _put_attr(out, "endx", x + w - 1)
    if y is not None and h is not None: _put_attr(out, "endy", y + h - 1)
    if font is not None: _put_attr(out, "font", font)
    if bco is not None: _put_attr(out, "bco", bco)
    if pco is not None: _put_attr(out, "pco", pco)
    if sta is not None: _put_attr(out, "sta", sta)
    if txt_maxl is not None: _put_attr(out, "txt_maxl", txt_maxl)
    if xcen is not None: _put_attr(out, "xcen", xcen)
    if ycen is not None: _put_attr(out, "ycen", ycen)
    if event_replace:
        old, new = event_replace
        old_b, new_b = old.encode(), new.encode()
        if len(old_b) != len(new_b):
            raise ValueError(f"fixed-size event replacement differs in length: {old!r} -> {new!r}")
        current = bytes(out)
        if new_b not in current:
            pos = current.find(old_b)
            if pos < 0:
                raise ValueError(f"event {old!r} not found")
            out[pos:pos+len(old_b)] = new_b
    return bytes(out)


def replace_component(pa: bytes, name: str, **kwargs) -> bytes:
    _, _, size, _, physical, rec = find_component(pa, name)
    patched = patch_record(rec, **kwargs)
    if len(patched) != size:
        raise AssertionError("in-place component patch changed record size")
    out = bytearray(pa)
    out[physical:physical+size] = patched
    struct.pack_into("<I", out, 0, page_crc(bytes(out)))
    return bytes(out)


def clone_component(pa: bytes, source_name: str, new_name: str, **kwargs) -> bytes:
    _, _, _, _, _, source_rec = find_component(pa, source_name)
    n = struct.unpack_from("<I", pa, 12)[0]
    rec = patch_record(source_rec, name=new_name, comp_id=n, **kwargs)
    # New PCH inserted after existing PCH rows. All existing relative starts
    # shift by 12 bytes because the data section moves by one PCH row.
    header = bytearray(pa[:PCH_BASE])
    pchs = bytearray()
    last_start = last_size = 0
    for i in range(n):
        s, sz, third = struct.unpack_from("<III", pa, PCH_BASE + i * PCH_SIZE)
        pchs += struct.pack("<III", s + PCH_SIZE, sz, third)
        last_start, last_size = s, sz
    pchs += struct.pack("<III", last_start + last_size + PCH_SIZE, len(rec), 0)
    data = pa[PCH_BASE + n * PCH_SIZE:]
    out = bytearray(header + pchs + data + rec)
    struct.pack_into("<I", out, 12, n + 1)
    struct.pack_into("<I", out, 4, len(out))
    struct.pack_into("<I", out, 0, page_crc(bytes(out)))
    return bytes(out)


def upsert_clone(pa: bytes, source_name: str, new_name: str, **kwargs) -> bytes:
    """Patch an existing cloned component, or create it on the first build."""
    try:
        find_component(pa, new_name)
    except KeyError:
        return clone_component(pa, source_name, new_name, **kwargs)
    return replace_component(pa, new_name, **kwargs)


def remove_components(pa: bytes, names: set[str]) -> bytes:
    """Remove components and rebuild the page's PCH table.

    The page object itself is also represented as component record 0 and is
    preserved. This is used for legacy dynamic objects that are not present in
    the locked Figma design. Removing them is preferable to moving them outside
    the canvas because Nextion Editor validates every component position.
    """
    kept = []
    for _, _, _, third, _, rec in component_records(pa):
        if component_name(rec) not in names:
            kept.append((third, rec))

    header = bytearray(pa[:PCH_BASE])
    pchs = bytearray()
    data = bytearray()
    relative_start = len(kept) * PCH_SIZE

    for new_id, (third, rec) in enumerate(kept):
        patched = patch_record(rec, comp_id=new_id)
        pchs += struct.pack("<III", relative_start + len(data), len(patched), third)
        data += patched

    out = bytearray(header + pchs + data)
    struct.pack_into("<I", out, 12, len(kept))
    struct.pack_into("<I", out, 4, len(out))
    struct.pack_into("<I", out, 0, page_crc(bytes(out)))
    return bytes(out)


def replace_picture(raw: bytes, picture_id: int, png: Path) -> bytes:
    im = Image.open(png).convert("RGB")
    if im.size != (480, 272):
        raise ValueError(f"{png}: expected 480x272, got {im.size}")
    out = bytearray(raw)

    # Source bitmap (.is): preserve the Editor resource header, replace only
    # the embedded BMP.  Pillow emits the same 54-byte 24-bit BMP header size.
    _, _, _, start, size, _, _ = find_entry(bytes(out), f"{picture_id}.is")
    bio = io.BytesIO()
    im.save(bio, "BMP")
    bmp = bio.getvalue()
    payload = b"bmp" + bmp
    if len(payload) != size - 24:
        raise ValueError(f"{picture_id}.is payload size {len(payload)} != expected {size-24}")
    out[start+24:start+size] = payload

    # Device-encoded bitmap (.i): 480*272 little-endian RGB565, top-down.
    _, _, _, start, size, _, _ = find_entry(bytes(out), f"{picture_id}.i")
    px = bytearray()
    for r, g, b in im.getdata():
        px += struct.pack("<H", rgb565((r, g, b)))
    if len(px) != size - 24:
        raise ValueError(f"{picture_id}.i payload size {len(px)} != expected {size-24}")
    out[start+24:start+size] = px
    return bytes(out)


GRAY = rgb565((217,217,217))
WHITE = rgb565((255,255,255))
BLACK = rgb565((0,0,0))
PURPLE = rgb565((97,85,245))
GREEN = rgb565((52,199,94))
YELLOW = rgb565((255,204,0))
PALE_GREEN = rgb565((222,255,230))
RED = rgb565((255,56,60))
TEAL = rgb565((0,200,179))
DONE_MAGENTA = rgb565((203,48,224))
TEST_MINT = rgb565((191,242,236))
TEST_STATUS_GREEN = rgb565((179,241,194))


def text_style(pa: bytes, name: str, x, y, w, h, *, bg=WHITE, fg=BLACK,
               font=0, maxl=48, xcen=1, ycen=1):
    return replace_component(pa, name, x=x, y=y, w=w, h=h, sta=1, bco=bg,
                             pco=fg, font=font, txt_maxl=maxl, xcen=xcen, ycen=ycen)


def build_pages(raw: bytes) -> bytes:
    # pSplash — the final Figma screen intentionally has no MCU status chips
    # or progress bar. Remove the legacy objects completely. Moving them to the
    # canvas boundary causes "Position Invalid" in Nextion Editor.
    pa = get_page(raw, 0)
    pa = remove_components(pa, {"tAtmega", "tPi", "tHmi", "jInit"})
    raw = rewrite_page(raw, 0, pa)

    # pHome — hotspot geometry is the fixed Figma button geometry.
    pa = get_page(raw, 1)
    home = {
        "mTest": (245,48,216,27), "mData": (245,84,216,27),
        "mSet": (245,119,216,27), "mHist": (245,155,216,27),
        "mCal": (245,190,216,27), "mExit": (245,226,216,27),
    }
    for n,(x,y,w,h) in home.items(): pa = replace_component(pa,n,x=x,y=y,w=w,h=h)
    raw = rewrite_page(raw,1,pa)

    # pTake — fixed visual fields + six independent selector hit targets.
    pa = get_page(raw,2)
    pa = text_style(pa,"tRoast",70,68,119,31,bg=PURPLE,fg=WHITE,font=1,maxl=12)
    pa = text_style(pa,"tOrigin",290,68,119,31,bg=PURPLE,fg=WHITE,font=1,maxl=16)
    pa = text_style(pa,"tBatch",70,125,119,31,bg=GRAY,fg=BLACK,font=1,maxl=8)
    pa = text_style(pa,"tCycles",249,125,203,31,bg=GRAY,fg=BLACK,font=1,maxl=8)
    pa = text_style(pa,"tFile",161,165,292,16,bg=GRAY,fg=BLACK,font=0,maxl=48)
    pa = replace_component(pa,"mBack",x=22,y=209,w=204,h=28)
    pa = replace_component(pa,"mStart",x=254,y=209,w=204,h=28)
    # Preserve originals for cloning before converting them to the previous/decrement actions.
    pa = upsert_clone(pa,"mRoast","mRNext",x=195,y=68,w=35,h=31)
    pa = upsert_clone(pa,"mOrigin","mOrgNxt",x=415,y=68,w=35,h=31)
    pa = upsert_clone(pa,"mBatch","mBInc0",x=195,y=119,w=35,h=37)
    pa = upsert_clone(pa,"tFile","tStat",x=22,y=185,w=436,h=22,
                      bco=YELLOW,pco=GREEN,sta=1,font=0,txt_maxl=48,xcen=1,ycen=1)
    pa = replace_component(pa,"mRoast",x=29,y=68,w=35,h=31,event_replace=("EVT:ROAST_NEXT","EVT:ROAST_PREV"))
    pa = replace_component(pa,"mOrigin",x=249,y=68,w=35,h=31,event_replace=("EVT:ORIGIN_NEXT","EVT:ORIGIN_PREV"))
    pa = replace_component(pa,"mBatch",x=29,y=119,w=35,h=37,event_replace=("EVT:BATCH_INC","EVT:BATCH_DEC"))
    raw = rewrite_page(raw,2,pa)

    # pDataRun
    pa = get_page(raw,3)
    pa = text_style(pa,"tSample",22,48,436,28,bg=PURPLE,fg=WHITE,font=0,maxl=32)
    pa = text_style(pa,"tRemain",27,95,162,14,bg=WHITE,fg=GREEN,font=0,maxl=12,xcen=0)
    pa = text_style(pa,"tTemp",247,95,162,14,bg=WHITE,fg=GREEN,font=0,maxl=12,xcen=0)
    pa = text_style(pa,"tHum",27,137,162,14,bg=WHITE,fg=GREEN,font=0,maxl=12,xcen=0)
    pa = text_style(pa,"tPhase",247,137,162,14,bg=WHITE,fg=GREEN,font=0,maxl=16,xcen=0)
    pa = text_style(pa,"tCycle",163,179,153,10,bg=PURPLE,fg=WHITE,font=0,maxl=20)
    pa = text_style(pa,"tSensors",0,0,1,1,bg=GRAY,fg=GRAY,font=0,maxl=24)
    pa = replace_component(pa,"jCycle",x=28,y=193,w=425,h=6)
    pa = replace_component(pa,"mPause",x=22,y=209,w=204,h=28)
    pa = replace_component(pa,"mCancel",x=254,y=209,w=204,h=28)
    raw = rewrite_page(raw,3,pa)

    # pDataDone
    pa = get_page(raw,4)
    pa = text_style(pa,"tFile",149,132,182,21,bg=rgb565((234,89,110)),fg=WHITE,font=1,maxl=48)
    pa = upsert_clone(pa,"tFile","tDone",x=102,y=49,w=277,h=31,
                      bco=DONE_MAGENTA,pco=WHITE,sta=1,font=0,txt_maxl=32,xcen=1,ycen=1)
    pa = replace_component(pa,"mNew",x=22,y=209,w=204,h=28)
    pa = replace_component(pa,"mHome",x=254,y=209,w=204,h=28)
    raw = rewrite_page(raw,4,pa)

    # pTest
    pa = get_page(raw,5)
    pa = text_style(pa,"tTestId",22,137,208,23,bg=WHITE,fg=rgb565((0,136,255)),font=0,maxl=24)
    pa = text_style(pa,"tMode",250,137,208,23,bg=WHITE,fg=GREEN,font=0,maxl=24)
    for n,x in [("tAtmega",79),("tPi",191),("tSensors",303)]:
        pa = text_style(pa,n,x,173,99,20,bg=PALE_GREEN,fg=GREEN,font=0,maxl=20)
    pa = replace_component(pa,"mBack",x=22,y=209,w=204,h=28)
    pa = replace_component(pa,"mStart",x=254,y=209,w=204,h=28)
    raw = rewrite_page(raw,5,pa)

    # pTestRun — exact exported Figma geometry is already close to the baseline;
    # align the fields and the single cancel target to the fixed frame.
    pa = get_page(raw,6)
    pa = text_style(pa,"tTestId",28,48,350,28,bg=TEST_MINT,fg=WHITE,font=0,maxl=24,xcen=0)
    pa = text_style(pa,"tPi",380,55,62,14,bg=TEST_STATUS_GREEN,fg=GREEN,font=0,maxl=18)
    for n,y in [("tStep1",102),("tStep2",125),("tStep3",148)]:
        pa = text_style(pa,n,380,y,73,21,bg=WHITE,fg=GREEN,font=0,maxl=24,xcen=2)
    pa = upsert_clone(pa,"tStep3","tStep4",x=380,y=171,w=73,h=21,
                      bco=WHITE,pco=GREEN,sta=1,font=0,txt_maxl=24,
                      xcen=2,ycen=1)
    pa = text_style(pa,"tEta",138,192,204,17,bg=GRAY,fg=BLACK,font=0,maxl=32)
    pa = replace_component(pa,"jAI",x=28,y=76,w=425,h=6)
    pa = replace_component(pa,"mCancel",x=138,y=209,w=204,h=28)
    raw = rewrite_page(raw,6,pa)

    # pResult
    pa = get_page(raw,7)
    pa = text_style(pa,"tRoast",27,66,162,24,bg=PURPLE,fg=WHITE,font=1,maxl=18,xcen=0)
    pa = text_style(pa,"tRConf",27,94,147,15,bg=PURPLE,fg=GREEN,font=0,maxl=24,xcen=0)
    pa = text_style(pa,"tOrigin",247,66,200,24,bg=WHITE,fg=BLACK,font=0,maxl=36,xcen=0)
    pa = text_style(pa,"tOConf",247,94,147,15,bg=WHITE,fg=GREEN,font=0,maxl=24,xcen=0)
    for n,y in [("tLight",148),("tMedium",164),("tDark",180)]:
        pa = text_style(pa,n,409,y,49,10,bg=GRAY,fg=BLACK,font=0,maxl=12,xcen=2)
    for n,y in [("jLight",150),("jMedium",166),("jDark",182)]:
        pa = replace_component(pa,n,x=85,y=y,w=324,h=6)
    pa = replace_component(pa,"mSave",x=22,y=209,w=204,h=28)
    pa = replace_component(pa,"mHome",x=254,y=209,w=204,h=28)
    raw = rewrite_page(raw,7,pa)

    # pCal
    pa = get_page(raw,8)
    pa = text_style(pa,"tSensors",371,98,80,11,bg=WHITE,fg=GREEN,font=0,maxl=20,xcen=2)
    pa = text_style(pa,"tChamber",350,123,101,11,bg=WHITE,fg=GREEN,font=0,maxl=24,xcen=2)
    pa = text_style(pa,"tPump",407,149,44,11,bg=WHITE,fg=GREEN,font=0,maxl=12,xcen=2)
    pa = text_style(pa,"tBase",407,173,44,11,bg=WHITE,fg=GREEN,font=0,maxl=16,xcen=2)
    pa = replace_component(pa,"mStart",x=22,y=209,w=204,h=28)
    pa = replace_component(pa,"mHome",x=254,y=209,w=204,h=28)
    raw = rewrite_page(raw,8,pa)

    # pSettings
    pa = get_page(raw,9)
    fields={
        "tWifi":(330,49,121,17), "tDuration":(330,71,121,18),
        "tBright":(385,96,66,12), "tLang":(360,115,91,19),
        "tDevId":(340,137,111,19), "tFw":(370,160,81,19),
    }
    for n,(x,y,w,h) in fields.items():
        pa = text_style(pa,n,x,y,w,h,bg=PURPLE,fg=WHITE,font=0,maxl=32,xcen=2)
    pa = replace_component(pa,"mReset",x=22,y=209,w=204,h=28)
    pa = replace_component(pa,"mHome",x=254,y=209,w=204,h=28)
    raw = rewrite_page(raw,9,pa)

    # pHistory
    pa = get_page(raw,10)
    for n,y in [("tH0",48),("tH1",85),("tH2",122),("tH3",159)]:
        pa = text_style(pa,n,30,y,418,31,bg=WHITE,fg=BLACK,font=0,maxl=64)
    pa = replace_component(pa,"mClear",x=22,y=209,w=204,h=28)
    pa = replace_component(pa,"mHome",x=254,y=209,w=204,h=28)
    raw = rewrite_page(raw,10,pa)

    # pAlert
    pa = get_page(raw,11)
    alert_bg = rgb565((235,120,120))
    pa = text_style(pa,"tAlert",213,56,225,24,bg=alert_bg,fg=BLACK,font=0,maxl=32,xcen=0)
    pa = text_style(pa,"tMsg",30,83,420,19,bg=alert_bg,fg=BLACK,font=0,maxl=64)
    pa = text_style(pa,"tAction",30,137,420,48,bg=YELLOW,fg=BLACK,font=0,maxl=80,xcen=0,ycen=0)
    pa = replace_component(pa,"mRetry",x=22,y=209,w=204,h=28)
    pa = replace_component(pa,"mHome",x=254,y=209,w=204,h=28)
    raw = rewrite_page(raw,11,pa)
    return raw


def verify(raw: bytes):
    count = struct.unpack_from("<I", raw, 0)[0]
    primary = raw[:4 + count * ENTRY_SIZE]
    backup = raw[BACKUP_DIR_OFFSET:BACKUP_DIR_OFFSET + len(primary)]
    if primary != backup:
        raise AssertionError("backup directory mismatch")
    dir_end = 4 + count * ENTRY_SIZE
    stored = struct.unpack_from("<I", raw, dir_end)[0]
    if stored != directory_checksum(primary):
        raise AssertionError("directory checksum mismatch")
    _, _, _, main_start, main_size, _, _ = find_entry(raw, "main.HMI")
    main = raw[main_start:main_start + main_size]
    model_crc = struct.unpack_from("<I", main, 16)[0]
    if model_crc != EXPECTED_MODEL_CRC:
        raise AssertionError(
            f"unexpected display model CRC 0x{model_crc:08x}; "
            f"expected NX4827T043_011 CRC 0x{EXPECTED_MODEL_CRC:08x}"
        )

    pages=[]
    for pid in range(12):
        pa=get_page(raw,pid)
        if struct.unpack_from("<I",pa,0)[0] != page_crc(pa):
            raise AssertionError(f"page {pid} CRC mismatch")
        names = {component_name(rec) for *_, rec in component_records(pa)}
        missing = REQUIRED_COMPONENTS[pid] - names
        if missing:
            raise AssertionError(f"page {pid} missing components: {sorted(missing)}")
        for *_, rec in component_records(pa):
            attrs = {key: attr_bytes(rec, key) for key in ("x", "y", "w", "h")}
            if not all(value is not None for value in attrs.values()):
                continue
            values = {
                key: int.from_bytes(value, "little")
                for key, value in attrs.items()
            }
            if (
                values["w"] < 1
                or values["h"] < 1
                or values["x"] + values["w"] > 480
                or values["y"] + values["h"] > 272
            ):
                raise AssertionError(
                    f"page {pid} component {component_name(rec)!r} "
                    f"position invalid: {values}"
                )
        pages.append((pid, pa[24:40].split(b"\0",1)[0].decode("ascii"), struct.unpack_from("<I",pa,12)[0]))

    present_events = {
        match.decode("ascii")
        for match in __import__("re").findall(rb"EVT:[A-Z_]+", raw)
    }
    missing_events = REQUIRED_EVENTS - present_events
    if missing_events:
        raise AssertionError(f"missing HMI events: {sorted(missing_events)}")

    return {
        "model_crc": f"0x{model_crc:08x}",
        "pages": pages,
        "events": len(present_events),
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--baseline",type=Path,required=True)
    ap.add_argument("--images",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    raw=args.baseline.read_bytes()
    names=["00_Splash","01_Home","02_TakeData","03_DataRun","04_DataDone","05_StartTest","06_TestRun","07_TestResult","08_Calibration","09_Settings","10_History","11_Alert"]
    for pid,name in enumerate(names):
        raw=replace_picture(raw,pid,args.images/f"{name}.png")
    raw=build_pages(raw)
    qa=verify(raw)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(raw)
    print(f"wrote {args.output} ({len(raw):,} bytes)")
    print("qa:", qa)


if __name__ == "__main__":
    main()
