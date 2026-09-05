#!/usr/bin/env python3
"""Read-only map of an EA / Visual Concepts PlayStation 2 disc.

One command per disc, run wherever the image lives (the rig), writing only counts,
names, sizes, offsets and digests -- never member payloads, strings or pixels --
so its output can be committed to a retail-free repository::

    python3 tools/owner/ea_disc_map.py --iso IMAGE.iso --out DIR [--label "NCAA Football 06 (USA)"] [--hash-image]
    python3 tools/owner/ea_disc_map.py --render DIR/<serial>.<label>.map.json      # the Markdown again, from the JSON
    python3 tools/owner/ea_disc_map.py --page DIR/<serial>.<label>.map.json        # a pre-filled disc-map page skeleton
    python3 tools/owner/ea_disc_map.py --compare A.map.json B.map.json             # retail vs Deluxe, 04 vs 06 vs 09
    python3 tools/owner/ea_disc_map.py --summary DIR                               # one table over every map in DIR
    python3 tools/owner/ea_disc_map.py --selftest

It produces ``<out>/<serial>.<label-slug>.map.json`` (the whole map) and
``<out>/<serial>.<label-slug>.map.md`` (the summary a person or an agent reads).
What it maps:

* identity: SYSTEM.CNF boot file and serial, the boot ELF's sha256 and PCSX2 CRC,
  the volume header, optionally the whole-image sha256;
* every file: path, size, and a first-level kind from its magic (``TERF``
  container, ``TDB`` database, ``ELF``/``IRX`` code, ``QL01``, ``BIGF``, ``SHPS``,
  ``SCHl``, ``MPCh``, ``ABKC``, PS2 system files, ``TEXT``, ``VC-pack`` by path,
  or ``other:<hex>`` with an extension hint);
* every TERF container: chunk chain, alignment, member count, codec histogram,
  decompressed-format histogram, layout violations, member-size statistics, MMAP
  dimension / version / format-id histograms, TEXT totals, SCHl header ids,
  nested TERF (three levels), the EA TDB schema of every database member
  (identical schemas recorded once), and a histogram of unclassified magics;
* every EA BIG archive (``BIGF`` / ``BIG4`` / ``.VIV``): entries, size-field
  endianness, RefPack-packed members classified by their *decompressed* head,
  nested archives one level down, SHPS image-bank headers, SCHl headers, TERF and
  TDB members;
* every bare TDB file, every ``QL01`` preload file, every ELF / IRX.

Nothing here writes to the image.  Containers are read through a memory map on a
2048-byte image and through sector-gathered reads on a raw-CD (2352-byte) image.
The EA TDB reader below is schema-only and little-endian (the PlayStation 2
layout the owner's repositories document byte by byte); a big-endian or
unreadable database is reported as such, not guessed.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import mmap
import os
import re
import statistics
import struct
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

_FILE = globals().get("__file__", "")
if _FILE and Path(_FILE).is_file():
    _HERE = Path(_FILE).resolve().parent          # tools/owner
else:  # run as ``python3 - < tools/owner/ea_disc_map.py`` from the repository root (the rig): __file__ is "<stdin>"
    _HERE = Path.cwd() / "tools" / "owner"
_ROOT = _HERE.parent.parent
for _p in (_ROOT / "tools", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import ps2_iso9660 as iso  # noqa: E402
from mod_editor.games._formats import ea_terf  # noqa: E402
from mod_editor.games._formats import ps2_elf  # noqa: E402

SCHEMA = "ea_disc_map/v2"
TDB_FIELD_TYPES = {0: "string", 1: "binary", 2: "sint", 3: "uint", 4: "float"}

#: File-level kinds by magic, first match wins.  Every entry is either an EA
#: format the owner's census measured on these discs, or a PlayStation 2 system
#: file whose magic is fixed by Sony's SDK.
MAGIC_KINDS: Dict[bytes, str] = {
    b"TERF": "TERF", b"DB\x00\x08": "TDB", b"\x7fELF": "ELF", b"QL01": "QL01",
    b"BIGF": "BIGF", b"BIG4": "BIGF", b"RIFF": "RIFF", b"MMAP": "MMAP", b"SCHl": "SCHl",
    b"SMF\x00": "SMF", b"DMF\x00": "DMF",
    b"SHPS": "SHPS", b"ShpS": "SHPS", b"SHPM": "SHPS", b"SHPP": "SHPS", b"SHPX": "SHPS",
    b"MPCh": "MPCh", b"ABKC": "ABKC", b"BNKl": "BNKl", b"LOCH": "LOCH",
    b"FNTS": "FNTS", b"FntS": "FNTS", b"SKL1": "SKL1", b"1LKS": "SKL1", b"SEVT": "SEVT",
    b"EAGL": "EAGL", b"HSH1": "HSH1", b"PFR1": "PFR1", b"Apt ": "Apt", b"ASFT": "ASFT",
    b"RESET\x00\x00\x00": "IOPRP", b"PS2D": "ICON.SYS",
    b"\x00\x00\x01\xb3": "MPEG-video", b"\x00\x00\x01\xba": "MPEG-PS",
    b"IECS": "SCEI-HD",
    b"\x03\x12\x3c\x07": "EVT", b"\x03\x11\x3c\x07": "EVT",   # the head of every loose .EVT audio event table (MVP 2005, NCAA 06)
}
#: Member-level magics the mapper adds on top of ``ea_terf.identify_member`` --
#: applied only to members that module leaves unclassified, so its counts and
#: this tool's agree wherever both know the format.
EXTRA_MEMBER_MAGICS: Tuple[Tuple[bytes, str], ...] = (
    (b"ABKC", "ABKC"), (b"RIFF", "RIFF"), (b"LOCH", "LOCH"), (b"PFR1", "PFR1"),
    (b"Apt ", "Apt"), (b"ASFT", "ASFT"), (b"\x03\x12\x3c\x07", "EVT"), (b"\x03\x11\x3c\x07", "EVT"),
    (b"\x00\x00\x01\xba", "MPEG-PS"), (b"\x00\x00\x01\xb3", "MPEG-video"),
)
#: What a file with no magic probably is, from its extension alone.  These are
#: hints, graded [A] wherever they are quoted; the ``kind`` column never uses them.
EXT_HINTS: Dict[str, str] = {
    "evt": "EA audio event table (no magic)", "off": "EA audio offset table, text rows (no magic)",
    "idx": "EA audio index table (no magic)", "fcd": "EA speech header table (no magic)",
    "csi": "EA audio event index (no magic)", "a1c": "EA audio event table (no magic)",
    "hd": "Sony SCEI sound header (.HD)", "bd": "Sony SCEI sound body (.BD, no magic)",
    "rgb": "raw image (no magic)", "pf": "raw font bitmap (no magic)", "m2v": "MPEG-2 video",
    "pss": "PS2 movie stream (MPEG-PS)", "rws": "RenderWare stream", "hwd": "Burnout demo vehicle mesh",
    "lwd": "Burnout demo vehicle mesh", "bgv": "Burnout demo vehicle data", "txd": "RenderWare texture dictionary",
    "img": "Sony IOP reset image", "ico": "PS2 save icon", "sys": "PS2 save icon descriptor",
    "qix": "IRX bundle (by name)", "loc": "locale table", "csv": "text table", "tsv": "text table",
    "txt": "text", "cfg": "text config", "xml": "XML text", "lop": "text list", "cnf": "PS2 config text",
    "mpc": "EA movie stream", "abk": "EA audio bank", "ssh": "EA shape / image bank", "sfn": "EA font",
    "viv": "EA BIG archive (VIV)", "big": "EA BIG archive", "ttf": "TrueType font", "pfr": "EA font resource",
    "dbc": "EA database text", "act": "EA action script", "mgd": "EA camera data", "ubr": "XML lighting rig",
    "gdb": "text", "pl": "text", "scn": "EA scene", "fx": "EA audio effect", "sbk": "EA script bank",
    "ico;1": "PS2 save icon",
}
#: ``/VC_<serial digits>/<n>.`` -- Visual Concepts' outer pack archive.  Not EA,
#: not walked here; the fork's 2K5 module already inventories it.
VC_PACK_RE = re.compile(r"^/VC_\d{5}/\d+\.?$")
VC_PACK_NOTE = ("Visual Concepts outer pack archive; inventoried by the fork's "
                "`nfl2k5ps2.textures.disc_inventory` lane (`tools/validate_nfl2k5_ps2_disc_inventory.sh`), not by this mapper")

#: PT-header tags of an EA ``SCHl`` stream, as vgmstream's ``ea_schl.c`` reads
#: them: each tag is one byte, then a length byte, then a big-endian value.
SCHL_TAG_CHANNELS, SCHL_TAG_CODEC, SCHL_TAG_RATE, SCHL_TAG_SAMPLES = 0x82, 0x83, 0x84, 0x85
SCHL_PLATFORMS = {0x00: "PC", 0x01: "PSX", 0x02: "N64", 0x03: "MAC", 0x04: "SAT", 0x05: "PS2",
                  0x06: "GC/Wii", 0x07: "Xbox", 0x09: "X360", 0x0A: "PSP", 0x0E: "PS3"}
#: ELF ``e_type`` values that matter on a PlayStation 2 disc.
ELF_TYPES = {2: "EXEC", 1: "REL", 0xFF80: "IRX (SCE IOP relocatable)"}

RAW_VIEW_CAP = 1 << 30           # a raw-CD image has no contiguous extent to memory-map; gather up to this
BIG_MEMBER_READ_CAP = 64 << 20   # a TERF member inside a BIG archive is mapped only up to this size
HEAD_BYTES = 16


class MapError(ValueError):
    """A sentence about what could not be mapped; never a traceback for the operator."""


# --------------------------------------------------------------------------
# EA TDB, schema only (little-endian PS2 layout)
# --------------------------------------------------------------------------
def tdb_schema(data) -> Dict[str, Any]:
    """Tables, record counts and fields of one EA TDB v8 database; refuses unreadable ones."""
    data = bytes(data[:24]) + bytes(data[24:]) if not isinstance(data, (bytes, bytearray)) else data
    preamble = 0
    if data[:4] == b"\x02\x00\x00\x00" and data[4:6] == b"DB":
        preamble = 4
    body = data[preamble:]
    if body[:2] != b"DB":
        raise MapError("not an EA TDB: magic %r" % (bytes(body[:2]),))
    if len(body) < 24:
        raise MapError("EA TDB header needs 24 bytes; %d given" % len(body))
    # The version word sits on the disc as ``00 08`` (a bare memory-card database writes ``08 00``);
    # both mean 8, so the smaller of the two readings is the version and the bytes are kept verbatim.
    version = min(struct.unpack_from("<H", body, 2)[0], struct.unpack_from(">H", body, 2)[0])
    version_bytes = bytes(body[2:4]).hex()
    table_count = struct.unpack_from("<I", body, 0x10)[0]
    if table_count > 10_000:
        return {"endian": "big", "version": version, "version_bytes": version_bytes,
                "tables": [], "note": "big-endian TDB (PS3 layout); schema not parsed here"}
    if version_bytes not in ("0008", "0800"):
        raise MapError("EA TDB version word %s: only the v8 layout (00 08 on disc) is parsed here" % version_bytes)
    directory = 24
    directory_end = directory + table_count * 8
    if directory_end > len(body):
        raise MapError("EA TDB declares %d tables but is only %d bytes" % (table_count, len(body)))
    tables = []
    for index in range(table_count):
        name_raw = body[directory + index * 8: directory + index * 8 + 4]
        offset = struct.unpack_from("<I", body, directory + index * 8 + 4)[0]
        header = directory_end + offset
        if header + 40 > len(body):
            tables.append({"name": name_raw.decode("latin-1"), "error": "table header outside the database"})
            continue
        len_bytes = struct.unpack_from("<I", body, header + 8)[0]
        len_bits = struct.unpack_from("<I", body, header + 12)[0]
        max_records = struct.unpack_from("<H", body, header + 20)[0]
        cur_records = struct.unpack_from("<H", body, header + 22)[0]
        num_fields = body[header + 28]
        index_count = body[header + 29]
        fields = []
        fbase = header + 40
        for f in range(num_fields):
            fo = fbase + f * 16
            if fo + 16 > len(body):
                break
            ftype, fbit, fname, fwidth = struct.unpack_from("<II4sI", body, fo)
            fields.append({"name": fname.decode("latin-1"), "type": TDB_FIELD_TYPES.get(ftype, str(ftype)),
                           "bit_offset": fbit, "bits": fwidth})
        tables.append({"name": name_raw.decode("latin-1"), "records": cur_records, "max_records": max_records,
                       "record_bytes": len_bytes, "record_bits": len_bits, "indexes": index_count,
                       "fields": fields})
    return {"endian": "little", "version": version, "version_bytes": bytes(body[2:4]).hex(), "preamble": preamble, "table_count": table_count,
            "db_size": struct.unpack_from("<I", body, 8)[0], "tables": tables}


def schema_signature(schema: Dict[str, Any]) -> str:
    """A digest of the table/field shape (not the record counts), so repeats are recorded once."""
    shape = [(t.get("name"), tuple((f["name"], f["type"], f["bits"]) for f in t.get("fields", [])))
             for t in schema.get("tables", [])]
    return hashlib.sha256(repr(shape).encode("utf-8")).hexdigest()[:16]


def _record_schema(schema: Dict[str, Any], schemas: Dict[str, Dict[str, Any]]) -> str:
    sig = schema_signature(schema)
    schemas.setdefault(sig, {"tables": [{k: v for k, v in t.items() if k != "records"} for t in schema["tables"]],
                             "endian": schema["endian"], "version": schema["version"]})
    return sig


# --------------------------------------------------------------------------
# small format headers: SHPS, SCHl, RefPack, MMAP format id, ELF, QL01
# --------------------------------------------------------------------------
def shps_header(data) -> Dict[str, Any]:
    """The EA image-bank (FSH / SHPS) directory: image count, directory id, and the first image's record.

    Layout as fshtool and the niotso FSH notes give it: magic, u32 file size, u32 image count,
    4-char directory id, then ``count`` x (4-char name, u32 offset); an image record starts with
    a u8 record id, a u24 block size, u16 width and u16 height.  Little-endian on PlayStation 2
    banks; the cross-platform UI packs NCAA 06 carries store the same fields big-endian, so the
    byte order is chosen by which reading gives a plausible count and is reported.
    """
    if len(data) < 16 or bytes(data[:4]) not in (b"SHPS", b"ShpS", b"SHPM", b"SHPP", b"SHPX"):
        raise MapError("not an SHPS image bank")
    size_le, count_le = struct.unpack_from("<II", data, 4)
    size_be, count_be = struct.unpack_from(">II", data, 4)
    plausible = lambda count, size: 0 < count <= 4096 and 16 + 8 * count <= max(size, len(data))  # noqa: E731
    if plausible(count_le, size_le):
        order, size, count = "<", size_le, count_le
    elif plausible(count_be, size_be):
        order, size, count = ">", size_be, count_be
    else:
        raise MapError("SHPS directory declares %d (LE) / %d (BE) images; neither fits the bank" % (count_le, count_be))
    result: Dict[str, Any] = {"declared_size": size, "images": count, "endian": "little" if order == "<" else "big",
                              "directory_id": bytes(data[12:16]).decode("latin-1", "replace")}
    if 16 + 8 * count <= len(data):
        first_offset = struct.unpack_from(order + "I", data, 16 + 4)[0]
        if first_offset + 8 <= len(data):
            record_id = data[first_offset]
            width, height = struct.unpack_from(order + "HH", data, first_offset + 4)
            result["first_image"] = {"record_id": record_id, "width": width, "height": height}
    return result


def schl_header(head) -> Optional[Dict[str, Any]]:
    """Platform id and the version / channels / codec / sample-rate patches of an EA ``SCHl`` header block.

    ``SCHl``, u32 block size, then either ``PT`` + u16 platform id or ``GSTR`` + u32 (a generic
    stream), then patches: one tag byte, one length byte, a big-endian value -- except 0xFD, which
    marks the start of the platform sub-header and carries nothing, and 0xFC..0xFF, which end the
    list.  This is the reading vgmstream's ``ea_schl.c`` documents (tag 0x80 version, 0x82
    channels, 0x83 codec, 0x84 sample rate, 0x85 sample count, 0xA0 codec, second family).
    Returns ``None`` for a block this reader cannot follow; nothing below the header is read.
    """
    head = bytes(head)
    if len(head) < 12 or head[:4] != b"SCHl":
        return None
    block = struct.unpack_from("<I", head, 4)[0]
    if block > 0x10000:  # some platforms store the block size big-endian
        block = struct.unpack_from(">I", head, 4)[0]
    if head[8:10] == b"PT":
        platform: Any = struct.unpack_from("<H", head, 10)[0]; pos = 12
    elif head[8:12] == b"GSTR":
        platform = "GSTR"; pos = 16
    else:
        return None
    tags: Dict[int, int] = {}
    limit = min(len(head), block if 12 < block <= len(head) else len(head))
    while pos < limit:
        tag = head[pos]; pos += 1
        if tag >= 0xFC and tag != 0xFD:
            break
        if tag == 0xFD:
            continue
        if pos >= limit:
            break
        width = head[pos]; pos += 1
        if width == 0 or width > 4 or pos + width > limit:
            break
        tags[tag] = int.from_bytes(head[pos:pos + width], "big"); pos += width
    return {"block": block, "platform": platform, "version": tags.get(0x80), "channels": tags.get(SCHL_TAG_CHANNELS),
            "codec": tags.get(SCHL_TAG_CODEC), "codec2": tags.get(0xA0), "rate": tags.get(SCHL_TAG_RATE), "samples": tags.get(SCHL_TAG_SAMPLES)}


def refpack_head(buf, want: int = 32) -> Optional[Tuple[int, bytes]]:
    """(declared decompressed size, first ``want`` decompressed bytes) of an EA RefPack stream.

    RefPack is EA's public LZ77 variant (the ``10 FB`` family: flag byte with bit 4 set, then
    ``FB``; bit 7 = a compressed-size field is present, bit 0 = 4-byte sizes; big-endian
    sizes).  Stops the instant ``want`` bytes exist, so a member is never unpacked further than
    its magic.  Returns ``None`` when the stream is not RefPack or is cut before ``want`` bytes.
    """
    buf = bytes(buf)
    if len(buf) < 5 or buf[1] != 0xFB or (buf[0] & 0x3E) != 0x10:
        return None
    flags = buf[0]; big = flags & 0x01; pos = 2
    if flags & 0x80:
        pos += 4 if big else 3
    size_width = 4 if big else 3
    if pos + size_width > len(buf):
        return None
    declared = int.from_bytes(buf[pos:pos + size_width], "big"); pos += size_width
    out = bytearray()
    try:
        while pos < len(buf) and len(out) < want:
            b0 = buf[pos]
            if b0 < 0x80:
                b1 = buf[pos + 1]; pos += 2; lit = b0 & 3; out += buf[pos:pos + lit]; pos += lit
                offset = ((b0 & 0x60) << 3) + b1 + 1; length = ((b0 & 0x1C) >> 2) + 3
            elif b0 < 0xC0:
                b1, b2 = buf[pos + 1], buf[pos + 2]; pos += 3; lit = b1 >> 6; out += buf[pos:pos + lit]; pos += lit
                offset = ((b1 & 0x3F) << 8) + b2 + 1; length = (b0 & 0x3F) + 4
            elif b0 < 0xE0:
                b1, b2, b3 = buf[pos + 1], buf[pos + 2], buf[pos + 3]; pos += 4; lit = b0 & 3; out += buf[pos:pos + lit]; pos += lit
                offset = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1; length = ((b0 & 0x0C) << 6) + b3 + 5
            elif b0 < 0xFC:
                pos += 1; lit = ((b0 & 0x1F) << 2) + 4; out += buf[pos:pos + lit]; pos += lit
                continue
            else:
                pos += 1; lit = b0 & 3; out += buf[pos:pos + lit]; pos += lit
                break
            if offset > len(out):
                return None
            for _ in range(length):
                out.append(out[-offset])
    except IndexError:
        return None
    if len(out) < min(want, declared):
        return None
    return declared, bytes(out[:want])


def mmap_ids(payload) -> Tuple[int, int, int]:
    """(version, format id at +0x2C, u32 at +0x30) of an MMAP member; measured fields, not interpreted."""
    version = struct.unpack_from("<I", payload, 4)[0]
    format_id = struct.unpack_from("<H", payload, 0x2C)[0] if len(payload) >= 0x2E else -1
    pixel_field = struct.unpack_from("<I", payload, 0x30)[0] if len(payload) >= 0x34 else -1
    return version, format_id, pixel_field


def elf_info(head: bytes) -> Dict[str, Any]:
    """Class, type, machine and entry of an ELF from its first 32 bytes."""
    if len(head) < 24 or head[:4] != b"\x7fELF":
        raise MapError("not an ELF")
    little = head[5] == 1
    order = "<" if little else ">"
    e_type, e_machine = struct.unpack_from(order + "HH", head, 16)
    entry = struct.unpack_from(order + "I", head, 24)[0] if len(head) >= 28 else None
    return {"class": 32 if head[4] == 1 else 64, "endian": "little" if little else "big",
            "type": ELF_TYPES.get(e_type, "0x%04x" % e_type), "machine": e_machine, "entry": entry}


def map_qkl(data) -> Dict[str, Any]:
    """A ``QL01`` preload file: which containers it copies and how many copies, as the census read it."""
    if len(data) < 16 or bytes(data[:4]) != b"QL01":
        raise MapError("not a QL01 preload file")
    first, data_offset = struct.unpack_from("<II", data, 4)
    result: Dict[str, Any] = {"payload_offset": data_offset, "payload_bytes": max(0, len(data) - data_offset)}
    pos = first; names: List[str] = []; entries = 0; kinds: Counter = Counter(); per_file: Counter = Counter(); offsets = set()
    for _ in range(8):
        if pos + 8 > len(data):
            break
        tag = bytes(data[pos:pos + 4]); size = struct.unpack_from("<I", data, pos + 4)[0]
        if tag == b"FILS" and size >= 12:
            count = struct.unpack_from("<I", data, pos + 8)[0]
            for i in range(min(count, 4096)):
                start = pos + 12 + i * 48
                if start + 48 > len(data):
                    break
                names.append(bytes(data[start:start + 48]).split(b"\x00")[0].decode("latin-1", "replace"))
        elif tag == b"DTLS" and size >= 12:
            entries = struct.unpack_from("<I", data, pos + 8)[0]
            for i in range(min(entries, 1_000_000)):
                start = pos + 12 + i * 12
                if start + 12 > len(data):
                    break
                kind, _, file_index = data[start], data[start + 1], data[start + 2]
                kinds[int(kind)] += 1
                per_file[names[file_index] if file_index < len(names) else "?"] += 1
                offsets.add(struct.unpack_from("<I", data, start + 8)[0])
        if size == 0 or tag == b"DATA":
            break
        pos += size
    result.update({"files": len(names), "file_names": names, "entries": entries,
                   "header_copies": kinds.get(0, 0), "member_copies": kinds.get(1, 0), "other_kinds": {str(k): v for k, v in kinds.items() if k not in (0, 1)},
                   "distinct_offsets": len(offsets), "copies_per_file": dict(per_file.most_common(40))})
    return result


def identify_head(head: bytes, path: str = "") -> str:
    """First-level kind of a *file* from its first bytes (and, for VC packs, its path)."""
    if VC_PACK_RE.match(path):
        return "VC-pack"
    if not head:
        return "empty"
    for magic, kind in MAGIC_KINDS.items():
        if head.startswith(magic):
            return kind
    if head[:4] == b"\x00\x00\x01\x00" and len(head) >= 8 and 1 <= struct.unpack_from("<I", head, 4)[0] <= 8:
        return "PS2-ICO"
    if len(head) >= 4 and not any(head[:HEAD_BYTES]):
        return "zero-head"
    if ea_terf.identify_member(head) == ea_terf.FORMAT_TEXT:
        return "TEXT"
    text = head[3:] if head.startswith(b"\xef\xbb\xbf") else head
    if text and all(32 <= b < 127 or b in (9, 10, 13) or b >= 0xA0 for b in text):
        return "TEXT"   # a file-level rule only: UTF-8 BOM or Latin-1 letters; members keep ea_terf's strict ASCII rule
    return "other:" + head[:4].hex()


def magic_kind(head: bytes) -> str:
    """Kind from a magic alone (kept for callers that have no path)."""
    return identify_head(bytes(head))


def ext_hint(path: str) -> str:
    name = path.rsplit("/", 1)[-1].lower()
    return EXT_HINTS.get(name.rsplit(".", 1)[-1], "") if "." in name else ""


def _extra_member_kind(head: bytes) -> Optional[str]:
    for magic, kind in EXTRA_MEMBER_MAGICS:
        if head.startswith(magic):
            return kind
    return None


# --------------------------------------------------------------------------
# containers
# --------------------------------------------------------------------------
def _size_stats(sizes: Sequence[int]) -> Dict[str, Any]:
    if not sizes:
        return {"min": 0, "median": 0, "max": 0, "distinct": 0}
    return {"min": min(sizes), "median": int(statistics.median(sizes)), "max": max(sizes), "distinct": len(set(sizes))}


def _schl_stats(records: Iterable[Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """Histograms over parsed SCHl headers; ``-`` means the patch is absent (vgmstream then defaults: 1 channel)."""
    platforms: Counter = Counter(); codecs: Counter = Counter(); rates: Counter = Counter(); channels: Counter = Counter(); versions: Counter = Counter()
    parsed = unparsed = 0
    for rec in records:
        if rec is None:
            unparsed += 1
            continue
        parsed += 1
        plat = rec["platform"]
        platforms[plat if isinstance(plat, str) else SCHL_PLATFORMS.get(plat, "0x%02x" % plat)] += 1
        codecs[("c1=0x%02x" % rec["codec"] if rec.get("codec") is not None else "") + ("/" if rec.get("codec") is not None and rec.get("codec2") is not None else "")
               + ("c2=0x%02x" % rec["codec2"] if rec.get("codec2") is not None else "") or "-"] += 1
        rates[str(rec["rate"]) if rec.get("rate") is not None else "-"] += 1
        channels[str(rec["channels"]) if rec.get("channels") is not None else "-"] += 1
        versions[str(rec["version"]) if rec.get("version") is not None else "-"] += 1
    return {"parsed": parsed, "unparsed": unparsed, "platforms": dict(platforms.most_common(6)), "versions": dict(versions.most_common(4)),
            "codecs": dict(codecs.most_common(8)), "rates": dict(rates.most_common(8)), "channels": dict(channels.most_common(4))}


def map_terf(data, schemas: Dict[str, Dict[str, Any]], *, depth: int = 0, max_depth: int = 3,
             magic_index: Optional[Dict[str, Counter]] = None, origin: str = "") -> Dict[str, Any]:
    """One TERF container, as counts: chain, codecs, formats, sizes, MMAP ids, SCHl ids, TDB schemas, TEXT totals."""
    container = ea_terf.parse_terf(data, allow_size_mismatch=True)
    formats: Counter = Counter()
    dims: Counter = Counter(); mmap_formats: Counter = Counter(); mmap_unparsed = 0; mmap_index_like = 0
    nested_formats: Counter = Counter(); nested_tdb = 0; nested_schemas: set = set(); nested = 0; nested_depth = depth
    text_members = 0; text_bytes = 0
    tdb_members: List[Dict[str, Any]] = []
    undecodable = 0
    unknown_heads: Counter = Counter()
    schl_records: List[Optional[Dict[str, Any]]] = []
    for index in range(container.member_count):
        try:
            kind = container.member_format(index)
        except ea_terf.TerfError:
            undecodable += 1
            formats["undecodable"] += 1
            continue
        if kind is None:
            try:
                head = container.member(index, max_output=ea_terf.IDENTIFY_HEAD)
            except ea_terf.TerfError:
                head = b""
            kind = _extra_member_kind(head)
            if kind is None:
                kind = "unclassified"
                unknown_heads[head[:4].hex() or "empty"] += 1
        formats[kind] += 1
        if kind == "MMAP":
            try:
                payload = container.member(index, max_output=0x40)
                head = ea_terf.parse_mmap_header(payload)
                version, format_id, _ = mmap_ids(payload)
                mmap_formats[f"v{version}/fmt{format_id:#x}"] += 1
                if format_id == 0x400:
                    mmap_index_like += 1     # declares 1x3; not a texture layout the parser understands
                else:
                    dims[f"{head.width}x{head.height}"] += 1
            except (ea_terf.TerfError, ValueError, struct.error):
                mmap_unparsed += 1
        elif kind == "TEXT":
            text_members += 1
            text_bytes += container.members[index].decompressed_size
        elif kind == "SCHl":
            try:
                schl_records.append(schl_header(container.member(index, max_output=96)))
            except ea_terf.TerfError:
                schl_records.append(None)
        elif kind == "TERF":
            nested += 1
            if depth < max_depth:
                try:
                    inner = map_terf(container.member(index), schemas, depth=depth + 1, max_depth=max_depth, magic_index=magic_index, origin=origin)
                    nested_formats.update(inner["formats"])
                    nested_formats.update(inner.get("nested_formats", {}))
                    nested_tdb += len(inner["tdb_members"]) + inner.get("nested_tdb_members", 0)
                    nested_schemas.update(t["schema"] for t in inner["tdb_members"] if t.get("schema"))
                    nested_schemas.update(inner.get("nested_schemas", []))
                    nested_depth = max(nested_depth, inner.get("nested_depth_max", depth + 1))
                except (ea_terf.TerfError, ValueError, MapError, struct.error):
                    nested_formats["undecodable"] += 1
        elif kind == "TDB":
            try:
                schema = tdb_schema(container.member(index))
                sig = _record_schema(schema, schemas)
                tdb_members.append({"member": index, "schema": sig, "tables": [(t["name"], t.get("records")) for t in schema["tables"]]})
            except (MapError, struct.error, ea_terf.TerfError) as error:
                tdb_members.append({"member": index, "error": str(error)[:120]})
    if magic_index is not None:
        for magic, n in unknown_heads.items():
            magic_index.setdefault(magic, Counter())[origin] += n
    stored_sizes = [m.stored_size for m in container.members]
    unpacked_sizes = [m.decompressed_size for m in container.members]
    largest = max(range(container.member_count), key=lambda i: unpacked_sizes[i], default=None)
    result: Dict[str, Any] = {
        "chain": container.chunk_chain, "alignment": container.alignment,
        "members": container.member_count, "declared_length": container.declared_length,
        "size_mismatch": container.size_mismatch, "codecs": container.codec_histogram(),
        "formats": dict(sorted(formats.items(), key=lambda kv: (-kv[1], kv[0]))),
        "layout_violations": container.layout_violations()[:8],
        "member_sizes": {**_size_stats(unpacked_sizes), "stored_total": sum(stored_sizes), "decompressed_total": sum(unpacked_sizes),
                         "largest_member": largest, "largest_bytes": unpacked_sizes[largest] if largest is not None else 0},
        "mmap_dimensions": dict(dims.most_common(24)), "mmap_formats": dict(mmap_formats.most_common(12)),
        "mmap_unparsed": mmap_unparsed, "mmap_format_0x400": mmap_index_like,
        "text_members": text_members, "text_bytes": text_bytes,
        "nested_terf": nested, "nested_formats": dict(sorted(nested_formats.items(), key=lambda kv: (-kv[1], kv[0]))),
        "nested_tdb_members": nested_tdb, "nested_schemas": sorted(nested_schemas), "nested_depth_max": nested_depth if nested else depth,
        "undecodable": undecodable, "unclassified_heads": dict(unknown_heads.most_common(8)), "unclassified_total": sum(unknown_heads.values()),
        "tdb_members": tdb_members,
    }
    if schl_records:
        result["schl"] = _schl_stats(schl_records)
    return result


class _View:
    """A bytes-like over one disc file plus the way to let go of it; ``close()`` never raises."""

    def __init__(self, data, closer: Callable[[], None]) -> None:
        self.data = data
        self._closer = closer

    def close(self) -> None:
        try:
            self._closer()
        except BufferError:
            gc.collect()
            try:
                self._closer()
            except BufferError:
                pass

    def __enter__(self) -> "_View":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class _Extent:
    """One file on the disc, readable in ranges or as a view, on 2048-byte and raw-CD images alike."""

    def __init__(self, handle, image, entry, offset: Optional[int] = None, size: Optional[int] = None) -> None:
        self.handle = handle; self.image = image; self.entry = entry
        self.lba = entry.lba if entry is not None else 0
        self.size = entry.length if size is None else size
        self.contiguous = image is None or (image.sector_size == iso.SECTOR_USER_BYTES and image.data_offset == 0)
        self.offset = offset if offset is not None else (iso.extent_byte_offset(image, self.lba) if image is not None else 0)

    def available(self, wanted: int) -> int:
        """How many of ``wanted`` bytes from this file's start the image physically holds."""
        if self.image is None:
            return min(wanted, self.size)
        if self.contiguous:
            return max(0, min(wanted, self.image.file_size - self.offset))
        if wanted <= 0:
            return 0
        last = iso.extent_byte_offset(self.image, self.lba, wanted - 1) + 1
        if last <= self.image.file_size:
            return wanted
        blocks = max(0, (self.image.file_size - self.image.data_offset) // self.image.sector_size - self.lba)
        return max(0, min(wanted, blocks * iso.SECTOR_USER_BYTES))

    def read(self, start: int, length: int, *, limit: Optional[int] = None) -> bytes:
        limit = self.size if limit is None else limit
        if start < 0 or length < 0 or start + length > limit:
            raise MapError("range %d+%d outside a %d-byte file" % (start, length, limit))
        if length == 0:
            return b""
        if self.contiguous:
            self.handle.seek(self.offset + start)
            return self.handle.read(length)
        parts = []
        position = start
        end = start + length
        while position < end:
            within = position % iso.SECTOR_USER_BYTES
            take = min(iso.SECTOR_USER_BYTES - within, end - position)
            self.handle.seek(iso.extent_byte_offset(self.image, self.lba, position))
            parts.append(self.handle.read(take))
            position += take
        return b"".join(parts)

    def view(self, length: Optional[int] = None) -> _View:
        """The first ``length`` bytes (default: the file) as a memoryview; the caller closes the view."""
        length = self.size if length is None else length
        if length == 0:
            return _View(memoryview(b""), lambda: None)
        if not self.contiguous:
            if length > RAW_VIEW_CAP:
                raise MapError("raw-CD image: a %d-byte file cannot be memory-mapped and exceeds the %d-byte gather cap" % (length, RAW_VIEW_CAP))
            data = memoryview(self.read(0, length, limit=length))
            return _View(data, data.release)
        gran = mmap.ALLOCATIONGRANULARITY
        base = self.offset - self.offset % gran
        mapped = mmap.mmap(self.handle.fileno(), (self.offset - base) + length, access=mmap.ACCESS_READ, offset=base)
        whole = memoryview(mapped)
        sliced = whole[self.offset - base: self.offset - base + length]

        def closer() -> None:
            sliced.release(); whole.release(); mapped.close()
        return _View(sliced, closer)


def container_span(extent: _Extent) -> Tuple[int, int]:
    """(bytes to map, bytes the ISO9660 record is short by) for a TERF file whose DATA chunk may say more than the directory."""
    try:
        head = extent.read(0, min(extent.size, 8192))
        declared = ea_terf.declared_length(head)
    except (ea_terf.TerfError, MapError, struct.error):
        return extent.size, 0
    if declared <= extent.size:
        return extent.size, 0
    available = extent.available(declared)
    return available, declared - extent.size


# --------------------------------------------------------------------------
# EA BIG archives
# --------------------------------------------------------------------------
def _big_entries(header: bytes, index: bytes, count: int) -> List[Tuple[str, int, int]]:
    entries = []; pos = 0
    for _ in range(count):
        if pos + 8 > len(index):
            break
        off, size = struct.unpack_from(">II", index, pos); pos += 8
        end = index.find(b"\x00", pos)
        if end < 0:
            break
        entries.append((index[pos:end].decode("latin-1"), off, size)); pos = end + 1
    return entries


def _classify_big_member(read_head: Callable[[int], bytes], size: int) -> Tuple[str, Optional[int], bytes]:
    """(kind, RefPack declared size or None, first bytes as the member would read decompressed).

    RefPack members are unpacked only as far as a header needs (128 bytes); nothing else is decoded.
    """
    if size == 0:
        return "empty", None, b""
    head = read_head(min(size, 1024))
    if len(head) >= 2 and head[1] == 0xFB and (head[0] & 0x3E) == 0x10:
        unpacked = refpack_head(head, 128)
        if unpacked is not None:
            inner = identify_head(unpacked[1])
            return (inner if not inner.startswith("other:") else "refpack:" + inner[6:]), unpacked[0], unpacked[1]
        return "refpack:undecoded", None, b""
    return identify_head(head[:HEAD_BYTES] if len(head) >= HEAD_BYTES else head), None, head


def map_bigf(extent: _Extent, schemas: Optional[Dict[str, Dict[str, Any]]] = None, *, depth: int = 0,
             base: int = 0, size: Optional[int] = None, magic_index: Optional[Dict[str, Counter]] = None, origin: str = "") -> Dict[str, Any]:
    """An EA BIG archive (``BIGF`` / ``BIG4`` / ``.VIV``): entries, member kinds after RefPack, nested archives, SHPS / SCHl / TERF / TDB members."""
    schemas = {} if schemas is None else schemas
    size = extent.size if size is None else size
    head = extent.read(base, min(16, size), limit=base + size)
    if head[:4] not in (b"BIGF", b"BIG4"):
        raise MapError("not a BIG archive: %r" % head[:4])
    size_le = struct.unpack_from("<I", head, 4)[0]; size_be = struct.unpack_from(">I", head, 4)[0]
    count, index_size = struct.unpack_from(">II", head, 8)
    if count > 200_000 or index_size > size or index_size > (64 << 20):
        raise MapError("BIG index declares %d entries / %d index bytes in a %d-byte archive; refusing" % (count, index_size, size))
    index = extent.read(base + 16, max(0, min(index_size, size) - 16), limit=base + size)
    entries = _big_entries(head, index, count)
    kinds: Counter = Counter(); exts: Counter = Counter(); total = 0; shps = 0; shps_images = 0
    shps_records: Counter = Counter(); shps_dims: Counter = Counter(); refpack = 0; refpack_bytes = 0
    directory_entries = 0; nested_bigf = 0; nested_entries = 0; nested_kinds: Counter = Counter(); nested_exts: Counter = Counter()
    schl_records: List[Optional[Dict[str, Any]]] = []; terf_members: Dict[str, Any] = {}; tdb_members: List[Dict[str, Any]] = []
    largest = ("", 0)
    for name, off, member_size in entries:
        total += member_size
        if member_size > largest[1]:
            largest = (name, member_size)
        exts[(name.rsplit(".", 1)[-1].lower() if "." in name else "-")] += 1
        if member_size == 0 and off == 0:
            directory_entries += 1
            kinds["directory"] += 1
            continue
        if off + member_size > size or off < 0:
            kinds["outside-archive"] += 1
            continue

        def read_head(n: int, off: int = off, member_size: int = member_size) -> bytes:
            return extent.read(base + off, min(n, member_size), limit=base + size)
        kind, declared, decoded = _classify_big_member(read_head, member_size)
        kinds[kind] += 1
        if declared is not None:
            refpack += 1; refpack_bytes += declared
        if kind == "SHPS":
            shps += 1
            try:
                info = shps_header(decoded[:128])
                shps_images += info["images"]
                first = info.get("first_image")
                if first:
                    shps_records["0x%02x" % first["record_id"]] += 1; shps_dims[f"{first['width']}x{first['height']}"] += 1
            except (MapError, struct.error):
                pass
        elif kind == "SCHl":
            schl_records.append(schl_header(decoded[:96]))
        elif kind == "BIGF" and depth < 1:
            nested_bigf += 1
            try:
                inner = map_bigf(extent, schemas, depth=depth + 1, base=base + off, size=member_size, magic_index=magic_index, origin=origin)
                nested_entries += inner["entries"]; nested_kinds.update(inner["member_kinds"]); nested_exts.update(inner["extensions"])
                shps += inner["shps_members"]; shps_images += inner["shps_images"]; refpack += inner["refpack_members"]
                shps_records.update(inner["shps_first_record_ids"]); shps_dims.update(inner["shps_first_dims"])
                schl_records.extend([None] * inner.get("schl", {}).get("unparsed", 0))
            except (MapError, struct.error, ValueError) as error:
                nested_kinds["refused: " + str(error)[:60]] += 1
        elif kind == "TERF" and member_size <= BIG_MEMBER_READ_CAP:
            try:
                terf_members[name] = map_terf(memoryview(extent.read(base + off, member_size, limit=base + size)), schemas, depth=1,
                                              magic_index=magic_index, origin=origin)
            except (ea_terf.TerfError, MapError, ValueError, struct.error) as error:
                terf_members[name] = {"error": str(error)[:120]}
        elif kind == "TDB" and member_size <= BIG_MEMBER_READ_CAP:
            try:
                schema = tdb_schema(extent.read(base + off, member_size, limit=base + size))
                tdb_members.append({"name": name, "schema": _record_schema(schema, schemas), "tables": [(t["name"], t.get("records")) for t in schema["tables"]]})
            except (MapError, struct.error) as error:
                tdb_members.append({"name": name, "error": str(error)[:120]})
    result: Dict[str, Any] = {
        "format": head[:4].decode("ascii"), "declared_size": size_le if size_le == size else size_be,
        "size_field": ("LE" if size_le == size else "BE" if size_be == size
                       else "BE (declares %d, file %d)" % (size_be, size) if abs(size_be - size) <= 4096
                       else "LE (declares %d, file %d)" % (size_le, size) if abs(size_le - size) <= 4096
                       else "neither (LE %d / BE %d, file %d)" % (size_le, size_be, size)),
        "entries": count, "entries_read": len(entries), "index_bytes": index_size, "member_bytes": total,
        "member_kinds": dict(kinds.most_common(16)), "extensions": dict(exts.most_common(16)),
        "shps_members": shps, "shps_images": shps_images, "shps_first_record_ids": dict(shps_records.most_common(8)),
        "shps_first_dims": dict(shps_dims.most_common(8)), "refpack_members": refpack, "refpack_declared_bytes": refpack_bytes,
        "directory_entries": directory_entries, "names_with_paths": sum(1 for n, _, _ in entries if "/" in n or "~" in n or "\\" in n),
        "nested_bigf": nested_bigf, "nested_entries": nested_entries, "nested_member_kinds": dict(nested_kinds.most_common(16)),
        "nested_extensions": dict(nested_exts.most_common(12)), "largest_entry": {"name": largest[0], "bytes": largest[1]},
        "names_sample": [n for n, _, _ in entries[:12]],
    }
    if schl_records:
        result["schl"] = _schl_stats(schl_records)
    if terf_members:
        result["terf_members"] = terf_members
    if tdb_members:
        result["tdb_members"] = tdb_members
    return result


# --------------------------------------------------------------------------
# the disc
# --------------------------------------------------------------------------
def _sha256_extent(extent: _Extent) -> str:
    digest = hashlib.sha256(); position = 0
    while position < extent.size:
        chunk = extent.read(position, min(1 << 20, extent.size - position)); digest.update(chunk); position += len(chunk)
    return digest.hexdigest()


def totals_of(containers: Dict[str, Any], archives: Dict[str, Any], magic_index: Optional[Dict[str, Counter]] = None) -> Dict[str, Any]:
    magic_index = magic_index or {}
    formats: Counter = Counter(); codecs: Counter = Counter(); chains: Counter = Counter(); aligns: Counter = Counter()
    dims: Counter = Counter(); mmap_formats: Counter = Counter(); mmap_containers = 0; text_members = text_bytes = 0
    schl_containers: List[str] = []; nested = 0; tdb_members = 0; refused: List[str] = []; members = 0; undecodable = 0
    schl_platforms: Counter = Counter(); schl_codecs: Counter = Counter(); iso_short = 0; text_containers: List[str] = []; tdb_unparsed = 0
    for path, c in sorted(containers.items()):
        if "error" in c:
            refused.append(path); continue
        members += c.get("members", 0); formats.update(c.get("formats", {})); codecs.update(c.get("codecs", {}))
        chains[c.get("chain", "?")] += 1; aligns[str(c.get("alignment"))] += 1
        dims.update(c.get("mmap_dimensions", {})); mmap_formats.update(c.get("mmap_formats", {}))
        mmap_containers += 1 if c.get("formats", {}).get("MMAP") else 0
        text_members += c.get("text_members", 0); text_bytes += c.get("text_bytes", 0)
        if c.get("text_members"):
            text_containers.append(path)
        if c.get("formats", {}).get("SCHl"):
            schl_containers.append(path)
        nested += c.get("nested_terf", 0); tdb_members += len(c.get("tdb_members", [])); undecodable += c.get("undecodable", 0)
        tdb_unparsed += sum(1 for t in c.get("tdb_members", []) if "error" in t)
        schl_platforms.update(c.get("schl", {}).get("platforms", {})); schl_codecs.update(c.get("schl", {}).get("codecs", {}))
        iso_short += 1 if c.get("iso_short_by") else 0
    archive_kinds: Counter = Counter(); archive_entries = 0; archive_refpack = 0; archive_shps = 0; archive_exts: Counter = Counter()
    for a in archives.values():
        if "error" in a:
            continue
        archive_entries += a.get("entries", 0); archive_kinds.update(a.get("member_kinds", {})); archive_kinds.update(a.get("nested_member_kinds", {}))
        archive_refpack += a.get("refpack_members", 0); archive_shps += a.get("shps_members", 0); archive_exts.update(a.get("extensions", {}))
    return {
        "containers": len(containers), "containers_refused": refused, "containers_iso_short": iso_short, "members": members,
        "formats": dict(sorted(formats.items(), key=lambda kv: (-kv[1], kv[0]))), "codecs": dict(codecs),
        "chains": dict(chains.most_common()), "alignments": dict(aligns.most_common()),
        "mmap_members": formats.get("MMAP", 0), "mmap_containers": mmap_containers, "mmap_dimensions": dict(dims.most_common(24)),
        "mmap_formats": dict(mmap_formats.most_common(12)),
        "text_members": text_members, "text_bytes": text_bytes, "text_containers": text_containers,
        "schl_members": formats.get("SCHl", 0), "schl_containers": schl_containers,
        "schl_platforms": dict(schl_platforms.most_common(4)), "schl_codecs": dict(schl_codecs.most_common(8)),
        "nested_terf": nested, "tdb_members": tdb_members, "tdb_unparsed": tdb_unparsed, "unclassified": formats.get("unclassified", 0), "undecodable": undecodable,
        "unclassified_all_depths": sum(sum(c.values()) for c in magic_index.values()),
        "unclassified_magics": [{"magic": h, "members": sum(c.values()), "containers": [n for n, _ in c.most_common(6)]}
                                for h, c in sorted(magic_index.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:48]],
        "archives": len(archives), "archive_entries": archive_entries, "archive_member_kinds": dict(archive_kinds.most_common(24)),
        "archive_extensions": dict(archive_exts.most_common(16)), "archive_refpack_members": archive_refpack, "archive_shps_members": archive_shps,
    }


def map_disc(iso_path: Path, *, label: str = "", hash_image: bool = False,
             progress: Callable[[str], None] = lambda line: None) -> Dict[str, Any]:
    started = time.time()
    image = iso.open_image(iso_path)
    identity = iso.boot_identity(image)
    summary = iso.summarise(image)
    boot_entry = iso.find(image, "/" + identity["boot_file"]) if identity.get("boot_file") else None
    elf = iso.read_file(image, boot_entry) if boot_entry else b""
    identity["pcsx2_crc"] = ps2_elf.pcsx2_crc(elf) if elf[:4] == b"\x7fELF" else None
    if hash_image:
        digest = hashlib.sha256()
        with open(iso_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 22), b""):
                digest.update(chunk)
        identity["image_sha256"] = digest.hexdigest()
    files: List[Dict[str, Any]] = []
    containers: Dict[str, Any] = {}
    archives: Dict[str, Any] = {}
    databases: Dict[str, Any] = {}
    preloads: Dict[str, Any] = {}
    executables: Dict[str, Any] = {}
    schemas: Dict[str, Dict[str, Any]] = {}
    kinds: Counter = Counter()
    magic_index: Dict[str, Counter] = {}
    with open(iso_path, "rb") as handle:
        for entry in iso.iter_entries(image):
            if entry.is_dir:
                continue
            extent = _Extent(handle, image, entry)
            try:
                head = extent.read(0, min(HEAD_BYTES, entry.length))
            except (MapError, OSError) as error:
                files.append({"path": entry.path, "size": entry.length, "lba": entry.lba, "kind": "unreadable", "note": str(error)[:120]})
                kinds["unreadable"] += 1
                continue
            kind = identify_head(head, entry.path)
            kinds[kind] += 1
            record: Dict[str, Any] = {"path": entry.path, "size": entry.length, "lba": entry.lba, "kind": kind}
            if kind.startswith("other:") or kind in ("zero-head", "TEXT"):
                hint = ext_hint(entry.path)
                if hint:
                    record["hint"] = hint
            if kind == "VC-pack":
                record["note"] = VC_PACK_NOTE
            files.append(record)
            if kind == "TERF":
                progress(f"container {entry.path} ({entry.length:,} bytes)")
                length, short_by = container_span(extent)
                view: Optional[_View] = None
                try:
                    view = extent.view(length)
                    mapped = map_terf(view.data, schemas, magic_index=magic_index, origin=entry.path.rsplit("/", 1)[-1])
                    mapped["iso_length"] = entry.length
                    if short_by:
                        mapped["iso_short_by"] = short_by
                        mapped["mapped_length"] = length
                    containers[entry.path] = mapped
                except (ea_terf.TerfError, MapError, ValueError, OSError, struct.error) as error:
                    containers[entry.path] = {"error": str(error)[:160], "iso_length": entry.length}
                finally:
                    if view is not None:
                        view.close()
            elif kind == "BIGF":
                progress(f"archive {entry.path} ({entry.length:,} bytes)")
                try:
                    archives[entry.path] = map_bigf(extent, schemas, magic_index=magic_index, origin=entry.path.rsplit("/", 1)[-1])
                except (MapError, struct.error, ValueError, OSError) as error:
                    archives[entry.path] = {"error": str(error)[:160]}
            elif kind == "TDB":
                try:
                    schema = tdb_schema(extent.read(0, entry.length))
                    databases[entry.path] = {"schema": _record_schema(schema, schemas), "tables": [(t["name"], t.get("records")) for t in schema["tables"]]}
                except (MapError, struct.error) as error:
                    databases[entry.path] = {"error": str(error)[:160]}
            elif kind == "QL01":
                try:
                    preloads[entry.path] = map_qkl(extent.read(0, entry.length))
                except (MapError, struct.error) as error:
                    preloads[entry.path] = {"error": str(error)[:160]}
            elif kind == "ELF":
                try:
                    info = elf_info(extent.read(0, min(32, entry.length)))
                    info["size"] = entry.length
                    info["sha256"] = _sha256_extent(extent) if entry.length <= (64 << 20) else None
                    executables[entry.path] = info
                except (MapError, struct.error) as error:
                    executables[entry.path] = {"error": str(error)[:160]}
    totals = totals_of(containers, archives, magic_index)
    return {
        "schema": SCHEMA, "label": label, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "image": {"name": iso_path.name, "size": iso_path.stat().st_size, **{k: summary[k] for k in ("sector_size", "layout", "volume_id", "volume_blocks", "files", "directories", "declared_file_bytes") if k in summary}},
        "identity": {k: identity.get(k) for k in ("serial", "boot_file", "boot_sha256", "boot_size", "pcsx2_crc", "image_sha256")},
        "kinds": dict(kinds.most_common()), "files": files, "containers": containers, "archives": archives, "databases": databases,
        "preloads": preloads, "executables": executables, "schemas": schemas, "totals": totals,
        "seconds": round(time.time() - started, 1),
    }


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------
def _top(d: Optional[Dict[str, Any]], limit: Optional[int] = None) -> List[Tuple[str, Any]]:
    """Items of a count dictionary by descending count then key -- the JSON on disk is key-sorted, so order is restored here."""
    items = sorted((d or {}).items(), key=lambda kv: (-(kv[1] if isinstance(kv[1], int) else 0), str(kv[0])))
    return items if limit is None else items[:limit]


def _fmt_counts(d: Optional[Dict[str, Any]], limit: Optional[int] = None) -> str:
    return ", ".join(f"{k} {v}" for k, v in _top(d, limit))


def render_markdown(m: Dict[str, Any]) -> str:
    ident = m.get("identity", {}); img = m.get("image", {})
    containers = m.get("containers", {}); archives = m.get("archives", {}); databases = m.get("databases", {})
    sizes = {f["path"]: f["size"] for f in m.get("files", [])}
    totals = m.get("totals") or totals_of(containers, archives)
    out = [f"# Disc map — {m.get('label') or img.get('name')} ({ident.get('serial')})", "",
           f"Generated {m.get('generated_utc')} by `tools/owner/ea_disc_map.py` ({m.get('schema', SCHEMA)}), read-only, in {m.get('seconds')} s. "
           "Counts, names, sizes and digests only; no game bytes.", "",
           "## Identity", "", "| field | value |", "|---|---|",
           f"| image | `{img.get('name')}` — {img.get('size', 0):,} bytes, {img.get('files')} files / {img.get('directories')} dirs, sector {img.get('sector_size')}{' (' + img['layout'] + ')' if img.get('layout') and img.get('sector_size') != 2048 else ''} |",
           f"| boot file / serial | `{ident.get('boot_file')}` / **{ident.get('serial')}** |",
           f"| boot ELF | {ident.get('boot_size'):,} bytes, sha256 `{ident.get('boot_sha256')}`, PCSX2 CRC `{ident.get('pcsx2_crc')}` |" if ident.get("boot_size") else "| boot ELF | not found |",
           f"| whole image sha256 | `{ident.get('image_sha256') or 'not hashed (run with --hash-image)'}` |", "",
           "## File kinds", "", "| kind | files |", "|---|---:|"]
    out += [f"| {k} | {v} |" for k, v in m.get("kinds", {}).items()]
    out += ["", "## Totals (the numbers a page quotes)", "", "| measure | value |", "|---|---|",
            f"| TERF containers | {totals['containers']} ({len(totals['containers_refused'])} refused; {totals.get('containers_iso_short', 0)} recorded short in ISO9660 and read to their declared length) |",
            f"| chains | {_fmt_counts(totals['chains'])} |",
            f"| alignments | {_fmt_counts(totals['alignments'])} |",
            f"| members (level 1) | {totals['members']:,} |",
            f"| codecs | {_fmt_counts(totals['codecs'])} |",
            f"| decompressed formats | {_fmt_counts(totals['formats'])} |",
            f"| MMAP members | {totals['mmap_members']:,} across {totals['mmap_containers']} containers |",
            f"| MMAP dimensions (top 10, format 0x400 excluded) | {', '.join(f'{k} ×{v}' for k, v in _top(totals['mmap_dimensions'], 10))} |",
            f"| MMAP version / format id | {_fmt_counts(totals.get('mmap_formats', {}))} |",
            f"| TEXT members | {totals['text_members']:,} ({totals['text_bytes']:,} bytes) in {len(totals.get('text_containers', []))} containers |",
            f"| SCHl members | {totals['schl_members']:,} in {len(totals['schl_containers'])} containers: {', '.join('`' + p + '`' for p in totals['schl_containers'][:8])}{' …' if len(totals['schl_containers']) > 8 else ''} |",
            f"| SCHl platform / codec ids (PT header, as vgmstream reads it) | {_fmt_counts(totals.get('schl_platforms', {}))} / {_fmt_counts(totals.get('schl_codecs', {}))} |",
            f"| nested TERF | {totals['nested_terf']:,} |",
            f"| TDB members | {totals['tdb_members']:,} ({totals.get('tdb_unparsed', 0)} not the v8 layout); bare TDB files {len(databases)}; distinct schema shapes {len(m.get('schemas', {}))} |",
            f"| unclassified / undecodable members | {totals['unclassified']:,} / {totals['undecodable']:,} (level 1); unclassified at every depth {totals.get('unclassified_all_depths', totals['unclassified']):,} |",
            f"| EA BIG archives | {totals['archives']} holding {totals['archive_entries']:,} entries; RefPack-packed {totals['archive_refpack_members']:,}; SHPS {totals['archive_shps_members']:,} |"]
    out += ["", "## Containers (TERF)", "", "| path | bytes | chain | align | members | codecs | decompressed formats | MMAP sizes (top) | TEXT | TDB members | notes |", "|---|---:|---|---:|---:|---|---|---|---:|---:|---|"]
    for path, c in sorted(containers.items()):
        if "error" in c:
            out.append(f"| `{path}` | {sizes.get(path, 0):,} | — | — | — | — | — | — | — | — | refused: {c['error']} |")
            continue
        codecs = _fmt_counts(c.get("codecs", {}))
        formats = ", ".join(f"{k} {v}" for k, v in sorted(c.get("formats", {}).items(), key=lambda kv: -kv[1]))
        mm = ", ".join(f"{k} ×{v}" for k, v in _top(c.get("mmap_dimensions"), 4))
        notes = []
        if c.get("nested_terf"):
            inner = _fmt_counts(c.get("nested_formats", {}), 5)
            notes.append(f"{c['nested_terf']} nested TERF" + (f" (depth {c['nested_depth_max']})" if c.get("nested_depth_max", 0) > 1 else "") + (f" holding {inner}" if inner else "") + (f"; {c['nested_tdb_members']} TDB inside" if c.get("nested_tdb_members") else ""))
        if c.get("undecodable"): notes.append(f"{c['undecodable']} undecodable")
        if c.get("layout_violations"): notes.append(f"{len(c['layout_violations'])} layout violations")
        if c.get("iso_short_by"): notes.append(f"ISO9660 record {c['iso_short_by']:,} bytes short; read to declared length")
        elif c.get("size_mismatch"): notes.append(f"size mismatch {c['size_mismatch']:+,}")
        if c.get("mmap_format_0x400"): notes.append(f"{c['mmap_format_0x400']} MMAP format 0x400 (1×3, excluded from sizes)")
        if c.get("schl"): notes.append("SCHl " + _fmt_counts(c["schl"].get("platforms", {})) + " codec " + _fmt_counts(c["schl"].get("codecs", {}), 3))
        ms = c.get("member_sizes")
        if ms and ms.get("distinct", 99) <= 12 and c.get("members", 0) >= 100 and ms.get("max", 0) <= 256:
            notes.append(f"fixed-size records {ms['min']}–{ms['max']} B ({ms['distinct']} sizes)")
        out.append(f"| `{path}` | {sizes.get(path, 0):,} | {c.get('chain')} | {c.get('alignment')} | {c.get('members')} | {codecs} | {formats} | {mm} | {c.get('text_members', 0)} | {len(c.get('tdb_members', []))} | {'; '.join(notes)} |")
    with_tdb = [(p, c) for p, c in sorted(containers.items()) if c.get("tdb_members")]
    if with_tdb:
        out += ["", "## Databases inside containers", "", "| container | TDB members | schema → members | tables (records) of the first member per schema |", "|---|---:|---|---|"]
        for path, c in with_tdb:
            per: Dict[str, List[Dict[str, Any]]] = {}
            for t in c["tdb_members"]:
                per.setdefault(t.get("schema", "error"), []).append(t)
            sig_cells = "; ".join((f"`{sig}` ×{len(ts)}" if sig != "error" else f"unparsed ×{len(ts)} ({ts[0].get('error', '')[:60]})") for sig, ts in per.items())
            first_cells = " / ".join(", ".join(f"{n} ({r})" for n, r in ts[0].get("tables", [])[:10]) + (" …" if len(ts[0].get("tables", [])) > 10 else "") for ts in per.values() if ts[0].get("tables"))
            out.append(f"| `{path}` | {len(c['tdb_members'])} | {sig_cells} | {first_cells} |")
    if archives:
        out += ["", "## Archives (EA BIG)", "", "| path | bytes | format / size field | entries | member kinds (after RefPack) | extensions | RefPack | SHPS (images) | nested BIG (entries) | notes |", "|---|---:|---|---:|---|---|---:|---|---|---|"]
        for path, a in sorted(archives.items()):
            if "error" in a:
                out.append(f"| `{path}` | {sizes.get(path, 0):,} | — | — | refused: {a['error']} | | | | | |"); continue
            notes = []
            if a.get("directory_entries"): notes.append(f"{a['directory_entries']} directory entries")
            if a.get("terf_members"): notes.append(f"{len(a['terf_members'])} TERF members mapped")
            if a.get("tdb_members"): notes.append(f"{len(a['tdb_members'])} TDB members")
            if a.get("schl"): notes.append("SCHl " + _fmt_counts(a["schl"].get("platforms", {})) + " codec " + _fmt_counts(a["schl"].get("codecs", {}), 3))
            if a.get("entries") != a.get("entries_read"): notes.append(f"index read {a.get('entries_read')} of {a.get('entries')}")
            nested = f"{a.get('nested_bigf', 0)} ({a.get('nested_entries', 0)})" if a.get("nested_bigf") else "—"
            out.append(f"| `{path}` | {sizes.get(path, 0):,} | {a.get('format')} / {a.get('size_field', '?')} | {a.get('entries')} | {_fmt_counts(a.get('member_kinds', {}), 8)} | {_fmt_counts(a.get('extensions', {}), 8)} | {a.get('refpack_members', 0)} | {a.get('shps_members', 0)} ({a.get('shps_images', 0)}) | {nested} | {'; '.join(notes)} |")
    if databases:
        out += ["", "## Bare databases (TDB files)", "", "| path | schema | tables (records) |", "|---|---|---|"]
        for path, d in sorted(databases.items()):
            if "error" in d:
                out.append(f"| `{path}` | — | refused: {d['error']} |")
            else:
                out.append(f"| `{path}` | `{d['schema']}` | " + ", ".join(f"{n} ({r})" for n, r in d["tables"][:24]) + (" …" if len(d["tables"]) > 24 else "") + " |")
    if m.get("preloads"):
        out += ["", "## Preload copies (QL01)", "", "Each `.QKL` carries byte copies of container directories (kind 0) and of members' stored bytes (kind 1); an edit to a member named here must be applied in the QKL too.", "",
                "| path | bytes | containers named | entries | header copies | member copies | distinct offsets | most-copied containers |", "|---|---:|---:|---:|---:|---:|---:|---|"]
        for path, q in sorted(m["preloads"].items()):
            if "error" in q:
                out.append(f"| `{path}` | {sizes.get(path, 0):,} | refused: {q['error']} | | | | | |"); continue
            top = _fmt_counts(q.get("copies_per_file"), 6)
            out.append(f"| `{path}` | {sizes.get(path, 0):,} | {q.get('files')} | {q.get('entries')} | {q.get('header_copies')} | {q.get('member_copies')} | {q.get('distinct_offsets')} | {top} |")
    if m.get("executables"):
        by_type: Counter = Counter(v.get("type", "error") for v in m["executables"].values())
        out += ["", "## Executables (ELF / IRX)", "", f"{len(m['executables'])} files: " + _fmt_counts(dict(by_type)) + ".", "",
                "| path | bytes | type | entry | sha256 |", "|---|---:|---|---|---|"]
        for path, e in sorted(m["executables"].items()):
            if "error" in e:
                out.append(f"| `{path}` | {sizes.get(path, 0):,} | refused: {e['error']} | | |"); continue
            out.append(f"| `{path}` | {e.get('size', 0):,} | {e.get('type')} | {('0x%08x' % e['entry']) if e.get('entry') is not None else '—'} | `{e.get('sha256') or '—'}` |")
    out += ["", "## Database schemas (each distinct table/field shape once)", ""]
    for sig, s in sorted(m.get("schemas", {}).items()):
        out.append(f"### schema `{sig}` — {s['endian']}-endian v{s['version']}, {len(s['tables'])} table(s)")
        out.append("")
        for t in s["tables"]:
            fields = ", ".join(f"{f['name']}:{f['type']}{f['bits']}" for f in t.get("fields", []))
            out.append(f"- **{t.get('name')}** — {t.get('record_bytes')} B/rec ({t.get('record_bits')} bits), max {t.get('max_records')}, {len(t.get('fields', []))} fields: {fields}")
        out.append("")
    magics = totals.get("unclassified_magics") or []
    if not magics:
        heads: Counter = Counter(); where: Dict[str, set] = {}
        for path, c in containers.items():
            for head, n in (c.get("unclassified_heads") or {}).items():
                heads[head] += n; where.setdefault(head, set()).add(path.rsplit("/", 1)[-1])
        magics = [{"magic": h, "members": n, "containers": sorted(where[h])[:6]} for h, n in heads.most_common(20)]
    if magics:
        out += ["", "## Unclassified member magics (first 4 bytes after decompression, every nesting depth)", "",
                "| magic | members | containers (up to 6) |", "|---|---:|---|"]
        for row in magics[:48]:
            out.append(f"| `{row['magic']}` | {row['members']} | {', '.join(row['containers'])} |")
    others = [f for f in m.get("files", []) if f["kind"].startswith("other:") or f["kind"] in ("zero-head", "VC-pack")]
    if others:
        out += ["", "## Files with an unrecognised magic", "", "| path | bytes | first bytes | hint (by extension or path, [A]) |", "|---|---:|---|---|"]
        out += [f"| `{f['path']}` | {f['size']:,} | `{f['kind'][6:] if f['kind'].startswith('other:') else f['kind']}` | {f.get('hint') or f.get('note') or ''} |" for f in others[:80]]
        if len(others) > 80: out.append(f"| … {len(others) - 80} more | | | |")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# --compare and --summary
# --------------------------------------------------------------------------
def _sizes_of(m: Dict[str, Any]) -> Dict[str, int]:
    return {f["path"]: f["size"] for f in m.get("files", [])}


def _delta(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    keys = sorted(set(a) | set(b), key=lambda k: -(abs((b.get(k) or 0) - (a.get(k) or 0))))
    parts = [f"{k} {a.get(k, 0)}→{b.get(k, 0)}" for k in keys if a.get(k) != b.get(k)]
    return ", ".join(parts[:8]) + (" …" if len(parts) > 8 else "")


def render_compare(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    la = a.get("label") or a.get("image", {}).get("name"); lb = b.get("label") or b.get("image", {}).get("name")
    ia, ib = a.get("identity", {}), b.get("identity", {})
    out = [f"# Disc compare — {la} vs {lb}", "", "| field | A | B |", "|---|---|---|",
           f"| label | {la} | {lb} |", f"| serial | {ia.get('serial')} | {ib.get('serial')} |",
           f"| image bytes | {a.get('image', {}).get('size', 0):,} | {b.get('image', {}).get('size', 0):,} |",
           f"| image sha256 | `{ia.get('image_sha256')}` | `{ib.get('image_sha256')}` |",
           f"| boot ELF sha256 / CRC | `{ia.get('boot_sha256')}` / `{ia.get('pcsx2_crc')}` | `{ib.get('boot_sha256')}` / `{ib.get('pcsx2_crc')}` |",
           f"| files | {len(a.get('files', []))} | {len(b.get('files', []))} |", ""]
    sa, sb = _sizes_of(a), _sizes_of(b)
    added = sorted(set(sb) - set(sa)); removed = sorted(set(sa) - set(sb)); resized = sorted(p for p in set(sa) & set(sb) if sa[p] != sb[p])
    out += ["## Files", "", f"added {len(added)}, removed {len(removed)}, size changed {len(resized)}, unchanged size {len(set(sa) & set(sb)) - len(resized)}", ""]
    for title, paths, fmt in (("Added", added, lambda p: f"`{p}` ({sb[p]:,} B)"), ("Removed", removed, lambda p: f"`{p}` ({sa[p]:,} B)"),
                              ("Size changed", resized, lambda p: f"`{p}` {sa[p]:,} → {sb[p]:,} ({sb[p] - sa[p]:+,})")):
        if paths:
            out += [f"### {title}", ""] + [f"- {fmt(p)}" for p in paths[:60]] + ([f"- … {len(paths) - 60} more"] if len(paths) > 60 else []) + [""]
    ca, cb = a.get("containers", {}), b.get("containers", {})
    changed = []
    for path in sorted(set(ca) & set(cb)):
        x, y = ca[path], cb[path]
        if "error" in x or "error" in y:
            if x.get("error") != y.get("error"):
                changed.append((path, f"refusal: {x.get('error', 'none')} → {y.get('error', 'none')}"))
            continue
        bits = []
        if x.get("members") != y.get("members"): bits.append(f"members {x.get('members')}→{y.get('members')}")
        if x.get("chain") != y.get("chain"): bits.append(f"chain {x.get('chain')}→{y.get('chain')}")
        d = _delta(x.get("codecs", {}), y.get("codecs", {}))
        if d: bits.append("codecs: " + d)
        d = _delta(x.get("formats", {}), y.get("formats", {}))
        if d: bits.append("formats: " + d)
        d = _delta(x.get("mmap_dimensions", {}), y.get("mmap_dimensions", {}))
        if d: bits.append("MMAP sizes: " + d)
        if len(x.get("tdb_members", [])) != len(y.get("tdb_members", [])): bits.append(f"TDB members {len(x.get('tdb_members', []))}→{len(y.get('tdb_members', []))}")
        if x.get("text_bytes") != y.get("text_bytes"): bits.append(f"TEXT bytes {x.get('text_bytes', 0):,}→{y.get('text_bytes', 0):,}")
        if (x.get("iso_short_by") or 0) != (y.get("iso_short_by") or 0): bits.append(f"ISO9660 short by {x.get('iso_short_by', 0)}→{y.get('iso_short_by', 0)}")
        if bits and sa.get(path) == sb.get(path): bits.append("(same byte size)")
        if bits: changed.append((path, "; ".join(bits)))
    same = len(set(ca) & set(cb)) - len(changed)
    out += ["## Containers (TERF)", "", f"added {len(set(cb) - set(ca))}, removed {len(set(ca) - set(cb))}, changed {len(changed)}, identical in every mapped count {same}", ""]
    if changed:
        out += ["| container | what changed (A → B) |", "|---|---|"] + [f"| `{p}` | {what} |" for p, what in changed] + [""]
    aa, ab = a.get("archives", {}), b.get("archives", {})
    arch_changed = [(p, _delta(aa[p].get("member_kinds", {}), ab[p].get("member_kinds", {})) or f"entries {aa[p].get('entries')}→{ab[p].get('entries')}")
                    for p in sorted(set(aa) & set(ab)) if aa[p].get("entries") != ab[p].get("entries") or aa[p].get("member_kinds") != ab[p].get("member_kinds")]
    if aa or ab:
        out += ["## Archives (EA BIG)", "", f"added {len(set(ab) - set(aa))}, removed {len(set(aa) - set(ab))}, changed {len(arch_changed)}", ""]
        out += [f"- `{p}`: {what}" for p, what in arch_changed[:40]] + ([""] if arch_changed else [])
    da, db = a.get("databases", {}), b.get("databases", {})
    db_changed = [p for p in sorted(set(da) & set(db)) if da[p] != db[p]]
    out += ["## Bare databases and schemas", "", f"bare TDB files: added {len(set(db) - set(da))}, removed {len(set(da) - set(db))}, changed {len(db_changed)}" + (": " + ", ".join(f"`{p}`" for p in db_changed) if db_changed else ""),
            f"schema shapes: only in A {len(set(a.get('schemas', {})) - set(b.get('schemas', {})))}, only in B {len(set(b.get('schemas', {})) - set(a.get('schemas', {})))}, shared {len(set(a.get('schemas', {})) & set(b.get('schemas', {})))}", ""]
    ta = a.get("totals") or totals_of(ca, aa); tb = b.get("totals") or totals_of(cb, ab)
    out += ["## Totals", "", "| measure | A | B |", "|---|---:|---:|"]
    for key in ("containers", "members", "mmap_members", "text_members", "text_bytes", "schl_members", "nested_terf", "tdb_members", "unclassified", "archives", "archive_entries"):
        out.append(f"| {key} | {ta.get(key, 0):,} | {tb.get(key, 0):,} |")
    out.append(f"| formats | {_fmt_counts(ta.get('formats', {}))} | {_fmt_counts(tb.get('formats', {}))} |")
    return "\n".join(out) + "\n"


SUMMARY_COLUMNS = ("disc", "serial", "files", "containers", "refused", "members", "archives", "archive entries", "schemas", "MMAP", "SCHl", "TEXT", "TDB members", "nested TERF", "unclassified", "seconds", "image sha256")


def summary_rows(maps: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for m in maps:
        t = m.get("totals") or totals_of(m.get("containers", {}), m.get("archives", {}))
        rows.append({"disc": m.get("label") or m.get("image", {}).get("name"), "serial": m.get("identity", {}).get("serial"),
                     "files": len(m.get("files", [])), "containers": t["containers"], "refused": len(t["containers_refused"]), "members": t["members"],
                     "archives": t["archives"], "archive entries": t["archive_entries"], "schemas": len(m.get("schemas", {})),
                     "MMAP": t["mmap_members"], "SCHl": t["schl_members"], "TEXT": t["text_members"], "TDB members": t["tdb_members"],
                     "nested TERF": t["nested_terf"], "unclassified": t["unclassified"], "seconds": m.get("seconds"),
                     "image sha256": m.get("identity", {}).get("image_sha256") or "—"})
    return sorted(rows, key=lambda r: (str(r["serial"]), str(r["disc"])))


def render_summary(maps: Sequence[Dict[str, Any]]) -> str:
    rows = summary_rows(maps)
    out = [f"# Fleet summary — {len(rows)} disc map(s)", "", "| " + " | ".join(SUMMARY_COLUMNS) + " |",
           "|" + "|".join("---:" if c not in ("disc", "serial", "image sha256") else "---" for c in SUMMARY_COLUMNS) + "|"]
    for r in rows:
        cells = []
        for c in SUMMARY_COLUMNS:
            v = r[c]
            cells.append(f"`{v}`" if c == "image sha256" and v != "—" else (f"{v:,}" if isinstance(v, int) else str(v)))
        out.append("| " + " | ".join(cells) + " |")
    out += ["", f"Totals over the fleet: {sum(r['containers'] for r in rows):,} containers, {sum(r['members'] for r in rows):,} members, "
            f"{sum(r['MMAP'] for r in rows):,} MMAP, {sum(r['SCHl'] for r in rows):,} SCHl, {sum(r['TEXT'] for r in rows):,} TEXT, "
            f"{sum(r['unclassified'] for r in rows):,} unclassified, {sum(r['archives'] for r in rows):,} archives."]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# --page: the disc-map page skeleton, mechanical parts filled in
# --------------------------------------------------------------------------
#: Container-name glossary: (regex on the file name, studio pages, what it is for, grade).  [S] rows
#: come from the owner's Madden 09 census (docs/madden09-container-census.md §1, §6, App. A) or
#: the Madden 04 scoping; [A] rows are the natural reading of the name and nothing more.
GLOSSARY: Tuple[Tuple[str, Tuple[str, ...], str, str], ...] = (
    (r"^UNIFORMS?$", ("Uniforms & Equipment", "All Textures"), "uniform / kit textures", "S"),
    (r"^TATTOOS$", ("Uniforms & Equipment", "All Textures"), "tattoo textures", "S"),
    (r"^UIS_GEAR$", ("Uniforms & Equipment", "All Textures"), "equipment UI textures", "A"),
    (r"^PLYRFACE$", ("Names, Numbers & Faces", "All Textures"), "player face textures", "S"),
    (r"^COACFACE$", ("Names, Numbers & Faces", "All Textures"), "coach face textures", "S"),
    (r"^COACHES$", ("Names, Numbers & Faces", "All Textures"), "coach models and textures", "S"),
    (r"^PLADATA$", ("Uniforms & Equipment", "All Textures"), "player models and textures", "S"),
    (r"^FANDATA$", ("Presentation", "All Textures"), "crowd models and textures", "S"),
    (r"^DB_TEAMS$", ("Names, Numbers & Faces", "Text & Team Identity"), "per-team roster databases", "S"),
    (r"^TEMPLATE$", ("Names, Numbers & Faces",), "fresh-franchise template databases", "S"),
    (r"^GAMEDATA$", ("Playbooks & Plays", "Names, Numbers & Faces"), "playbook databases (Madden 09: members 0–102) plus a few UI textures", "S"),
    (r"^LEAGUE$", ("Names, Numbers & Faces", "Text & Team Identity"), "league databases", "A"),
    (r"^STADIUMS$", ("Stadiums", "All Textures"), "stadium geometry and textures", "S"),
    (r"^STADATA$", ("Stadiums", "Field Art & Create-Team Art"), "stadium art and geometry", "S"),
    (r"^STAD_CR$", ("Stadiums",), "stadium geometry (create-a-stadium)", "A"),
    (r"^FIELDART$", ("Field Art & Create-Team Art",), "field geometry and field-art textures", "S"),
    (r"^(STRY|STORY)", ("Text & Team Identity", "Menus & UI"), "story / news generator text", "S"),
    (r"^OSDKSTRN$", ("Text & Team Identity",), "OSDK online strings", "A"),
    (r"^LOADDATA$", ("Presentation", "Menus & UI"), "loading-screen textures and text", "S"),
    (r"^(SPCH|CMNT|EATRX|FESND)", ("Audio",), "speech / commentary audio streams", "S"),
    (r"^SPCHHDRS$", ("Audio",), "speech header records (small fixed-size, no magic)", "S"),
    (r"^BGM$", ("Audio", "Presentation"), "music streams", "S"),
    (r"^SOUNDDAT$", ("Audio",), "sound banks and effects", "S"),
    (r"^(MOVIEDAT|UIS_FMV|UIS_MMF)$", ("Presentation",), "movie streams", "S"),
    (r"^ANIMDATA$", ("Gameplay",), "animation data (skeletons, event tables, unclassified blobs)", "S"),
    (r"^CAFE", ("Menus & UI",), "EA Nation / online dashboard nested archives", "S"),
    (r"^(UIS_FONT|FONTS)$", ("Menus & UI", "Text & Team Identity"), "fonts", "S"),
    (r"^UIS_(TMLO|CTLO|TMLL|SLIV|TMFN|TMLF)$", ("Field Art & Create-Team Art", "Menus & UI"), "team logo / team art UI textures", "A"),
    (r"^UIS_", ("Menus & UI", "All Textures"), "UI textures", "S"),
    (r"^ONLINE$", ("Gameplay",), "online executable and resources", "S"),
    (r"^ICONS$", ("Menus & UI",), "icons", "A"),
    (r"^CREDITS$", ("Menus & UI",), "credits", "A"),
    (r"^MSCTDATA$", ("Presentation", "All Textures"), "mascot models and textures", "A"),
    (r"^(HEISDATA|SUPERSIM|EXAMS|JERSEY)$", ("Text & Team Identity",), "mode data (by name)", "A"),
)
#: Archive-name glossary, [S] rows from the owner's Madden 09 census §5.
ARCHIVE_GLOSSARY: Tuple[Tuple[str, str, str], ...] = (
    (r"^BUNDLE\.BIG$", "EA Nation dashboard UI: 70 nested archives of Apt screens, SHPS banks and IOP objects", "S"),
    (r"^LOC_PS2\.BIG$", "EA Nation localisation tables (text)", "S"),
    (r"^MODULES3?\.BIG$", "IOP modules (IRX) for the online stack", "S"),
    (r"HDR\.BIG$", "speech header records, no magic (by name)", "A"),
    (r"DAT\.BIG$", "speech / audio streams (by name)", "A"),
    (r"^GHEAD\.BIG$", "head textures (by name)", "A"),
    (r"^PORTRAIT\.BIG$", "portrait textures (by name)", "A"),
    (r"^UNIFORMS?\.BIG$", "uniform textures (by name)", "A"),
    (r"^MODELS\.BIG$", "models and their textures (by name)", "A"),
    (r"^(STADIUMS?|BKGNDS)\.BIG$", "stadium / background art (by name)", "A"),
)
PAGE_ROWS = ("Uniforms & Equipment", "Names, Numbers & Faces", "Text & Team Identity", "Field Art & Create-Team Art", "Stadiums",
             "Presentation", "Menus & UI", "The Crib", "Audio", "Gameplay", "Playbooks & Plays", "All Textures", "Saves")
#: The rung a decompressed format earns today, and what lifts it (the runbook's mechanical rules).
FORMAT_RUNGS: Dict[str, Tuple[str, str]] = {
    "MMAP": ("read-only-mapped", "MMAP→PNG decoder (none exists for EA titles yet)"),
    "TDB": ("read-only-mapped (schema + rows)", "offline TDB writer with the four CRCs and an independent verifier"),
    "TEXT": ("read-only-mapped", "TEXT decoder"),
    "SCHl": ("read-only-mapped", "SCHl decoder; never a writer (no public encoder)"),
    "BNKl": ("read-only-mapped", "sound-bank decoder"),
    "SMF": ("read-only-mapped", "SMF geometry reader"),
    "DMF": ("read-only-mapped", "DMF model reader"),
    "MPCh": ("read-only-mapped", "movie decoder"),
    "FNTS": ("read-only-mapped", "font decoder"),
    "SHPS": ("read-only-mapped", "FSH/SHPS decoder"),
}


def _glossary(name: str) -> Tuple[Tuple[str, ...], str, str]:
    for pattern, pages, phrase, grade in GLOSSARY:
        if re.match(pattern, name):
            return pages, phrase, grade
    return (), "", ""


def render_page(m: Dict[str, Any], today: Optional[str] = None) -> str:
    today = today or time.strftime("%Y-%m-%d", time.gmtime())
    ident = m.get("identity", {}); img = m.get("image", {}); label = m.get("label") or img.get("name", "")
    containers = m.get("containers", {}); archives = m.get("archives", {}); databases = m.get("databases", {})
    sizes = _sizes_of(m); totals = m.get("totals") or totals_of(containers, archives)
    kinds = m.get("kinds", {})
    title = re.sub(r"\s*\((USA|Europe|Japan)\)\s*$", "", label) or label
    region = re.search(r"\((USA|Europe|Japan)\)", label)
    out = [f"# {title} ({region.group(1) if region else 'USA'}) — PlayStation 2 disc map", "",
           f"Mapped {today} with `tools/owner/ea_disc_map.py` ({m.get('schema', SCHEMA)}), read-only. Source: `{ident.get('serial')}.<label>.map.json` / `.map.md` (counts below are copied from its Totals table by `--page`).",
           "Grades: [M] measured by the mapper, [S] sourced (cite), [A] assumed. Every cell not marked otherwise is [M].", "",
           "## Identity [M]", "", "| field | value |", "|---|---|",
           f"| image | `{img.get('name')}`, {img.get('size', 0):,} bytes, {img.get('files')} files / {img.get('directories')} dirs{', raw CD ' + str(img.get('sector_size')) + '-byte sectors' if img.get('sector_size') not in (None, 2048) else ''} |",
           f"| boot file / serial | `{ident.get('boot_file')}` / **{ident.get('serial')}** |",
           f"| boot ELF | {ident.get('boot_size') or 0:,} bytes, sha256 `{ident.get('boot_sha256')}`, PCSX2 CRC `{ident.get('pcsx2_crc')}` |",
           f"| whole image sha256 | `{ident.get('image_sha256') or 'not hashed'}` |", "",
           "## What is on the disc [M]", "", "| kind | files | notes |", "|---|---:|---|"]
    other_kinds = {k: v for k, v in kinds.items() if k.startswith("other:")}
    named = [(k, v) for k, v in kinds.items() if not k.startswith("other:")]
    for k, v in named:
        note = ""
        if k == "TERF":
            note = f"chains: {_fmt_counts(totals['chains'])}; alignments: {_fmt_counts(totals['alignments'])}"
        elif k == "TDB":
            note = ", ".join(f"`{p}`" for p in sorted(databases))
        elif k == "ELF":
            ex = m.get("executables", {}); note = _fmt_counts(dict(Counter(e.get("type", "?") for e in ex.values()))) if ex else "boot ELF + IOP modules"
        elif k == "BIGF":
            note = f"{totals['archive_entries']:,} entries; RefPack-packed {totals['archive_refpack_members']:,}; SHPS {totals['archive_shps_members']:,}"
        elif k == "QL01":
            note = "preload copies of container directories and members (see the map's QL01 table)"
        elif k == "VC-pack":
            note = VC_PACK_NOTE
        out.append(f"| {k} | {v} | {note} |")
    if other_kinds:
        out.append(f"| other (unrecognised magic) | {sum(other_kinds.values())} | {len(other_kinds)} distinct heads: {', '.join(k[6:] for k in list(other_kinds)[:12])}{' …' if len(other_kinds) > 12 else ''} (hints by extension in the map, [A]) |")
    if containers:
        out += ["", "### Containers that matter (largest 12 by bytes, plus every container holding TDB or TEXT) [M]", "",
                "| container | bytes | chain | members | codecs | decompressed formats | what it is for |", "|---|---:|---|---:|---|---|---|"]
        ok = {p: c for p, c in containers.items() if "error" not in c}
        chosen = sorted(ok, key=lambda p: -sizes.get(p, 0))[:12]
        chosen += [p for p in sorted(ok) if p not in chosen and (ok[p].get("tdb_members") or ok[p].get("text_members"))]
        for path in chosen:
            c = ok[path]; name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            _, phrase, grade = _glossary(name)
            purpose = f"{phrase} [{grade}]" if phrase else "<what it is for> [A]"
            formats = ", ".join(f"{k} {v}" for k, v in sorted(c.get("formats", {}).items(), key=lambda kv: -kv[1]))
            out.append(f"| `{path}` | {sizes.get(path, 0):,} | {c.get('chain', '').replace(' -> ', '→')} | {c.get('members')} | {_fmt_counts(c.get('codecs', {}))} | {formats} | {purpose} |")
        refused = totals.get("containers_refused", [])
        if refused:
            out += ["", f"Refused containers ({len(refused)}): " + ", ".join(f"`{p}` ({containers[p].get('error', '')[:80]})" for p in refused)]
    if archives:
        out += ["", "### Archives that matter (largest 12) [M]", "", "| archive | bytes | entries | member kinds (after RefPack) | extensions | RefPack | SHPS (images) | what it is for |", "|---|---:|---:|---|---|---:|---|---|"]
        ok_a = {p: a for p, a in archives.items() if "error" not in a}
        for path in sorted(ok_a, key=lambda p: -sizes.get(p, 0))[:12]:
            a = ok_a[path]; base = path.rsplit("/", 1)[-1].upper()
            purpose = next((f"{phrase} [{grade}]" for pattern, phrase, grade in ARCHIVE_GLOSSARY if re.search(pattern, base)), "<what it is for> [A]")
            out.append(f"| `{path}` | {sizes.get(path, 0):,} | {a.get('entries')} | {_fmt_counts(a.get('member_kinds', {}), 6)} | {_fmt_counts(a.get('extensions', {}), 6)} | {a.get('refpack_members', 0)} | {a.get('shps_members', 0)} ({a.get('shps_images', 0)}) | {purpose} |")
    out += ["", "### Databases [M]", ""]
    if databases or totals.get("tdb_members"):
        out += ["| where | TDB members | schema → members | tables (records) of the first member per schema |", "|---|---:|---|---|"]
        for path, c in sorted(containers.items()):
            if c.get("tdb_members"):
                per: Dict[str, List[Dict[str, Any]]] = {}
                for t in c["tdb_members"]:
                    per.setdefault(t.get("schema", "error"), []).append(t)
                first = " / ".join(", ".join(f"{n} ({r})" for n, r in ts[0].get("tables", [])[:8]) + (" …" if len(ts[0].get("tables", [])) > 8 else "") for ts in per.values() if ts[0].get("tables"))
                out.append(f"| `{path}` | {len(c['tdb_members'])} | {'; '.join((f'`{s}` ×{len(ts)}' if s != 'error' else f'unparsed ×{len(ts)}') for s, ts in per.items())} | {first} |")
        for path, d in sorted(databases.items()):
            if "error" in d:
                out.append(f"| `{path}` | — | refused: {d['error']} | |")
            else:
                out.append(f"| `{path}` | 1 (bare file) | `{d['schema']}` | " + ", ".join(f"{n} ({r})" for n, r in d["tables"][:8]) + (" …" if len(d["tables"]) > 8 else "") + " |")
        shared = sorted({t["name"] for s in m.get("schemas", {}).values() for t in s.get("tables", [])} & {"PLAY", "TEAM", "DCHT", "INJY", "COCH", "SEAI", "SLRI", "PBPL", "PLYS"})
        out += ["", f"Distinct schema shapes: {len(m.get('schemas', {}))}. Table names shared with the Madden 08/09 TDB stack (`PLAY`, `TEAM`, `DCHT`, `INJY`, `COCH`, `SEAI`, `SLRI`, `PBPL`, `PLYS`): {', '.join('`' + t + '`' for t in shared) or 'none'}."]
    else:
        out += ["No EA TDB database was found by the mapper (no bare `.DB`, no TDB member)."]
    out += ["", "### Textures [M]", "",
            f"MMAP members: {totals['mmap_members']:,} across {totals['mmap_containers']} containers; dimensions (disc-wide top 6, format 0x400 excluded): "
            + (", ".join(f"{k} ×{v}" for k, v in _top(totals['mmap_dimensions'], 6)) or "none") + f". MMAP version / format ids: {_fmt_counts(totals.get('mmap_formats', {}))}. "
            + (f"SHPS image banks: {totals['archive_shps_members']:,} inside archives, {kinds.get('SHPS', 0)} loose files. " if totals.get("archive_shps_members") or kinds.get("SHPS") else "")
            + "Faces / kits / UI split: from the container glossary above ([S]/[A] as marked), never from pixels.",
            "", "### Text and audio [M]", "",
            f"TEXT members: {totals['text_members']:,} ({totals['text_bytes']:,} bytes) in {len(totals.get('text_containers', []))} containers. "
            f"SCHl members: {totals['schl_members']:,} in {len(totals['schl_containers'])} containers ({', '.join('`' + p + '`' for p in totals['schl_containers'][:6])}{' …' if len(totals['schl_containers']) > 6 else ''}); "
            f"PT-header platform / codec ids: {_fmt_counts(totals.get('schl_platforms', {})) or '—'} / {_fmt_counts(totals.get('schl_codecs', {})) or '—'} [S: vgmstream ea_schl]. "
            f"Nested TERF: {totals['nested_terf']:,}. Unclassified members: {totals['unclassified']:,} (magic histogram in the map)."]
    # page-by-page, mechanical
    out += ["", "## Page-by-page: what a studio could offer today (rungs as they stand, not as they could be)", "",
            "| page | feeding containers | format | rung today | what lifts it |", "|---|---|---|---|---|"]
    feeding: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {p: [] for p in PAGE_ROWS}
    for path, c in sorted(containers.items()):
        if "error" in c:
            continue
        name = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        pages, _, _ = _glossary(name)
        fmts = c.get("formats", {})
        for page in pages:
            feeding[page].append((path, c))
        if fmts.get("MMAP") and "All Textures" not in pages:
            feeding["All Textures"].append((path, c))
        if fmts.get("TDB") and not pages:
            feeding["Names, Numbers & Faces"].append((path, c))
        if fmts.get("TEXT") and "Text & Team Identity" not in pages and not pages:
            feeding["Text & Team Identity"].append((path, c))
        if fmts.get("SCHl") and "Audio" not in pages:
            feeding["Audio"].append((path, c))
    for path, d in databases.items():
        feeding["Names, Numbers & Faces"].append((path, {"formats": {"TDB": 1}}))
    for page in PAGE_ROWS:
        if page == "The Crib":
            out.append("| The Crib | — | — | honest empty page | not a concept on this disc |"); continue
        if page == "Saves":
            out.append("| Saves | — | — | honest empty page | saves are not the disc |"); continue
        if page == "Gameplay":
            out.append("| Gameplay | executable | R5900 | unknown (code-patch scaffold) | translations |"); continue
        rows = feeding[page]
        if not rows:
            if page == "Playbooks & Plays" and not containers and archives:
                out.append(f"| {page} | not located in the map | — | unknown | a format survey of the archives |"); continue
            out.append(f"| {page} | none found in the map | — | honest empty page | — |"); continue
        fmt_counter: Counter = Counter()
        for _, c in rows:
            for k in c.get("formats", {}):
                if k in FORMAT_RUNGS:
                    fmt_counter[k] += c["formats"][k]
        relevant = [k for k, _ in fmt_counter.most_common() if k in FORMAT_RUNGS][:3]
        rung = "; ".join(sorted({FORMAT_RUNGS[k][0] for k in relevant})) if relevant else "read-only-mapped"
        lifts = "; ".join(FORMAT_RUNGS[k][1] for k in relevant) if relevant else "a format survey"
        lzh1 = any(c.get("codecs", {}).get("LZH1") for _, c in rows)
        if lzh1:
            lifts += "; LZH1 encoder before any rewrite of the LZH1-packed members"
        names = ", ".join(f"`{p}`" for p, _ in rows[:6]) + (f" (+{len(rows) - 6} more)" if len(rows) > 6 else "")
        out.append(f"| {page} | {names} | {', '.join(relevant) or '—'} | {rung} | {lifts} |")
    # writers, mechanical
    data_only = sorted(p for p, c in containers.items() if "error" not in c and "COMP" not in c.get("chain", ""))
    lzh1_containers = sorted(p for p, c in containers.items() if "error" not in c and c.get("codecs", {}).get("LZH1"))
    rle1_only = sorted(p for p, c in containers.items() if "error" not in c and c.get("codecs", {}).get("RLE1") and not c.get("codecs", {}).get("LZH1"))
    comp_stored = sorted(p for p, c in containers.items() if "error" not in c and "COMP" in c.get("chain", "") and set(c.get("codecs", {})) <= {"NONE (stored)"})
    out += ["", "## Writers: what could be rewritten with what exists today [M]/[A]", "",
            f"- `DATA`-chain containers (every member stored): `ea_terf.rewrite_member` exists. {len(data_only)} containers: " + ", ".join(f"`{p}`" for p in data_only[:16]) + (f" (+{len(data_only) - 16} more)" if len(data_only) > 16 else "") + ".",
            f"- `COMP`-chain containers with LZH1 members: read only until an LZH1 encoder exists. {len(lzh1_containers)} containers: " + ", ".join(f"`{p}`" for p in lzh1_containers[:16]) + (f" (+{len(lzh1_containers) - 16} more)" if len(lzh1_containers) > 16 else "") + ".",
            f"- `COMP`-chain containers whose packed members are RLE1 only (encoder exists in `ea_terf`): {len(rle1_only)}" + (": " + ", ".join(f"`{p}`" for p in rle1_only[:8]) if rle1_only else "") + ".",
            f"- `COMP`-chain containers whose members are all stored (rewritable like a `DATA` chain): {len(comp_stored)}" + (": " + ", ".join(f"`{p}`" for p in comp_stored[:8]) if comp_stored else "") + ".",
            "- TDB rows: reader exists; writer needs the four CRCs and a verifier. [A] until built."]
    if archives:
        out.append("- EA BIG archives: no writer in the fork (BIG is not TERF; `ea_terf.rewrite_member` does not apply). [M]")
    if m.get("preloads"):
        out.append(f"- `QL01` preload files ({', '.join('`' + p + '`' for p in sorted(m['preloads']))}) copy container directories and members: any edit to a container they name must be applied there too. [S: census §3]")
    out += ["", "## Open questions (one line each, no speculation)", ""]
    magics = (totals.get("unclassified_magics") or [])[:3]
    for row in magics:
        out.append(f"- Unclassified magic `{row['magic']}` on {row['members']} members in {', '.join(row['containers'][:3])}: what format is it?")
    if totals.get("mmap_formats", {}).get("v2/fmt0x400"):
        out.append(f"- {totals['mmap_formats']['v2/fmt0x400']} MMAP members carry format id 0x400 and declare 1×3: not a texture layout the parser understands.")
    out.append("- <add only questions the map raises; cite the map's row>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# selftest: synthetic bytes only
# --------------------------------------------------------------------------
def _synthetic_tdb(tables: Iterable[Tuple[str, List[Tuple[str, int, int]], int]]) -> bytes:
    """A minimal little-endian TDB v8 with the given (name, [(field, type, bits)], records) tables."""
    tables = list(tables)
    directory = bytearray(); bodies = bytearray()
    for name, fields, records in tables:
        record_bits = sum(b for _, _, b in fields); record_bytes = (record_bits + 7) // 8
        header = bytearray(40)
        struct.pack_into("<I", header, 8, record_bytes); struct.pack_into("<I", header, 12, record_bits)
        struct.pack_into("<HH", header, 20, records, records); header[28] = len(fields)
        fdir = bytearray(); bit = 0
        for fname, ftype, bits in fields:
            fdir += struct.pack("<II4sI", ftype, bit, fname.encode("ascii"), bits); bit += bits
        directory += name.encode("ascii") + struct.pack("<I", len(bodies))
        bodies += header + fdir + bytes(record_bytes * records)
    head = bytearray(24); head[:4] = b"DB\x00\x08"   # the version word as it sits on every measured disc
    struct.pack_into("<I", head, 8, 24 + len(directory) + len(bodies)); struct.pack_into("<I", head, 0x10, len(tables))
    return bytes(head + directory + bodies)


def _synthetic_mmap(width: int, height: int, *, version: int = 2, format_id: int = 1, pixel_bytes: Optional[int] = None) -> bytes:
    pixel_bytes = width * height if pixel_bytes is None else pixel_bytes
    body = bytes(0x2a0 - 44)
    return (b"MMAP" + struct.pack("<I", version) + b"\x00\x01\x02\x03" + struct.pack("<HH", 1, 1) + struct.pack("<I", 1)
            + struct.pack("<I", 0x2a0) + struct.pack("<I", 0x28) + struct.pack("<III", 0x240, 0x290, 0)
            + struct.pack("<HH", width, height) + struct.pack("<HH", format_id, 0) + struct.pack("<I", pixel_bytes) + body)


def _synthetic_schl(*, platform: Any = 5, channels: Optional[int] = 1, codec: int = 0x08, codec2: int = 0x04, rate: int = 22050) -> bytes:
    """An SCHl header block shaped like the disc's: PT + platform (or GSTR), 0x06 patch, 0xFD marker, version, samples, channels, codec, rate, 0xA0, 0xFF."""
    patches = bytes([0x06, 1, 0x65, 0xFD, 0x80, 1, 3, 0x85, 3, 0x00, 0x24, 0xB4])
    if channels is not None:
        patches += bytes([0x82, 1, channels])
    patches += bytes([0x83, 1, codec, 0x84, 2]) + rate.to_bytes(2, "big") + bytes([0xA0, 1, codec2, 0xFF])
    sub = (b"GSTR" + struct.pack("<I", 1)) if platform == "GSTR" else (b"PT" + struct.pack("<H", platform))
    block = 8 + len(sub) + len(patches)
    return b"SCHl" + struct.pack("<I", block) + sub + patches + b"SCCl" + struct.pack("<I", 12) + bytes(4) + b"SCDl" + struct.pack("<I", 8) + bytes(16)


def _synthetic_shps(images: Sequence[Tuple[int, int, int]], *, big_endian: bool = False) -> bytes:
    """An SHPS bank whose image records carry (record id, width, height); little-endian unless asked otherwise."""
    order = ">" if big_endian else "<"
    directory = bytearray(); records = bytearray(); base = 16 + 8 * len(images)
    for i, (record_id, width, height) in enumerate(images):
        directory += b"im%02d" % i + struct.pack(order + "I", base + len(records))
        records += bytes([record_id]) + (16).to_bytes(3, "big" if big_endian else "little") + struct.pack(order + "HHHHHH", width, height, 0, 0, 0, 0)
    body = directory + records
    return b"SHPS" + struct.pack(order + "II", 16 + len(body), len(images)) + b"G354" + bytes(body)


def _refpack_literal(payload: bytes) -> bytes:
    """A RefPack stream holding ``payload`` as literals only (valid, uncompressed)."""
    out = bytearray(b"\x10\xfb" + len(payload).to_bytes(3, "big"))
    pos = 0
    while len(payload) - pos >= 4:
        take = min(112, (len(payload) - pos) // 4 * 4)
        out.append(0xE0 | (take // 4 - 1)); out += payload[pos:pos + take]; pos += take
    rest = payload[pos:]
    out.append(0xFC | len(rest)); out += rest
    return bytes(out)


def _synthetic_big(entries: Sequence[Tuple[bytes, bytes]], *, size_be: bool = False, tag: bytes = b"BIGF") -> bytes:
    """A BIG archive; a name ending in ``/`` with no payload becomes a (0, 0) directory entry."""
    names = [name.rstrip(b"/") if (not payload and name.endswith(b"/")) else name for name, payload in entries]
    index_size = 16 + sum(8 + len(name) + 1 for name in names)
    index = b""; payloads = b""; cursor = index_size
    for name, (raw, payload) in zip(names, entries):
        if not payload and raw.endswith(b"/"):
            index += struct.pack(">II", 0, 0) + name + b"\x00"
            continue
        index += struct.pack(">II", cursor, len(payload)) + name + b"\x00"
        payloads += payload; cursor += len(payload)
    total = index_size + len(payloads)
    return tag + (struct.pack(">I", total) if size_be else struct.pack("<I", total)) + struct.pack(">II", len(entries), index_size) + index + payloads


def _synthetic_qkl(names: Sequence[str], entries: Sequence[Tuple[int, int, int, int]]) -> bytes:
    fils = bytearray(b"FILS" + struct.pack("<II", 12 + 48 * len(names), len(names)))
    for name in names:
        fils += name.encode("ascii").ljust(48, b"\x00")
    dtls = bytearray(b"DTLS" + struct.pack("<II", 12 + 12 * len(entries), len(entries)))
    for kind, file_index, member, offset in entries:
        dtls += bytes([kind, 0, file_index, 0]) + struct.pack("<II", member, offset)
    data = b"DATA" + struct.pack("<I", 0)
    head = b"QL01" + struct.pack("<II", 12, 12 + len(fils) + len(dtls) + len(data))
    return head + bytes(fils) + bytes(dtls) + data + bytes(64)


TEXT_MEMBER = b"<Headline>A plain ASCII member of sixty-four bytes for the tests.</>"


def build_synthetic_disc(*, sector_size: int = 2048, data_offset: int = 0) -> Tuple[bytes, Dict[str, bytes]]:
    """A synthetic PS2-shaped ISO holding one of everything the mapper knows; returns (image bytes, payloads)."""
    db = _synthetic_tdb([("TEAM", [("TGID", 3, 8), ("TDNA", 0, 32)], 3), ("PLAY", [("PGID", 3, 16), ("POVR", 3, 7)], 5)])
    inner = ea_terf.build_terf([db, TEXT_MEMBER], chunk="DATA")
    inner2 = ea_terf.build_terf([inner], chunk="DATA")
    container = ea_terf.build_terf([db, _synthetic_mmap(32, 32), TEXT_MEMBER, b"", inner2, _synthetic_schl(), _synthetic_mmap(1, 3, format_id=0x400), b"\xf8\x01\x00\x00" + bytes(28)], chunk="DATA")
    comp = ea_terf.build_terf([db, _synthetic_mmap(64, 32, format_id=0)], chunk="COMP")
    nested_big = _synthetic_big([(b"inner.ssh", _synthetic_shps([(0x02, 16, 16)])), (b"m.irx", ps2_elf.build_synthetic_elf([0x03E00008, 0])),
                                 (b"be.ssh", _synthetic_shps([(0x7B, 32, 8)], big_endian=True))])
    big = _synthetic_big([(b"art/one.ssh", _synthetic_shps([(0x02, 64, 32), (0x02, 8, 8)])), (b"snd/two.abk", b"ABKC" + bytes(12)),
                          (b"packed/three.ssh", _refpack_literal(_synthetic_shps([(0x01, 128, 128)]) + bytes(40))),
                          (b"nested/four.big", nested_big), (b"cafeLib/", b""), (b"voice/five.dat", _synthetic_schl(codec=0x0A)),
                          (b"data/six.db", db), (b"data/seven.dat", inner)])
    viv = _synthetic_big([(b"stat.act", b"STAT" + bytes(12))], size_be=True)
    qkl = _synthetic_qkl(["X.DAT", "Y.DAT"], [(0, 0, 0, 0), (1, 0, 3, 64), (1, 1, 0, 128)])
    elf = ps2_elf.build_synthetic_elf([0x3C020000, 0x03E00008, 0])
    system_cnf = b"BOOT2 = cdrom0:\\SLUS_000.00;1\r\nVER = 1.00\r\nVMODE = NTSC\r\n"
    payloads = {"container": container, "comp": comp, "big": big, "viv": viv, "qkl": qkl, "db": db, "elf": elf, "system_cnf": system_cnf}
    image = iso.build_synthetic_iso(sector_size=sector_size, data_offset=data_offset,
                                    files=[(b"SYSTEM.CNF;1", system_cnf), (b"SLUS_000.00;1", elf), (b"TINY.BIN;1", b"\x01\x02"), (b"EMPTY.BIN;1", b"")],
                                    sub_files=[(b"X.DAT;1", container), (b"Y.DAT;1", comp), (b"Z.BIG;1", big), (b"W.VIV;1", viv),
                                               (b"GAME.QKL;1", qkl), (b"STRM.DB;1", db), (b"NOTE.TXT;1", b"plain ascii text file\r\n" * 4),
                                               (b"ICON.SYS;1", b"PS2D" + bytes(28)), (b"IOPRP.IMG;1", b"RESET\x00\x00\x00" + bytes(24)),
                                               (b"CLIP.M2V;1", b"\x00\x00\x01\xb3" + bytes(28)), (b"BLANK.RGB;1", bytes(64))])
    return image, payloads


def selftest() -> int:
    import tempfile
    checks = 0

    def check(cond: bool, what: str) -> None:
        nonlocal checks
        checks += 1
        if not cond:
            raise SystemExit(f"EA_DISC_MAP_SELFTEST_FAIL {what}")
    db = _synthetic_tdb([("TEAM", [("TGID", 3, 8), ("TDNA", 0, 32)], 3), ("PLAY", [("PGID", 3, 16), ("POVR", 3, 7)], 5)])
    schema = tdb_schema(db)
    check(schema["table_count"] == 2 and [t["name"] for t in schema["tables"]] == ["TEAM", "PLAY"] and schema["version"] == 8 and schema["version_bytes"] == "0008", "tdb tables")
    check(identify_head(db[:16]) == "TDB" and identify_head(b"\x03\x12\x3c\x07" + bytes(12)) == "EVT", "TDB / EVT file kinds")
    check(identify_head(b"\xef\xbb\xbfVK_SPACE=Espace") == "TEXT" and identify_head("caf\u00e9 latin".encode("latin-1")) == "TEXT", "BOM / Latin-1 text files")
    try:
        tdb_schema(b"DB\x01\x03" + bytes(12) + struct.pack("<I", 26) + bytes(4)); check(False, "v3 TDB accepted")
    except MapError as error:
        check("0103" in str(error), "v3 TDB refused with its version word"); checks += 1
    check(schema["tables"][1]["records"] == 5 and schema["tables"][1]["fields"][1]["bits"] == 7, "tdb fields")
    check(tdb_schema(b"\x02\x00\x00\x00" + db)["preamble"] == 4, "franchise preamble")
    try:
        tdb_schema(b"XXXX" + bytes(40)); check(False, "non-tdb accepted")
    except MapError:
        checks += 1
    check(schl_header(_synthetic_schl())["platform"] == 5 and schl_header(_synthetic_schl())["rate"] == 22050 and schl_header(_synthetic_schl())["codec2"] == 4, "SCHl PT header")
    check(schl_header(_synthetic_schl(platform="GSTR", channels=None))["platform"] == "GSTR" and schl_header(_synthetic_schl(platform="GSTR", channels=None))["channels"] is None, "SCHl GSTR header")
    check(shps_header(_synthetic_shps([(2, 64, 32)]))["first_image"] == {"record_id": 2, "width": 64, "height": 32}, "SHPS header")
    packed = _refpack_literal(b"SHPS" + bytes(range(60)))
    check(refpack_head(packed, 32)[1][:4] == b"SHPS" and refpack_head(packed, 32)[0] == 64, "RefPack head")
    check(identify_head(b"RESET\x00\x00\x00" + bytes(8)) == "IOPRP" and identify_head(b"\x00\x00\x01\x00\x01\x00\x00\x00\x07" + bytes(7)) == "PS2-ICO", "system kinds")
    check(identify_head(b"BOOT2 = cdrom0:\\") == "TEXT" and identify_head(bytes(16)) == "zero-head" and identify_head(b"", "/VC_20919/0.") == "VC-pack", "text / zero / VC kinds")
    with tempfile.TemporaryDirectory() as tmp:
        for sector_size, data_offset in ((2048, 0), (2352, 24)):
            image, payloads = build_synthetic_disc(sector_size=sector_size, data_offset=data_offset)
            path = Path(tmp) / f"disc{sector_size}.iso"; path.write_bytes(image)
            mapped = map_disc(path, label="Synthetic (USA)")
            c = mapped["containers"]["/DATA/X.DAT"]
            check("error" not in c and c["members"] == 8, f"container mapped on {sector_size}: {c.get('error')}")
            check(c["formats"].get("TDB") == 1 and c["formats"].get("MMAP") == 2 and c["formats"].get("SCHl") == 1 and c["formats"].get("TERF") == 1, "formats %s" % c["formats"])
            check(c["nested_terf"] == 1 and c["nested_depth_max"] == 2 and c["nested_tdb_members"] == 1, "nested to depth 2: %s" % c["nested_formats"])
            check(c["mmap_dimensions"] == {"32x32": 1} and c["mmap_format_0x400"] == 1 and c["mmap_formats"].get("v2/fmt0x400") == 1, "mmap ids %s" % c["mmap_formats"])
            check(c["schl"]["platforms"] == {"PS2": 1} and c["unclassified_heads"] == {"f8010000": 1}, "schl + unclassified heads")
            check(mapped["containers"]["/DATA/Y.DAT"]["chain"].find("COMP") >= 0 and len(mapped["schemas"]) == 1, "COMP container, one schema shape")
            a = mapped["archives"]["/DATA/Z.BIG"]
            check(a["entries"] == 8 and a["member_kinds"].get("SHPS") == 2 and a["refpack_members"] == 1 and a["directory_entries"] == 1, "BIG archive %s" % a["member_kinds"])
            check(a["nested_bigf"] == 1 and a["nested_member_kinds"].get("SHPS") == 2 and a["nested_member_kinds"].get("ELF") == 1 and a["shps_images"] == 5, "nested BIG %s" % a)
            check(a["member_kinds"].get("TDB") == 1 and a["shps_first_record_ids"] == {"0x02": 2, "0x01": 1, "0x7b": 1}, "BIG TDB member + RefPack SHPS header (nested banks included) %s" % a["shps_first_record_ids"])
            check(shps_header(_synthetic_shps([(0x7B, 32, 8)], big_endian=True))["endian"] == "big" and shps_header(_synthetic_shps([(0x7B, 32, 8)], big_endian=True))["first_image"]["width"] == 32, "big-endian SHPS bank")
            check(a["size_field"] == "LE" and mapped["archives"]["/DATA/W.VIV"]["size_field"] == "BE", "BIG size-field endianness")
            check("data/seven.dat" in a["terf_members"] and a["tdb_members"][0]["schema"] in mapped["schemas"] and a["schl"]["codecs"] == {"c1=0x0a/c2=0x04": 1}, "BIG members walked")
            q = mapped["preloads"]["/DATA/GAME.QKL"]
            check(q["files"] == 2 and q["entries"] == 3 and q["header_copies"] == 1 and q["member_copies"] == 2, "QL01 %s" % q)
            check(mapped["executables"]["/SLUS_000.00"]["type"] == "EXEC" and mapped["identity"]["serial"] == "SLUS-00000", "ELF + identity")
            check(mapped["kinds"].get("TEXT") == 2 and mapped["kinds"].get("ICON.SYS") == 1 and mapped["kinds"].get("IOPRP") == 1 and mapped["kinds"].get("MPEG-video") == 1 and mapped["kinds"].get("zero-head") == 1 and mapped["kinds"].get("empty") == 1, "file kinds %s" % mapped["kinds"])
            check(mapped["totals"]["members"] == 10 and mapped["totals"]["mmap_containers"] == 2 and mapped["totals"]["unclassified"] == 1, "totals %s" % mapped["totals"]["formats"])
            md = render_markdown(mapped); page = render_page(mapped, today="1970-01-01")
            check("SLUS-00000" in md and "/DATA/X.DAT" in md and "TGID:uint8" in md and "Preload copies" in md and "Executables" in md, "markdown renders")
            check("| Uniforms & Equipment |" in page and "read-only-mapped" in page and "PT-header platform" in page, "page renders")
            if sector_size == 2048:
                first = mapped
            else:
                strip = lambda m: {k: v for k, v in m.items() if k not in ("image", "seconds", "generated_utc")}  # noqa: E731
                check(json.dumps(strip(first), sort_keys=True) == json.dumps(strip(mapped), sort_keys=True), "raw-CD map equals the 2048 map")
        compare = render_compare(first, mapped)
        check("identical in every mapped count 2" in compare, "compare renders")
        summary = render_summary([first, mapped])
        check("Synthetic (USA)" in summary and "| 2 |" in summary, "summary renders")
    old = {"schema": "ea_disc_map/v1", "label": "Old", "generated_utc": "1970-01-01T00:00:00Z", "seconds": 0.0,
           "image": {"name": "old.iso", "size": 2048, "files": 1, "directories": 1, "sector_size": 2048},
           "identity": {"serial": "SLUS-00000", "boot_file": "SLUS_000.00", "boot_sha256": "0" * 64, "boot_size": 16, "pcsx2_crc": "00000000", "image_sha256": None},
           "kinds": {"TERF": 1}, "files": [{"path": "/DATA/X.DAT", "size": 1, "lba": 100, "kind": "TERF"}],
           "containers": {"/DATA/X.DAT": {"chain": "TERF -> DIR1 -> DATA", "alignment": 64, "members": 1, "declared_length": 1, "size_mismatch": 0,
                                          "codecs": {"NONE (stored)": 1}, "formats": {"MMAP": 1}, "layout_violations": [], "mmap_dimensions": {"32x32": 1},
                                          "text_members": 0, "text_bytes": 0, "tdb_members": []}},
           "archives": {}, "databases": {}, "schemas": {}}
    check("Disc map" in render_markdown(old) and "| Audio |" in render_page(old, today="1970-01-01"), "v1 JSON still renders")
    print(f"EA_DISC_MAP_SELFTEST_PASS checks={checks} tdb=schema-only terf=DATA+COMP+nested bigf=index+refpack+nested "
          f"qkl=ok elf=ok raw-cd=ok markdown=ok page=ok compare=ok summary=ok")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _load_map(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")  # cp1252 consoles must not stop a run
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--iso", type=Path, help="the disc image (read-only)")
    parser.add_argument("--out", type=Path, help="directory for <serial>.<label>.map.json and .map.md (or the output file of --page / --compare / --summary)")
    parser.add_argument("--label", default="", help="the disc's display name, e.g. 'NCAA Football 06 (USA)'")
    parser.add_argument("--hash-image", action="store_true", help="also sha256 the whole image (slow)")
    parser.add_argument("--render", type=Path, help="regenerate the Markdown from an existing .map.json")
    parser.add_argument("--page", type=Path, help="write a pre-filled disc-map page skeleton from an existing .map.json")
    parser.add_argument("--compare", type=Path, nargs=2, metavar=("A.map.json", "B.map.json"), help="diff two maps (retail vs Deluxe, 04 vs 09)")
    parser.add_argument("--summary", type=Path, help="one table over every *.map.json in this directory")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.render:
        data = _load_map(args.render)
        target = args.render.with_name(args.render.name[:-len(".json")] + ".md") if args.render.name.endswith(".map.json") else args.render.with_suffix(".md")
        _write_text(target, render_markdown(data))
        print(f"EA_DISC_MAP_RENDERED {target}")
        return 0
    if args.page:
        data = _load_map(args.page)
        target = args.out if args.out and args.out.suffix == ".md" else (args.out / (args.page.name.replace(".map.json", "") + ".page.md") if args.out else args.page.with_name(args.page.name.replace(".map.json", "") + ".page.md"))
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_text(target, render_page(data))
        print(f"EA_DISC_MAP_PAGE {target}")
        return 0
    if args.compare:
        text = render_compare(_load_map(args.compare[0]), _load_map(args.compare[1]))
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True); _write_text(args.out, text); print(f"EA_DISC_MAP_COMPARED {args.out}")
        else:
            sys.stdout.write(text)
        return 0
    if args.summary:
        maps = [_load_map(p) for p in sorted(args.summary.glob("*.map.json"))]
        if not maps:
            print(f"error: no *.map.json in {args.summary}", file=sys.stderr); return 1
        text = render_summary(maps)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True); _write_text(args.out, text); print(f"EA_DISC_MAP_SUMMARY {args.out} maps={len(maps)}")
        else:
            sys.stdout.write(text)
        return 0
    if not args.iso or not args.out:
        parser.error("--iso and --out are required (or --selftest / --render / --page / --compare / --summary)")
    if not args.iso.is_file():
        print(f"error: {args.iso} is not a file", file=sys.stderr)
        return 1
    progress = (lambda line: None) if args.quiet else (lambda line: print("  " + line, file=sys.stderr, flush=True))
    try:
        mapped = map_disc(args.iso, label=args.label or args.iso.stem, hash_image=args.hash_image, progress=progress)
    except (iso.Iso9660Error, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    serial = (mapped["identity"].get("serial") or args.iso.stem).replace("/", "_")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", mapped["label"]).strip("-") or "disc"
    json_path = args.out / f"{serial}.{slug}.map.json"
    json_path.write_text(json.dumps(mapped, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    md_path = args.out / f"{serial}.{slug}.map.md"
    _write_text(md_path, render_markdown(mapped))
    t = mapped["totals"]
    print(f"EA_DISC_MAP_DONE serial={serial} files={len(mapped['files'])} containers={len(mapped['containers'])} refused={len(t['containers_refused'])} "
          f"archives={len(mapped['archives'])} databases={len(mapped['databases'])} schemas={len(mapped['schemas'])} members={t['members']} "
          f"unclassified={t['unclassified']} seconds={mapped['seconds']} json={json_path} md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
