"""PROTOTYPE: the *one* identifier -- "what format is this run of bytes".

Every walker in the tree answers this question for itself today
(``ea_disc_map.identify_head`` / ``magic_kind`` / ``renderware_section``,
``ea_module_readiness``'s per-reader probes, each module's ``containers.py``,
and ``ea_terf.identify_member`` / ``ea_big.entry_format`` in the shipped
``_formats`` packages).  This module is the shape the specification proposes
they all collapse into.

Two properties are the point, and both are corrections of a real mistake:

**1. A four-byte tag is reported forward, as text, never as a bare hex word.**
   The mapper writes ``other:43505448`` for an unrecognised head.  A reader who
   takes that hex string for a *number* spells its bytes out backwards, and one
   did: the owner's scoping study named a Midway camera-path family ``HTPC``
   when the bytes on the disc are ``CPTH``.  :func:`tag_text` renders the tag
   once, forward, beside the hex, so no consumer ever performs that conversion
   by hand.

**2. A structural rule that can fail is stated with what it checked.**
   The mapper's ``renderware_section`` accepts a RenderWare stream only when
   ``section bytes + 12 == the file`` -- a *single-section* rule -- and so
   refused all 2,708 ``.dff`` members on the two Blitz discs, which are
   ordinary multi-section RenderWare.  :func:`renderware_walk` walks the
   top-level sections instead, and reports the sequence it consumed, so the
   same members identify and the evidence travels with the identity.

Bounded by construction: :func:`identify` is handed a **head window** and a
``read(offset, length)`` callback.  It never asks for a whole member.  The
RenderWare walk is the only rule that seeks, and it reads 12 bytes per
top-level section.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import struct
from typing import Any, Callable, Dict, Optional, Tuple

#: How many bytes of a run the identifier needs.  96 covers the deepest header
#: any rule below reads (an ``SCHl`` PT header); ``ea_terf.IDENTIFY_HEAD`` is 32
#: and the efficiency review measured 96 bytes of an LZH1 member at 0.401 ms
#: against 55.954 ms for the whole member.
HEAD_BYTES = 96

#: RenderWare section ids this identifier names.  [S: RenderWare's published ids.]
RW_STRUCT = 0x01
RW_STRING = 0x02
RW_EXTENSION = 0x03
RW_TEXTURE_NATIVE = 0x15
RW_TEXTURE_DICTIONARY = 0x16
RW_CLUMP = 0x10
RW_NAMES: Dict[int, str] = {
    RW_CLUMP: "RW-CLUMP", RW_TEXTURE_DICTIONARY: "RW-TXD",
    RW_TEXTURE_NATIVE: "RW-TEXNATIVE", RW_STRUCT: "RW-STRUCT",
    RW_STRING: "RW-STRING", RW_EXTENSION: "RW-EXTENSION",
}
#: A top-level section id larger than this is not RenderWare; the published ids
#: stop well below it and a random word almost always exceeds it.
RW_MAX_ID = 0x40
RW_SECTION_HEADER = 12

#: Tags whose first four bytes name the format outright, forward.  One table,
#: one place to add a family.  Values are the index's ``format`` field.
FORWARD_MAGICS: Tuple[Tuple[bytes, str], ...] = (
    (b"TERF", "TERF"), (b"\x7fELF", "ELF"), (b"QL01", "QL01"),
    (b"BIGF", "BIGF"), (b"BIG4", "BIGF"), (b"RIFF", "RIFF"),
    (b"MMAP", "MMAP"), (b"SCHl", "SCHl"), (b"SMF\x00", "SMF"), (b"DMF\x00", "DMF"),
    (b"SHPS", "SHPS"), (b"ShpS", "SHPS"), (b"SHPM", "SHPS"), (b"SHPP", "SHPS"), (b"SHPX", "SHPS"),
    (b"MPCh", "MPCh"), (b"ABKC", "ABKC"), (b"BNKl", "BNKl"), (b"LOCH", "LOCH"),
    (b"FNTS", "FNTS"), (b"FntS", "FNTS"), (b"SKL1", "SKL1"), (b"1LKS", "SKL1"),
    (b"SEVT", "SEVT"), (b"EAGL", "EAGL"), (b"HSH1", "HSH1"), (b"PFR1", "PFR1"),
    (b"Apt ", "Apt"), (b"ASFT", "ASFT"), (b"IECS", "SCEI-HD"),
    (b"RESET\x00\x00\x00", "IOPRP"), (b"PS2D", "ICON.SYS"),
    (b"\x00\x00\x01\xb3", "MPEG-video"), (b"\x00\x00\x01\xba", "MPEG-PS"),
    (b"\x03\x12\x3c\x07", "EVT"), (b"\x03\x11\x3c\x07", "EVT"),
    (b"PK\x03\x04", "ZIP"), (b"MWo3", "MWo3"), (b"EFS ", "EFS"),
    (b"VAGp", "VAGp"), (b".HDR", "HDR-dir"),
    (b"\x01\xf0\x0f", "MidwayOBF"),
    # Midway families the Blitz modules measured after the scoping study.  The
    # study named the first of these HTPC; see the module note above.
    (b"CPTH", "CPTH"), (b"WIFF", "WIFF"), (b"RYWM", "RYWM"), (b"EKAB", "EKAB"),
    (b"Part", "Part"), (b"SEC ", "MidwaySEC"),
)

#: Tags EA and Midway store as a CPU-native ``u32``, so the bytes on a
#: little-endian disc are the name reversed.  Listed by the bytes **as they lie
#: on the disc**, with the name they spell, so the reversal is stated once here
#: instead of being re-derived (or mis-derived) by every reader.
REVERSED_MAGICS: Tuple[Tuple[bytes, str, str], ...] = (
    (b" KAP", "MidwayPAK", "PAK "),
)

TDB_MAGIC = b"DB"
TDB_MAX_TABLES = 4096


@dataclass(frozen=True)
class Identity:
    """What a run of bytes is, and the arithmetic that earned it."""

    #: The index's ``format`` column.  ``"unknown"`` is a measured answer.
    format: str
    #: ``head[:4]`` as forward text when every byte is printable, else ``None``.
    #: The one field that stops a hex word being read backwards.
    tag: Optional[str] = None
    #: ``head[:4]`` as forward hex, always present for a non-empty head.
    magic: Optional[str] = None
    #: The check that earned the identity, in words, or ``None`` for a bare
    #: magic match.  A rule that could have failed and did not belongs here.
    rule: Optional[str] = None
    #: Cheap shape facts the rule produced on the way.  Never payload.
    shape: Dict[str, Any] = field(default_factory=dict)

    def as_row(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"format": self.format}
        if self.tag is not None:
            out["tag"] = self.tag
        if self.magic is not None:
            out["magic"] = self.magic
        if self.rule is not None:
            out["rule"] = self.rule
        if self.shape:
            out["shape"] = self.shape
        return out


def tag_text(head: bytes) -> Optional[str]:
    """``head[:4]`` as forward ASCII, or ``None`` when a byte is not printable.

    This is the whole of correction 1.  ``other:43505448`` is a hex *word*; the
    reader who spelled it out got ``HTPC``.  ``tag_text`` spells it ``CPTH``,
    once, in the direction the bytes actually lie.
    """
    raw = bytes(head[:4])
    if len(raw) < 4 or not all(0x20 <= b < 0x7F for b in raw):
        return None
    return raw.decode("ascii")


def renderware_walk(head: bytes, size: int,
                    read: Optional[Callable[[int, int], bytes]] = None,
                    *, max_sections: int = 64) -> Optional[Dict[str, Any]]:
    """Walk a RenderWare binary stream's **top-level** sections.

    A RenderWare section is ``u32 id``, ``u32 body bytes``, ``u32 library
    version``; a stream is one *or more* of them laid end to end.  The mapper's
    rule was ``body + 12 == the file``, which is the one-section case, and it is
    why 2,708 ``.dff`` clumps on the Blitz discs were left as a raw magic and
    written up as "either Midway wrote a variant or the id is a coincidence".
    They are neither: a walk consumes them, in the sequence ``Clump`` then
    ``Extension``.

    Returns ``None`` when the first section is not plausibly RenderWare.
    Otherwise a dict carrying the first section's id, the library version, the
    top-level sequence, and whether the walk landed exactly on the end -- the
    evidence, travelling with the identity.

    Reads ``RW_SECTION_HEADER`` bytes per section and nothing else.
    """
    if len(head) < RW_SECTION_HEADER or size < RW_SECTION_HEADER:
        return None
    first_id, first_body, first_version = struct.unpack_from("<3I", head, 0)
    if first_id > RW_MAX_ID or first_body + RW_SECTION_HEADER > size:
        return None
    sequence: list = []
    position = 0
    end_of_last = 0
    while position + RW_SECTION_HEADER <= size and len(sequence) < max_sections:
        if position == 0:
            chunk = head[:RW_SECTION_HEADER]
        elif read is None:
            break
        else:
            chunk = read(position, RW_SECTION_HEADER)
            if len(chunk) < RW_SECTION_HEADER:
                break
        section_id, body, _version = struct.unpack_from("<3I", chunk, 0)
        body_at = position + RW_SECTION_HEADER
        if body_at + body > size:
            # The same stop rule as ``rw_txd.walk``: a section whose declared
            # body runs past the end is not yielded, so the sequence describes
            # only what the walk really consumed.
            break
        sequence.append(section_id)
        end_of_last = position = body_at + body
    return {"section_id": first_id, "library_version": "0x%08x" % first_version,
            "sections": len(sequence),
            "top_level_sequence": " ".join("0x%x" % s for s in sequence[:8]),
            "walk_consumes_the_member": bool(sequence) and end_of_last == size,
            "one_section_accounts_for_the_file": first_body + RW_SECTION_HEADER == size}


def _cpth(head: bytes, size: int) -> Optional[Dict[str, Any]]:
    """``CPTH`` camera paths: ``16 + records * 32 == the member`` [M, both Blitz discs]."""
    if len(head) < 16:
        return None
    _tag, word1, records, word3 = struct.unpack_from("<4I", head, 0)
    if 16 + records * 32 != size:
        return None
    return {"records": records, "header_word1": word1, "header_word3": word3}


def _wiff(head: bytes, size: int) -> Optional[Dict[str, Any]]:
    """``WIFF``: a **big-endian** RIFF -- ``declared + 8 == the member`` [M]."""
    if len(head) < 12:
        return None
    declared, = struct.unpack_from(">I", head, 4)
    if declared + 8 != size:
        return None
    return {"form": head[8:12].decode("latin-1")}


def _mmap(head: bytes) -> Optional[Dict[str, Any]]:
    """``MMAP`` version, dimensions and format id, from a 64-byte window.

    Offsets as ``ea_terf.parse_mmap_header`` and the mapper's ``mmap_ids``
    read them: version ``u32`` at +0x04, ``u16`` width/height at +0x28, format
    id ``u16`` at +0x2C.  Nothing below +0x30 is read, so a 4 MB texture costs
    the same as a 4 KB one.
    """
    if len(head) < 0x2E:
        return None
    version, = struct.unpack_from("<I", head, 0x04)
    width, height = struct.unpack_from("<HH", head, 0x28)
    format_id, = struct.unpack_from("<H", head, 0x2C)
    return {"version": version, "format_id": "0x%x" % format_id,
            "width": width, "height": height}


#: ``SCHl`` patch tags, as vgmstream's ``ea_schl.c`` documents them. [S]
SCHL_TAG_VERSION, SCHL_TAG_CHANNELS = 0x80, 0x82
SCHL_TAG_CODEC, SCHL_TAG_RATE, SCHL_TAG_SAMPLES, SCHL_TAG_CODEC2 = 0x83, 0x84, 0x85, 0xA0
#: EA's platform ids in an ``SCHl`` PT header. [S: vgmstream's ``ea_schl.c``.]
#: The *name* belongs here, in the identifier, so a consumer never has to keep
#: its own copy of the table: the readiness tool and the mapper each carry one
#: today and they are the same table twice.
SCHL_PLATFORMS: Dict[int, str] = {0x00: "PC", 0x01: "PSX", 0x02: "N64", 0x03: "MAC",
                                  0x04: "SAT", 0x05: "PS2", 0x06: "GC/Wii", 0x07: "Xbox",
                                  0x09: "X360", 0x0A: "PSP", 0x0E: "PS3"}


def _schl(head: bytes) -> Optional[Dict[str, Any]]:
    """Platform and codec ids of an ``SCHl`` header, from the 96-byte window alone.

    ``SCHl``, u32 block size, then ``PT`` + u16 platform (or ``GSTR``), then
    tag / width / big-endian value patches.  Nothing below the header is read:
    the efficiency review measured this window at 0.401 ms against 55.954 ms
    for the whole member.
    """
    if len(head) < 12:
        return None
    block, = struct.unpack_from("<I", head, 4)
    if block > 0x10000:
        block, = struct.unpack_from(">I", head, 4)
    if head[8:10] == b"PT":
        platform: Any = struct.unpack_from("<H", head, 10)[0]
        position = 12
    elif head[8:12] == b"GSTR":
        platform = "GSTR"
        position = 16
    else:
        return None
    tags: Dict[int, int] = {}
    limit = min(len(head), block if 12 < block <= len(head) else len(head))
    while position < limit:
        tag = head[position]
        position += 1
        if tag >= 0xFC and tag != 0xFD:
            break
        if tag == 0xFD:
            continue
        if position >= limit:
            break
        width = head[position]
        position += 1
        if width == 0 or width > 4 or position + width > limit:
            break
        tags[tag] = int.from_bytes(head[position:position + width], "big")
        position += width
    return {"platform": SCHL_PLATFORMS.get(platform, platform) if platform != "GSTR" else "GSTR",
            "platform_id": platform if platform != "GSTR" else None,
            "channels": tags.get(SCHL_TAG_CHANNELS),
            "codec": tags.get(SCHL_TAG_CODEC), "codec2": tags.get(SCHL_TAG_CODEC2),
            "rate": tags.get(SCHL_TAG_RATE)}


def _tdb(head: bytes, size: int) -> Optional[Dict[str, Any]]:
    """``DB`` + version 8 + a table count that fits.  Header only, no records."""
    if len(head) < 24 or head[:2] != TDB_MAGIC:
        return None
    version, = struct.unpack_from("<H", head, 2)
    tables, = struct.unpack_from("<I", head, 16)
    if not (0 < tables <= TDB_MAX_TABLES):
        return None
    return {"version": version, "tables": tables}


def _looks_like_text(head: bytes) -> bool:
    if not head:
        return False
    return all(32 <= b < 127 or b in (9, 10, 13) for b in head[:32])


def identify(head: bytes, size: int, *,
             read: Optional[Callable[[int, int], bytes]] = None,
             name: str = "") -> Identity:
    """Name the format of a run of ``size`` bytes whose first bytes are ``head``.

    ``read(offset, length)`` -- optional -- lets a structural rule seek inside
    the run without decoding it.  Only :func:`renderware_walk` uses it, and only
    12 bytes at a time.

    ``name`` is used for **nothing that reaches the ``format`` column**; a file
    extension is a hint, and the index records it separately so a consumer can
    see the two disagree.
    """
    if not head:
        return Identity("empty")
    magic = bytes(head[:4]).hex()
    tag = tag_text(head)

    for lying, spelled, forward in REVERSED_MAGICS:
        if head.startswith(lying):
            return Identity(spelled, tag=tag, magic=magic,
                            rule="tag stored as a little-endian u32; forward on disc %r, spells %r"
                                 % (lying.decode("latin-1"), forward))

    for prefix, fmt in FORWARD_MAGICS:
        if head.startswith(prefix):
            shape = None
            if fmt == "CPTH":
                shape = _cpth(head, size)
                if shape is None:
                    return Identity("CPTH?", tag=tag, magic=magic,
                                    rule="tag is CPTH but 16 + records * 32 != the member")
            elif fmt == "WIFF":
                shape = _wiff(head, size)
                if shape is None:
                    return Identity("WIFF?", tag=tag, magic=magic,
                                    rule="tag is WIFF but big-endian declared + 8 != the member")
            elif fmt == "MMAP":
                shape = _mmap(head)
            elif fmt == "SCHl":
                shape = _schl(head)
            rule = None
            if fmt == "CPTH":
                rule = "16 + records * 32 == the member"
            elif fmt == "WIFF":
                rule = "big-endian declared size + 8 == the member"
            return Identity(fmt, tag=tag, magic=magic, rule=rule, shape=shape or {})

    tdb = _tdb(head, size)
    if tdb is not None:
        return Identity("TDB", tag=None, magic=magic,
                        rule="DB magic, version word, table count in range", shape=tdb)

    walk = renderware_walk(head, size, read)
    if walk is not None and walk["section_id"] in RW_NAMES:
        if walk["walk_consumes_the_member"]:
            rule = "top-level section walk consumes the member exactly"
        elif walk["one_section_accounts_for_the_file"]:
            rule = "one section accounts for the member"
        else:
            rule = None
        if rule is not None:
            return Identity(RW_NAMES[walk["section_id"]], tag=tag, magic=magic,
                            rule=rule, shape=walk)
        # The id is a published RenderWare one but neither rule held.  Say so,
        # and carry the sequence: that is what turns "not RenderWare" into a
        # question the next reader can answer.
        return Identity(RW_NAMES[walk["section_id"]] + "?", tag=tag, magic=magic,
                        rule="RenderWare id, but no top-level walk consumes the member",
                        shape=walk)

    if len(head) >= 8 and head[:4] == b"\x00\x00\x01\x00":
        count, = struct.unpack_from("<I", head, 4)
        if 1 <= count <= 8:
            return Identity("PS2-ICO", tag=None, magic=magic)
    if len(head) >= 4 and not any(head[:16]):
        return Identity("zero-head", tag=None, magic=magic)
    if _looks_like_text(head):
        return Identity("TEXT", tag=tag, magic=magic)
    return Identity("unknown", tag=tag, magic=magic)


__all__ = ["HEAD_BYTES", "Identity", "FORWARD_MAGICS", "REVERSED_MAGICS", "SCHL_PLATFORMS",
           "RW_NAMES", "identify", "renderware_walk", "tag_text"]
