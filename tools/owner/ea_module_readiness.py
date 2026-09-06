#!/usr/bin/env python3
"""How much of the Madden NFL 09 module's shipped readers works on another EA PlayStation 2 disc.

The disc *mapper* (``tools/owner/ea_disc_map.py``) says what is on a disc.  This
says what the **module's own readers** can do with it -- which is the question a
"could this be the next module?" answer turns on.  Every reader run here is the
one the shipped Madden 09 module runs, imported and not copied::

    ea_terf.parse_terf / decompress_member (LZH1, RLE1, stored) / identify_member
    ea_tdb.parse_tdb / crc_sites / verify_crcs / decode_name
    mmap_art.parse / decode_rgba
    ea_schl.parse_stream_header / iter_streams / parse_bank
    ea_big.parse_big / member / refpack_decompress / nested   (the BIG family)
    ea_shps.parse / decode_rgba / undecodable_reason          (the BIG family)
    madden09_ps2.containers.parse_preload_cache / preload copies
    ps2_elf.pcsx2_crc, tools/ps2_iso9660

The BIG family is the second half of the EA PlayStation 2 fleet: MVP Baseball
2005, the FIFA and NBA Street titles and FIFA 14 have **no** ``TERF`` container
and no bare ``TDB`` anywhere, so the seven rows above them all read ``0 / 0``
and the disc looks unmeasured.  ``ea_big`` and ``ea_shps`` are the readers that
lane ships; run here they say the same kind of thing about those discs that
``ea_terf`` and ``mmap_art`` say about a Madden one.

so a number here is a measurement of the product, not of a re-implementation::

    python3 tools/owner/ea_module_readiness.py --iso IMAGE.iso --out DIR [--label "Madden NFL 08 (USA)"]
                                              [--shps-sample 0] [--nested-sample 0] [--archive-depth 2]
    python3 tools/owner/ea_module_readiness.py --page DIR/<serial>.<label>.readiness.json [--baseline DIR/SLUS-21770.*.json]
    python3 tools/owner/ea_module_readiness.py --summary DIR [--out SUMMARY.md]
    python3 tools/owner/ea_module_readiness.py --selftest

**Retail-free.**  Names, counts, offsets, digests, and schema field names and
widths.  No member payload, no decoded pixel, no string out of a text bank: a
decoded texture is measured and dropped, a database's records are never read,
and the only text that leaves a disc is a four-byte table or field name, which
is the schema and is identical on every copy of the game.

**Read-only.**  The image is opened ``"rb"`` and nothing is written next to it.
Containers are read through a memory map, so a 415 MB speech container costs no
memory; a raw-CD image (2352-byte sectors) is gathered sector by sector by the
mapper's own extent reader.

**What "works unchanged" means, row by row** -- the page repeats this, because a
percentage with no definition is a decoration:

* *containers* -- ``ea_terf.parse_terf`` returned a container.
* *members* -- the member's stored bytes decoded far enough to be classified
  (``IDENTIFY_HEAD`` = 32 bytes), i.e. its codec is one of the three the module
  implements and its stream is not truncated.
* *TDB databases* -- ``ea_tdb.parse_tdb`` returned a database.
* *CRC sites* -- the stored checksum equals the one recomputed from the file's
  own bytes, per ``ea_tdb.crc_sites``.
* *MMAP images* -- ``mmap_art.decode_rgba`` returned pixels for image 0 of a
  sampled member.
* *SCHl streams* -- the header parsed **and** the codec is one the audio lane
  decodes (EA-XA, or a stream with no codec tag, which decodes the same way).
* *BNKl banks* -- ``ea_schl.parse_bank`` returned a bank directory.
* *preload caches* -- the cache parsed and each copy it carries is byte-identical
  to the container bytes it copies.
* *BIG archives* -- ``ea_big.parse_big`` returned an archive.  ``BIG4`` and the
  whole-archive-RefPack (``C0 FB``) spelling are refused **by name** by the
  reader, and a refusal by name is counted as refused, never as absent.
* *BIG entries* -- the entry's stored bytes decoded far enough to be classified
  (32 bytes): it is stored plain, or its RefPack stream started cleanly, and
  its table row addresses bytes the archive really holds.
* *RefPack streams* -- the same, over the packed entries only, plus every loose
  file on the disc whose first two bytes are a RefPack header.
* *SHPS images* -- ``ea_shps.decode_rgba`` returned pixels for that image, over
  every image of every bank sampled.  The pixels are measured and dropped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

_FILE = globals().get("__file__", "")
if _FILE and Path(_FILE).is_file():
    _HERE = Path(_FILE).resolve().parent          # tools/owner
else:  # run as ``python3 - < tools/owner/ea_module_readiness.py`` from the repository root
    _HERE = Path.cwd() / "tools" / "owner"
_ROOT = _HERE.parent.parent
for _p in (_HERE, _ROOT / "tools", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import ea_disc_map as mapper  # noqa: E402  the disc mapper: ISO walking, extents, QL01, glossary
import ps2_iso9660 as iso  # noqa: E402
from mod_editor.games.contract import Refusal  # noqa: E402
from mod_editor.games._formats import ea_big, ea_schl, ea_shps, ea_tdb, ea_terf, ps2_elf  # noqa: E402
from mod_editor.games.madden09_ps2 import containers as m09  # noqa: E402
from mod_editor.games.madden09_ps2 import mmap_art  # noqa: E402

SCHEMA = "ea_module_readiness/v2"          # v2 adds the BIG / RefPack / SHPS rows

#: The reader modules whose behaviour this tool measures.  Their digests go in
#: the JSON so a page can say which build of the module was run.
READER_FILES: Tuple[Tuple[str, str], ...] = (
    ("ea_terf", "mod_editor/games/_formats/ea_terf.py"),
    ("ea_tdb", "mod_editor/games/_formats/ea_tdb.py"),
    ("ea_schl", "mod_editor/games/_formats/ea_schl.py"),
    ("ea_big", "mod_editor/games/_formats/ea_big.py"),
    ("ea_shps", "mod_editor/games/_formats/ea_shps.py"),
    ("mmap_art", "mod_editor/games/madden09_ps2/mmap_art.py"),
    ("containers", "mod_editor/games/madden09_ps2/containers.py"),
    ("ps2_iso9660", "tools/ps2_iso9660.py"),
)

#: The tables whose full field list is recorded, so a page can say whether the
#: roster and identity lanes port with a schema table only.  Everything else is
#: recorded as a name with its field count and record stride.
SCHEMA_TABLES: Tuple[str, ...] = (
    "TEAM", "PLAY", "DCHT", "INJY", "COCH", "SEAI", "SLRI",
    "FORM", "PBFM", "PBST", "SETL", "PBPL", "PLYL",
)

#: How much of a member is decoded to classify it.  The module's own constant.
MEMBER_HEAD = ea_terf.IDENTIFY_HEAD

#: How much of an ``SCHl`` member is decoded to read its first stream header.
#: An EA header runs to a few hundred bytes; 64 KiB is the reader's own ceiling.
SCHL_HEAD_BYTES = 1 << 16

#: A member larger than this is not pulled into memory whole; the row says so.
MEMBER_WHOLE_CAP = 128 << 20

#: A preload cache larger than this is listed unread rather than loaded.
CACHE_CAP = 320 << 20

#: Default per-container sample sizes for the two passes that must decode a
#: whole member.  ``MMAP`` decoding is pure-Python per pixel and ``SCHl`` stream
#: walking touches the whole member, so both are sampled evenly across the
#: container and every row records what it sampled out of what.
DEFAULT_MMAP_SAMPLE = 48
DEFAULT_SCHL_SAMPLE = 16

#: ``SHPS`` banks per archive whose images are all decoded.  Parsing a bank
#: costs a whole RefPack decode of its entry; decoding the images it then holds
#: costs almost nothing on top, so this is the only knob the ``SHPS`` row needs.
#: ``0`` on the command line means every bank.
DEFAULT_SHPS_SAMPLE = 0

#: Nested archives opened per archive.  ``0`` means every one.
DEFAULT_NESTED_SAMPLE = 0

#: How far down a chain of archives-inside-archives this tool walks.  The
#: mapper stops at one level; two is enough for every disc in reach, and the
#: row says how many were left unopened when it is not.
ARCHIVE_MAX_DEPTH = 2

#: A file or entry whose name looks like a database.  What the page's "where do
#: the rosters live" row is built from -- names only; nothing is interpreted.
DATA_TABLE_RE = re.compile(r"(?i)(database|(?:^|[/!])db[._]|xdb|\.adf$|\.db$)")

#: How much of a database-shaped file is looked at for its first text line, and
#: the largest one that is probed at all.
DATA_PROBE_BYTES = 4096
DATA_PROBE_CAP_BYTES = 16 << 20

#: How many probe rows a record keeps.  The histogram behind them is complete.
DATA_PROBE_CAP = 240

#: File kinds that are containers in their own right, so the database probe
#: leaves them to the pass that opens them.
CONTAINER_KINDS: Tuple[str, ...] = ("TERF", "BIGF", "SHPS", "SCHl", "BNKl", "QL01", "ELF")

#: The studio's fourteen pages, in the shell's order.  ``mapper.PAGE_ROWS``
#: carries thirteen; Build & Share is the shell's own and no game writes it.
PAGE_ROWS: Tuple[str, ...] = mapper.PAGE_ROWS + ("Build & Share",)

#: Which decompressed format feeds which page, for the "what a module needs"
#: section.  A page with no format here is answered from the glossary alone.
PAGE_FORMATS: Dict[str, Tuple[str, ...]] = {
    "Uniforms & Equipment": ("MMAP", "SHPS"),
    "Names, Numbers & Faces": ("TDB", "MMAP", "SHPS"),
    "Text & Team Identity": ("TDB", "TEXT"),
    "Field Art & Create-Team Art": ("MMAP", "SHPS"),
    "Stadiums": ("MMAP", "SMF", "DMF", "SHPS"),
    "Presentation": ("MMAP", "MPCh", "SHPS"),
    "Menus & UI": ("TEXT", "MMAP", "FNTS", "SHPS"),
    "Audio": ("SCHl", "BNKl"),
    "Gameplay": ("ELF",),
    "Playbooks & Plays": ("TDB",),
    "All Textures": ("MMAP", "SHPS"),
}


class ReadinessError(ValueError):
    """A sentence about what could not be measured; never a traceback."""


# --------------------------------------------------------------------------
# The refusal ledger
# --------------------------------------------------------------------------
_DIGITS = re.compile(r"\d[\d,]*")
_WHITESPACE = re.compile(r"\s+")
_QUOTED = re.compile(r"b?['\"][^'\"]{0,40}['\"]")


def refusal_class(sentence: object) -> str:
    """*sentence* with its numbers and quoted bytes blanked, so instances group.

    "member 12 runs from 640 for 96 byte(s)" and "member 913 runs from 40960 for
    64 byte(s)" are one refusal seen twice, and a page that lists them twice is
    a page nobody reads to the end.
    """

    text = _WHITESPACE.sub(" ", str(sentence).strip())
    text = _QUOTED.sub("'..'", text)
    text = _DIGITS.sub("#", text)
    return text[:240]


class Ledger:
    """Every refusal a reader raised, grouped by sentence class."""

    def __init__(self) -> None:
        self.rows: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def add(self, reader: str, where: str, exc: object) -> str:
        key = (reader, refusal_class(exc))
        row = self.rows.get(key)
        if row is None:
            row = {"reader": reader, "type": type(exc).__name__ if isinstance(exc, BaseException) else "str",
                   "sentence_class": key[1], "example": str(exc)[:400], "count": 0, "where": []}
            self.rows[key] = row
        row["count"] += 1
        if where and len(row["where"]) < 6 and where not in row["where"]:
            row["where"].append(where)
        return key[1]

    def as_list(self) -> List[Dict[str, Any]]:
        return sorted(self.rows.values(), key=lambda r: (-r["count"], r["reader"], r["sentence_class"]))

    def total(self) -> int:
        return sum(row["count"] for row in self.rows.values())


def _evenly(indices: Sequence[int], sample: Optional[int]) -> List[int]:
    """*sample* of *indices*, spread across the whole run rather than its head."""

    items = list(indices)
    if sample is None or sample <= 0 or len(items) <= sample:
        return items
    step = len(items) / float(sample)
    return [items[min(len(items) - 1, int(i * step))] for i in range(sample)]


def _pct(part: int, whole: int) -> Optional[float]:
    """*part* of *whole* as a percentage, never rounding a shortfall up to 100.

    6,268 of 6,270 is 99.968%, and a page that prints that as 100.0% has quietly
    thrown away the two copies this whole study exists to find.
    """

    if not whole:
        return None
    if part >= whole:
        return 100.0
    return min(round(100.0 * part / whole, 1), 99.9)


def _table_signature(table: Any) -> str:
    shape = [(f.name, f.type_id, f.bit_width, f.bit_offset) for f in table.fields]
    return hashlib.sha256(repr((table.name, table.record_bytes, shape)).encode("utf-8")).hexdigest()[:16]


def _fields_of(table: Any) -> List[List[Any]]:
    return [[f.name, f.type_name, f.bit_width, f.bit_offset] for f in table.fields]


# --------------------------------------------------------------------------
# One container, under the module's readers
# --------------------------------------------------------------------------
def measure_container(data: Any, name: str, ledger: Ledger, tally: Dict[str, Any], *,
                      mmap_sample: Optional[int] = DEFAULT_MMAP_SAMPLE,
                      schl_sample: Optional[int] = DEFAULT_SCHL_SAMPLE,
                      deep: bool = True) -> Dict[str, Any]:
    """Every reader the module ships, run over one ``TERF`` container.

    *tally* is the disc-wide accumulator; the returned dictionary is this
    container's own row.  Raises only what ``parse_terf`` raises: a container
    that will not open is the caller's row to record.
    """

    container = ea_terf.parse_terf(data, allow_size_mismatch=True)
    row: Dict[str, Any] = {
        "chain": container.chunk_chain,
        "alignment": container.alignment,
        "members": container.member_count,
        "declared_length": container.declared_length,
        "size_mismatch": container.size_mismatch,
        "compressed": container.compressed,
        "codecs": container.codec_histogram(),
        "layout_violations": container.layout_violations()[:4],
    }
    tally["chains"][container.chunk_chain] += 1
    tally["alignments"][str(container.alignment)] += 1
    tally["codecs"].update(container.codec_histogram())

    # -- pass 1: classify every member from its first 32 decoded bytes --------
    formats: Counter = Counter()
    by_format: Dict[str, List[int]] = {}
    head_refused = 0
    for index in range(container.member_count):
        try:
            head = container.member(index, max_output=MEMBER_HEAD)
        except (Refusal, ValueError, struct.error, IndexError, MemoryError) as exc:
            head_refused += 1
            ledger.add("ea_terf.decompress_member", name, exc)
            continue
        kind = ea_terf.identify_member(head) or "unclassified"
        formats[kind] += 1
        by_format.setdefault(kind, []).append(index)
    row["formats"] = dict(sorted(formats.items(), key=lambda kv: (-kv[1], kv[0])))
    row["members_head_decoded"] = container.member_count - head_refused
    row["members_refused"] = head_refused
    tally["members"] += container.member_count
    tally["members_head_decoded"] += container.member_count - head_refused
    tally["members_refused"] += head_refused
    tally["formats"].update(formats)
    if not deep:
        return row

    # -- pass 2: the databases ----------------------------------------------
    tdb_indices = by_format.get("TDB", [])
    if tdb_indices:
        row["tdb"] = _measure_tdb_members(container, tdb_indices, name, ledger, tally)

    # -- pass 3: the textures ------------------------------------------------
    mmap_indices = by_format.get("MMAP", [])
    if mmap_indices:
        row["mmap"] = _measure_mmap_members(container, mmap_indices, name, ledger, tally,
                                            sample=mmap_sample)

    # -- pass 4: the audio ---------------------------------------------------
    schl_indices = by_format.get("SCHl", [])
    if schl_indices:
        row["schl"] = _measure_schl_members(container, schl_indices, name, ledger, tally,
                                            sample=schl_sample)
    bnkl_indices = by_format.get("BNKl", [])
    if bnkl_indices:
        row["bnkl"] = _measure_bnkl_members(container, bnkl_indices, name, ledger, tally)
    return row


def _whole(container: ea_terf.TerfContainer, index: int) -> bytes:
    """One member, whole and uncached -- the module's own helper, size-guarded."""

    if container.members[index].decompressed_size > MEMBER_WHOLE_CAP:
        raise ReadinessError(
            "member %d unpacks to %d byte(s), past this tool's %d-byte whole-member "
            "cap; it is counted and left unread."
            % (index, container.members[index].decompressed_size, MEMBER_WHOLE_CAP))
    return m09.member_uncached(container, index)


def _measure_tdb_members(container: ea_terf.TerfContainer, indices: Sequence[int],
                         name: str, ledger: Ledger, tally: Dict[str, Any]) -> Dict[str, Any]:
    out = {"total": len(indices), "parsed": 0, "refused": 0,
           "crc_sites": 0, "crc_matched": 0, "crc_refused": 0, "tables": 0, "fields": 0}
    for index in indices:
        tally["tdb_total"] += 1
        try:
            payload = _whole(container, index)
        except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
            out["refused"] += 1
            tally["tdb_refused"] += 1
            ledger.add("ea_terf.decompress_member", f"{name}:{index}", exc)
            continue
        _measure_one_tdb(payload, f"{name}:{index}", ledger, tally, out)
    return out


def _measure_one_tdb(payload: bytes, where: str, ledger: Ledger, tally: Dict[str, Any],
                     out: Dict[str, Any]) -> None:
    try:
        database = ea_tdb.parse_tdb(payload)
    except (Refusal, ValueError, struct.error, IndexError) as exc:
        out["refused"] += 1
        tally["tdb_refused"] += 1
        ledger.add("ea_tdb.parse_tdb", where, exc)
        return
    out["parsed"] += 1
    tally["tdb_parsed"] += 1
    out["tables"] += database.table_count
    tally["tdb_tables"] += database.table_count
    for table in database.tables:
        out["fields"] += table.field_count
        tally["tdb_fields"] += table.field_count
        tally["table_names"][table.name] += 1
        shapes = tally["schemas"].setdefault(table.name, {})
        signature = _table_signature(table)
        seen = shapes.get(signature)
        if seen is None:
            seen = {"count": 0, "record_bytes": table.record_bytes, "record_bits": table.record_bits,
                    "field_count": table.field_count, "first_seen": where,
                    "fields": _fields_of(table) if table.name in SCHEMA_TABLES else None}
            shapes[signature] = seen
        seen["count"] += 1
    try:
        sites = ea_tdb.crc_sites(payload)
    except (Refusal, ValueError, struct.error, IndexError) as exc:
        out["crc_refused"] += 1
        tally["crc_refused"] += 1
        ledger.add("ea_tdb.crc_sites", where, exc)
        return
    matched = sum(1 for site in sites if site.matches)
    out["crc_sites"] += len(sites)
    out["crc_matched"] += matched
    tally["crc_sites"] += len(sites)
    tally["crc_matched"] += matched
    if matched != len(sites):
        for site in sites:
            if not site.matches:
                ledger.add("ea_tdb.verify_crcs", where, site.sentence())
                break


def _measure_mmap_members(container: ea_terf.TerfContainer, indices: Sequence[int],
                          name: str, ledger: Ledger, tally: Dict[str, Any], *,
                          sample: Optional[int]) -> Dict[str, Any]:
    chosen = _evenly(indices, sample)
    out = {"members": len(indices), "sampled": len(chosen), "parsed": 0, "refused": 0,
           "images": 0, "image0_decoded": 0, "image0_refused": 0,
           "versions": Counter(), "dimensions": Counter(), "reasons": Counter()}
    tally["mmap_members"] += len(indices)
    tally["mmap_sampled"] += len(chosen)
    for index in chosen:
        where = f"{name}:{index}"
        try:
            payload = _whole(container, index)
        except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
            out["refused"] += 1
            tally["mmap_refused"] += 1
            ledger.add("ea_terf.decompress_member", where, exc)
            continue
        try:
            texture = mmap_art.parse(payload)
        except (Refusal, ValueError, struct.error, IndexError) as exc:
            out["refused"] += 1
            tally["mmap_refused"] += 1
            ledger.add("mmap_art.parse", where, exc)
            continue
        out["parsed"] += 1
        tally["mmap_parsed"] += 1
        out["versions"][str(texture.version)] += 1
        out["images"] += len(texture.images)
        tally["mmap_images"] += len(texture.images)
        if not texture.images:
            out["image0_refused"] += 1
            tally["mmap_image0_refused"] += 1
            out["reasons"]["this member declares no images"] += 1
            tally["mmap_reasons"]["this member declares no images"] += 1
            continue
        reason = texture.undecodable_reason(texture.image(0))
        if reason is not None:
            out["image0_refused"] += 1
            tally["mmap_image0_refused"] += 1
            out["reasons"][refusal_class(reason)] += 1
            tally["mmap_reasons"][refusal_class(reason)] += 1
            ledger.add("mmap_art.undecodable_reason", where, reason)
            continue
        try:
            width, height, rgba = mmap_art.decode_rgba(payload, image=0, texture=texture)
        except (Refusal, ValueError, struct.error, IndexError, MemoryError) as exc:
            out["image0_refused"] += 1
            tally["mmap_image0_refused"] += 1
            out["reasons"][refusal_class(exc)] += 1
            tally["mmap_reasons"][refusal_class(exc)] += 1
            ledger.add("mmap_art.decode_rgba", where, exc)
            continue
        # The pixels are measured and dropped: nothing decoded off a disc is kept.
        assert len(rgba) == width * height * 4
        del rgba
        out["image0_decoded"] += 1
        tally["mmap_image0_decoded"] += 1
        out["dimensions"][f"{width}x{height}"] += 1
        tally["mmap_dimensions"][f"{width}x{height}"] += 1
    out["versions"] = dict(out["versions"].most_common(6))
    out["dimensions"] = dict(out["dimensions"].most_common(12))
    out["reasons"] = dict(out["reasons"].most_common(6))
    return out


def _measure_schl_members(container: ea_terf.TerfContainer, indices: Sequence[int],
                          name: str, ledger: Ledger, tally: Dict[str, Any], *,
                          sample: Optional[int]) -> Dict[str, Any]:
    out = {"members": len(indices), "headers_parsed": 0, "headers_refused": 0,
           "decodable": 0, "undecodable": 0,
           "codecs": Counter(), "rates": Counter(), "channels": Counter(), "platforms": Counter(),
           "walked_members": 0, "streams": 0, "streams_complete": 0}
    tally["schl_members"] += len(indices)
    for index in indices:
        where = f"{name}:{index}"
        try:
            head = container.member(index, max_output=SCHL_HEAD_BYTES)
        except (Refusal, ValueError, struct.error, MemoryError) as exc:
            out["headers_refused"] += 1
            tally["schl_headers_refused"] += 1
            ledger.add("ea_terf.decompress_member", where, exc)
            continue
        try:
            header = ea_schl.parse_stream_header(head, 0, len(head))
        except (Refusal, ValueError, struct.error, IndexError) as exc:
            out["headers_refused"] += 1
            tally["schl_headers_refused"] += 1
            ledger.add("ea_schl.parse_stream_header", where, exc)
            continue
        out["headers_parsed"] += 1
        tally["schl_headers_parsed"] += 1
        codec = header.codec_name
        out["codecs"][codec] += 1
        tally["schl_codecs"][codec] += 1
        out["rates"][str(header.sample_rate)] += 1
        out["channels"][str(header.channels)] += 1
        out["platforms"][header.platform] += 1
        tally["schl_platforms"][header.platform] += 1
        if header.decodable:
            out["decodable"] += 1
            tally["schl_decodable"] += 1
        else:
            out["undecodable"] += 1
            tally["schl_undecodable"] += 1
    for index in _evenly(indices, sample):
        where = f"{name}:{index}"
        try:
            payload = _whole(container, index)
        except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
            ledger.add("ea_terf.decompress_member", where, exc)
            continue
        try:
            streams = ea_schl.iter_streams(payload, 0, len(payload))
        except (Refusal, ValueError, struct.error, IndexError) as exc:
            ledger.add("ea_schl.iter_streams", where, exc)
            continue
        out["walked_members"] += 1
        out["streams"] += len(streams)
        out["streams_complete"] += sum(1 for s in streams if s.complete)
        tally["schl_walked_members"] += 1
        tally["schl_streams"] += len(streams)
        tally["schl_streams_complete"] += sum(1 for s in streams if s.complete)
    for key in ("codecs", "rates", "channels", "platforms"):
        out[key] = dict(Counter(out[key]).most_common(8))
    return out


def _measure_bnkl_members(container: ea_terf.TerfContainer, indices: Sequence[int],
                          name: str, ledger: Ledger, tally: Dict[str, Any]) -> Dict[str, Any]:
    out = {"members": len(indices), "parsed": 0, "refused": 0, "sounds": 0, "empty_slots": 0}
    tally["bnkl_members"] += len(indices)
    for index in indices:
        where = f"{name}:{index}"
        try:
            payload = _whole(container, index)
        except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
            out["refused"] += 1
            tally["bnkl_refused"] += 1
            ledger.add("ea_terf.decompress_member", where, exc)
            continue
        try:
            bank = ea_schl.parse_bank(payload, 0, len(payload))
        except (Refusal, ValueError, struct.error, IndexError) as exc:
            out["refused"] += 1
            tally["bnkl_refused"] += 1
            ledger.add("ea_schl.parse_bank", where, exc)
            continue
        out["parsed"] += 1
        out["sounds"] += len(bank.sounds)
        out["empty_slots"] += bank.empty_slots
        tally["bnkl_parsed"] += 1
        tally["bnkl_sounds"] += len(bank.sounds)
    return out


# --------------------------------------------------------------------------
# The EA BIG family: archives, RefPack streams and SHPS image banks
# --------------------------------------------------------------------------
#: What "works unchanged" means for the three families this section adds, in
#: the same shape the TERF families use:
#:
#: * *BIG archives* -- ``ea_big.parse_big`` returned an archive.  A ``BIG4`` or
#:   whole-archive-RefPack (``C0 FB``) file is a **refusal by name**, which is
#:   the reader doing its job and is counted as refused, not as absent.
#: * *BIG entries* -- the entry's stored bytes decoded far enough to be
#:   classified (32 bytes), i.e. it is stored plain or its RefPack stream
#:   started cleanly and its row addresses bytes the archive really holds.
#: * *RefPack streams* -- the same, over the packed entries only, plus every
#:   loose file on the disc whose first two bytes are a RefPack header.
#: * *SHPS images* -- ``ea_shps.decode_rgba`` returned pixels for that image.
#:   The pixels are measured and dropped.


def _entry_label(where: str, entry: Any) -> str:
    return "%s!%s" % (where, entry.name)


def _entry_bytes(archive: Any, index: int) -> bytes:
    """One entry, whole and **uncached**, RefPack-decoded where it is packed.

    ``BigArchive.member`` caches only when it is asked for the whole entry with
    no ceiling; a census that walked 61,000 entries that way would hold every
    decompressed one alive.  Asking for exactly the declared size takes the
    reader's own bounded path and keeps nothing.
    """

    entry = archive.entry(index)
    header = archive.compression(index)
    want = header.decompressed_size if header is not None else entry.size
    if want > MEMBER_WHOLE_CAP:
        raise ReadinessError(
            "entry %d (%r) unpacks to %d byte(s), past this tool's %d-byte whole-entry "
            "cap; it is counted and left unread." % (index, entry.name, want, MEMBER_WHOLE_CAP))
    return archive.member(index, max_output=want)


#: How far a declared size may sit from the bytes on hand and still be read as
#: that byte order.  One ISO9660 sector; the mapper's own tolerance, and every
#: archive that needs it is within a sector.
SIZE_FIELD_SLACK = 4096


def size_field(archive: Any, head: "bytes | None", available: int) -> Tuple[str, str]:
    """Which byte order the archive's own size word is in, tolerant of padding.

    ``BigArchive`` reports ``little`` or ``big`` only when the declared size
    equals the bytes it was handed.  A file on an ISO9660 disc is padded out to
    a 2,048-byte sector, so a retail archive almost never matches exactly, and
    the reader falls back to ``little (declared)`` for both orders.  This asks
    the weaker question the padding allows: *does one of the two words land
    between the end of the last entry and the end of the file?*  Nothing is
    guessed -- an archive whose entries run past both words is ``neither``.
    """

    if head is None or len(head) < ea_big.BIG_HEADER_SIZE:
        return archive.size_endian, ("exact" if not archive.size_mismatch else
                                     "declares %d, holds %d" % (archive.declared_size, archive.length))
    little, = struct.unpack_from("<I", head, 4)
    big, = struct.unpack_from(">I", head, 4)
    span = max([entry.end for entry in archive.entries if entry.size] or [archive.index_bytes])
    for label, value in (("little", little), ("big", big)):
        if value == available:
            return label, "exact"
    for label, value in (("little", little), ("big", big)):
        if span <= value <= available:
            return label, "declares %d in a %d-byte file" % (value, available)
    # A third and weaker reading, for NBA Street Vol. 2: the size word is inside
    # one sector of the file's length but the last entry's declared length runs a
    # little past it, so the note carries the span as well as the word.
    for label, value in (("little", little), ("big", big)):
        if abs(value - available) <= SIZE_FIELD_SLACK:
            return label, ("declares %d in a %d-byte file, and its last entry ends at %d"
                           % (value, available, span))
    return "neither", "LE %d / BE %d in a %d-byte file whose last entry ends at %d" % (
        little, big, available, span)


def _probe_data_table(payload: bytes, where: str, tally: Dict[str, Any], source: str) -> None:
    """Say what a database-shaped file *is*, in magic, shape and counts only.

    The question this answers is "where does this title keep its rosters, and
    in what format" -- so the record carries the first four bytes as hex and as
    their printable form (a magic is schema, like a table name), whether
    ``ea_tdb.parse_tdb`` opens it, and, when the bytes are text, how many
    comma-separated fields the first line declares.  Never the line itself.
    """

    head = payload[:MEMBER_HEAD]
    kind = ea_terf.identify_member(head) or ea_big.FORMAT_UNCLASSIFIED
    opens_as_tdb = False
    try:
        ea_tdb.parse_tdb(payload)
        opens_as_tdb = True
    except (Refusal, ValueError, struct.error, IndexError):
        opens_as_tdb = False
    fields: Optional[int] = None
    magic_hex = ""
    printable = ""
    words: List[int] = []
    if kind == ea_terf.FORMAT_TEXT:
        # A CSV table's first four bytes are the first four characters of its
        # header line, and their hex is that text reversibly.  Nothing about the
        # bytes of a text table leaves this function: the shape a CSV has is how
        # many comma-separated names its first line declares, and that is a count.
        line = payload[:DATA_PROBE_BYTES].split(b"\n", 1)[0]
        if b"," in line:
            fields = line.count(b",") + 1
        key = ("plain text, %s comma-separated field(s) on its first line"
               % (fields if fields is not None else "no"))
    else:
        magic_hex = head[:4].hex()
        printable = "".join(chr(b) if 32 <= b < 127 else "." for b in head[:4])
        # On the Street titles the slot where a magic would be holds a small
        # little-endian count instead, so the first four words go in the row.
        words = [struct.unpack_from("<I", payload, offset)[0]
                 for offset in range(0, min(16, max(0, len(payload) - 3)), 4)]
        key = "%s (%s)" % (magic_hex, printable)
    tally["data_magics"][key] += 1
    tally["data_kinds"][kind] += 1
    if opens_as_tdb:
        tally["data_tdb"] += 1
    if len(tally["data_probes"]) < DATA_PROBE_CAP:
        tally["data_probes"].append({
            "where": where, "source": source, "bytes": len(payload),
            "magic": magic_hex, "printable": printable, "format": kind,
            "first_words_le": words,
            "opens_as_tdb": opens_as_tdb, "csv_fields": fields})


def _measure_one_shps(payload: bytes, where: str, ledger: Ledger, tally: Dict[str, Any],
                      out: Dict[str, Any]) -> None:
    """One ``SHPS`` bank: parse it, then decode **every** image it declares."""

    try:
        bank = ea_shps.parse(payload, name=where)
    except (Refusal, ValueError, struct.error, IndexError) as exc:
        out["refused"] += 1
        tally["shps_refused"] += 1
        ledger.add("ea_shps.parse", where, exc)
        return
    out["parsed"] += 1
    tally["shps_parsed"] += 1
    tally["shps_endians"][bank.endian] += 1
    tally["shps_directory_ids"][bank.directory_id] += 1
    for code, count in bank.code_histogram().items():
        tally["shps_block_codes"][code] += count
    for index, image in enumerate(bank.images):
        out["images"] += 1
        tally["shps_images"] += 1
        code = ("0x%02x" % image.code) if image.blocks else "(no block)"
        reason = bank.undecodable_reason(index)
        if reason is not None:
            out["image_refused"] += 1
            tally["shps_image_refused"] += 1
            tally["shps_refused_codes"][code] += 1
            tally["shps_reasons"][refusal_class(reason)] += 1
            ledger.add("ea_shps.undecodable_reason", where, reason)
            continue
        try:
            width, height, rgba = ea_shps.decode_rgba(bank, index)
        except (Refusal, ValueError, struct.error, IndexError, MemoryError) as exc:
            out["image_refused"] += 1
            tally["shps_image_refused"] += 1
            tally["shps_refused_codes"][code] += 1
            tally["shps_reasons"][refusal_class(exc)] += 1
            ledger.add("ea_shps.decode_rgba", where, exc)
            continue
        # Measured and dropped: nothing decoded off a disc is kept.
        assert len(rgba) == width * height * 4
        del rgba
        out["decoded"] += 1
        tally["shps_decoded"] += 1
        tally["shps_decoded_codes"][code] += 1
        tally["shps_dimensions"]["%dx%d" % (width, height)] += 1
        if image.mip_bytes:
            tally["shps_mip_images"] += 1


def _new_shps_row(banks: int, sampled: int) -> Dict[str, Any]:
    return {"banks": banks, "sampled": sampled, "parsed": 0, "refused": 0,
            "images": 0, "decoded": 0, "image_refused": 0}


def _schl_header_row(head: bytes, where: str, ledger: Ledger, tally: Dict[str, Any],
                     out: Dict[str, Any]) -> None:
    try:
        header = ea_schl.parse_stream_header(head, 0, len(head))
    except (Refusal, ValueError, struct.error, IndexError) as exc:
        out["headers_refused"] += 1
        tally["schl_headers_refused"] += 1
        ledger.add("ea_schl.parse_stream_header", where, exc)
        return
    out["headers_parsed"] += 1
    tally["schl_headers_parsed"] += 1
    out["codecs"][header.codec_name] += 1
    tally["schl_codecs"][header.codec_name] += 1
    out["platforms"][header.platform] += 1
    tally["schl_platforms"][header.platform] += 1
    if header.decodable:
        out["decodable"] += 1
        tally["schl_decodable"] += 1
    else:
        out["undecodable"] += 1
        tally["schl_undecodable"] += 1


def _schl_walk(payload: bytes, where: str, ledger: Ledger, tally: Dict[str, Any],
               out: Dict[str, Any]) -> None:
    try:
        streams = ea_schl.iter_streams(payload, 0, len(payload))
    except (Refusal, ValueError, struct.error, IndexError) as exc:
        ledger.add("ea_schl.iter_streams", where, exc)
        return
    out["walked_members"] += 1
    out["streams"] += len(streams)
    out["streams_complete"] += sum(1 for stream in streams if stream.complete)
    tally["schl_walked_members"] += 1
    tally["schl_streams"] += len(streams)
    tally["schl_streams_complete"] += sum(1 for stream in streams if stream.complete)


def _new_schl_row(members: int) -> Dict[str, Any]:
    return {"members": members, "headers_parsed": 0, "headers_refused": 0,
            "decodable": 0, "undecodable": 0, "codecs": Counter(), "platforms": Counter(),
            "walked_members": 0, "streams": 0, "streams_complete": 0}


def _finish_schl_row(out: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("codecs", "platforms"):
        out[key] = dict(Counter(out[key]).most_common(8))
    return out


def _measure_shps_entries(archive: Any, indices: Sequence[int], name: str, ledger: Ledger,
                          tally: Dict[str, Any], *, sample: Optional[int]) -> Dict[str, Any]:
    chosen = _evenly(indices, sample)
    out = _new_shps_row(len(indices), len(chosen))
    tally["shps_banks"] += len(indices)
    tally["shps_sampled"] += len(chosen)
    for index in chosen:
        label = _entry_label(name, archive.entry(index))
        try:
            payload = _entry_bytes(archive, index)
        except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
            out["refused"] += 1
            tally["shps_refused"] += 1
            ledger.add("ea_big.member", label, exc)
            continue
        _measure_one_shps(payload, label, ledger, tally, out)
    return out


def _measure_schl_entries(archive: Any, indices: Sequence[int], name: str, ledger: Ledger,
                          tally: Dict[str, Any], *, sample: Optional[int]) -> Dict[str, Any]:
    out = _new_schl_row(len(indices))
    tally["schl_members"] += len(indices)
    for index in indices:
        label = _entry_label(name, archive.entry(index))
        try:
            head = archive.member(index, max_output=SCHL_HEAD_BYTES)
        except (Refusal, ValueError, struct.error, MemoryError) as exc:
            out["headers_refused"] += 1
            tally["schl_headers_refused"] += 1
            ledger.add("ea_big.member", label, exc)
            continue
        _schl_header_row(head, label, ledger, tally, out)
    for index in _evenly(indices, sample):
        label = _entry_label(name, archive.entry(index))
        try:
            payload = _entry_bytes(archive, index)
        except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
            ledger.add("ea_big.member", label, exc)
            continue
        _schl_walk(payload, label, ledger, tally, out)
    return _finish_schl_row(out)


def _measure_bnkl_entries(archive: Any, indices: Sequence[int], name: str, ledger: Ledger,
                          tally: Dict[str, Any]) -> Dict[str, Any]:
    out = {"members": len(indices), "parsed": 0, "refused": 0, "sounds": 0}
    tally["bnkl_members"] += len(indices)
    for index in indices:
        label = _entry_label(name, archive.entry(index))
        try:
            payload = _entry_bytes(archive, index)
        except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
            out["refused"] += 1
            tally["bnkl_refused"] += 1
            ledger.add("ea_big.member", label, exc)
            continue
        _measure_one_bnkl(payload, label, ledger, tally, out)
    return out


def _measure_one_bnkl(payload: bytes, where: str, ledger: Ledger, tally: Dict[str, Any],
                      out: Dict[str, Any]) -> None:
    try:
        bank = ea_schl.parse_bank(payload, 0, len(payload))
    except (Refusal, ValueError, struct.error, IndexError) as exc:
        out["refused"] += 1
        tally["bnkl_refused"] += 1
        ledger.add("ea_schl.parse_bank", where, exc)
        return
    out["parsed"] += 1
    out["sounds"] += len(bank.sounds)
    tally["bnkl_parsed"] += 1
    tally["bnkl_sounds"] += len(bank.sounds)


def _measure_tdb_entries(archive: Any, indices: Sequence[int], name: str, ledger: Ledger,
                         tally: Dict[str, Any]) -> Dict[str, Any]:
    out = {"total": len(indices), "parsed": 0, "refused": 0, "crc_sites": 0,
           "crc_matched": 0, "crc_refused": 0, "tables": 0, "fields": 0}
    for index in indices:
        label = _entry_label(name, archive.entry(index))
        tally["tdb_total"] += 1
        try:
            payload = _entry_bytes(archive, index)
        except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
            out["refused"] += 1
            tally["tdb_refused"] += 1
            ledger.add("ea_big.member", label, exc)
            continue
        _measure_one_tdb(payload, label, ledger, tally, out)
    return out


def _measure_mmap_entries(archive: Any, indices: Sequence[int], name: str, ledger: Ledger,
                          tally: Dict[str, Any], *, sample: Optional[int]) -> Dict[str, Any]:
    chosen = _evenly(indices, sample)
    out = {"members": len(indices), "sampled": len(chosen), "parsed": 0, "refused": 0,
           "image0_decoded": 0, "image0_refused": 0}
    tally["mmap_members"] += len(indices)
    tally["mmap_sampled"] += len(chosen)
    for index in chosen:
        label = _entry_label(name, archive.entry(index))
        try:
            payload = _entry_bytes(archive, index)
        except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
            out["refused"] += 1
            tally["mmap_refused"] += 1
            ledger.add("ea_big.member", label, exc)
            continue
        try:
            texture = mmap_art.parse(payload)
            reason = texture.undecodable_reason(texture.image(0)) if texture.images else \
                "this member declares no images"
            if reason is not None:
                raise ReadinessError(str(reason))
            width, height, rgba = mmap_art.decode_rgba(payload, image=0, texture=texture)
        except (Refusal, ReadinessError, ValueError, struct.error, IndexError, MemoryError) as exc:
            out["image0_refused"] += 1
            tally["mmap_image0_refused"] += 1
            tally["mmap_reasons"][refusal_class(exc)] += 1
            ledger.add("mmap_art.decode_rgba", label, exc)
            continue
        assert len(rgba) == width * height * 4
        del rgba
        out["parsed"] += 1
        out["image0_decoded"] += 1
        tally["mmap_parsed"] += 1
        tally["mmap_image0_decoded"] += 1
        tally["mmap_dimensions"]["%dx%d" % (width, height)] += 1
    return out


def _measure_nested(archive: Any, indices: Sequence[int], name: str, ledger: Ledger,
                    tally: Dict[str, Any], *, sample: Optional[int], depth: int,
                    passes: Dict[str, Any]) -> Dict[str, Any]:
    chosen = _evenly(indices, sample)
    out = {"archives": len(indices), "sampled": len(chosen), "opened": 0,
           "refused": 0, "entries": 0}
    tally["big_nested"] += len(indices)
    tally["big_nested_unopened"] += len(indices) - len(chosen)
    for index in chosen:
        label = _entry_label(name, archive.entry(index))
        tally["big_archives"] += 1
        try:
            # A stored nested archive is opened in place through the same
            # window (nothing is copied); a packed one has to be unpacked, and
            # is unpacked through the uncached path so a census of 13,000 of
            # them does not hold every one alive.
            inner = (ea_big.parse_big(_entry_bytes(archive, index), name=label)
                     if archive.is_compressed(index) else archive.nested(index))
        except (Refusal, ReadinessError, ValueError, struct.error, IndexError, MemoryError) as exc:
            out["refused"] += 1
            tally["big_archives_refused"] += 1
            ledger.add("ea_big.parse_big", label, exc)
            continue
        out["opened"] += 1
        try:
            inner_head = archive.member(index, max_output=ea_big.BIG_HEADER_SIZE)
        except (Refusal, ValueError, struct.error, IndexError, MemoryError):
            inner_head = None
        row = measure_archive(inner, label, ledger, tally, head=inner_head,
                              available=inner.length, depth=depth + 1, **passes)
        out["entries"] += row["entries"]
    return out


def measure_archive(archive: Any, name: str, ledger: Ledger, tally: Dict[str, Any], *,
                    head: "bytes | None" = None, available: Optional[int] = None,
                    shps_sample: Optional[int] = DEFAULT_SHPS_SAMPLE,
                    schl_sample: Optional[int] = DEFAULT_SCHL_SAMPLE,
                    nested_sample: Optional[int] = DEFAULT_NESTED_SAMPLE,
                    mmap_sample: Optional[int] = DEFAULT_MMAP_SAMPLE,
                    depth: int = 0, max_depth: int = ARCHIVE_MAX_DEPTH,
                    deep: bool = True) -> Dict[str, Any]:
    """Every reader the BIG lane ships, run over one opened ``BIGF`` archive.

    *tally* is the disc-wide accumulator; the returned dictionary is this
    archive's own row.  A caller hands the archive already opened, because a
    refusal to open it is the caller's row to record.
    """

    summary = archive.summary()
    order, note = size_field(archive, head, archive.length if available is None else available)
    row: Dict[str, Any] = {
        "format": archive.format, "depth": depth,
        "size_field": order, "size_note": note,
        "declared_size": archive.declared_size, "length": archive.length,
        "entries": len(archive.entries), "index_bytes": archive.index_bytes,
        "alignment": summary["alignment"], "duplicate_names": archive.duplicate_names,
        "empty_entries": summary["empty_entries"], "payload_bytes": summary["payload_bytes"],
        "entry_span": max([entry.end for entry in archive.entries if entry.size] or [archive.index_bytes]),
        "layout_notes": summary["layout_notes"][:4],
        "names_sample": [entry.name for entry in archive.entries[:6]],
    }
    tally["big_archives_opened"] += 1
    if depth:
        tally["big_nested_opened"] += 1
    tally["big_size_fields"][order] += 1
    tally["big_alignments"][str(summary["alignment"])] += 1
    if summary["layout_notes"]:
        tally["big_archives_with_layout_notes"] += 1

    probe_everything = bool(DATA_TABLE_RE.search(name))
    formats: Counter = Counter()
    by_format: Dict[str, List[int]] = {}
    packed_total = packed_ok = refused = 0
    for entry in archive.entries:
        tally["big_entries"] += 1
        tally["big_extensions"][entry.extension or "(none)"] += 1
        if entry.size == 0:
            formats[ea_big.FORMAT_EMPTY] += 1
            tally["big_entries_classified"] += 1
            tally["big_entry_formats"][ea_big.FORMAT_EMPTY] += 1
            continue
        label = _entry_label(name, entry)
        try:
            packed = archive.is_compressed(entry.index)
        except (Refusal, ValueError, struct.error, IndexError) as exc:
            refused += 1
            tally["big_entries_refused"] += 1
            ledger.add("ea_big.stored", label, exc)
            continue
        if packed:
            packed_total += 1
            tally["refpack_entries"] += 1
        try:
            first = archive.member(entry.index, max_output=ea_big.IDENTIFY_HEAD)
        except (Refusal, ValueError, struct.error, IndexError, MemoryError) as exc:
            refused += 1
            tally["big_entries_refused"] += 1
            if packed:
                tally["refpack_refused"] += 1
            ledger.add("ea_big.refpack_decompress" if packed else "ea_big.stored", label, exc)
            continue
        if packed:
            packed_ok += 1
            tally["refpack_unpacked"] += 1
            header = archive.compression(entry.index)
            if header is not None:
                tally["refpack_declared_bytes"] += header.decompressed_size
        tally["big_entries_classified"] += 1
        kind = ea_terf.identify_member(first) or ea_big.FORMAT_UNCLASSIFIED
        formats[kind] += 1
        tally["big_entry_formats"][kind] += 1
        by_format.setdefault(kind, []).append(entry.index)
        if (probe_everything or DATA_TABLE_RE.search(entry.name)) and entry.size <= DATA_PROBE_CAP_BYTES:
            try:
                _probe_data_table(_entry_bytes(archive, entry.index), label, tally, "archive entry")
            except (Refusal, ReadinessError, ValueError, struct.error, MemoryError) as exc:
                ledger.add("ea_big.member", label, exc)
    row["formats"] = dict(sorted(formats.items(), key=lambda kv: (-kv[1], kv[0])))
    row["entries_classified"] = len(archive.entries) - refused
    row["entries_refused"] = refused
    row["refpack_entries"] = packed_total
    row["refpack_unpacked"] = packed_ok
    if not deep:
        return row

    passes = {"shps_sample": shps_sample, "schl_sample": schl_sample,
              "nested_sample": nested_sample, "mmap_sample": mmap_sample,
              "max_depth": max_depth, "deep": deep}
    if by_format.get("SHPS"):
        row["shps"] = _measure_shps_entries(archive, by_format["SHPS"], name, ledger, tally,
                                            sample=shps_sample)
    if by_format.get("SCHl"):
        row["schl"] = _measure_schl_entries(archive, by_format["SCHl"], name, ledger, tally,
                                            sample=schl_sample)
    if by_format.get("BNKl"):
        row["bnkl"] = _measure_bnkl_entries(archive, by_format["BNKl"], name, ledger, tally)
    if by_format.get("TDB"):
        row["tdb"] = _measure_tdb_entries(archive, by_format["TDB"], name, ledger, tally)
    if by_format.get("MMAP"):
        row["mmap"] = _measure_mmap_entries(archive, by_format["MMAP"], name, ledger, tally,
                                            sample=mmap_sample)
    if by_format.get("BIGF"):
        if depth < max_depth:
            row["nested"] = _measure_nested(archive, by_format["BIGF"], name, ledger, tally,
                                            sample=nested_sample, depth=depth, passes=passes)
        else:
            count = len(by_format["BIGF"])
            row["nested"] = {"archives": count, "sampled": 0, "opened": 0, "refused": 0,
                             "entries": 0, "note": "past the tool's archive depth of %d" % max_depth}
            tally["big_nested"] += count
            tally["big_nested_unopened"] += count
    return row


def measure_loose_refpack(data: bytes, path: str, ledger: Ledger,
                          tally: Dict[str, Any]) -> Dict[str, Any]:
    """A file that is a RefPack stream in its own right, outside any archive.

    NBA Street Vol. 2 keeps 22 of them -- fonts, palettes, layout and the whole
    front-end art set -- and NBA Street V3, FIFA Street and FIFA 14 keep a
    handful each.  The row records what the reader makes of it, including when
    the reader refuses: the ``C0 FB`` spelling is **not** the family marker
    ``ea_big.is_refpack`` tests for, and saying so with the reader's own
    sentence is the measurement.
    """

    tally["loose_refpack"] += 1
    row: Dict[str, Any] = {"bytes": len(data), "head": data[:2].hex()}
    header = ea_big.refpack_header(data)
    row["declared"] = None if header is None else header.decompressed_size
    try:
        unpacked = ea_big.refpack_decompress(data, max_output=MEMBER_HEAD, what=path)
    except (Refusal, ValueError, struct.error, IndexError, MemoryError) as exc:
        tally["loose_refpack_refused"] += 1
        row["format"] = ea_big.FORMAT_UNDECODABLE
        ledger.add("ea_big.refpack_decompress", path, exc)
        tally["loose_refpack_formats"][ea_big.FORMAT_UNDECODABLE] += 1
        return row
    tally["loose_refpack_unpacked"] += 1
    if header is not None:
        tally["refpack_declared_bytes"] += header.decompressed_size
    kind = ea_terf.identify_member(unpacked) or ea_big.FORMAT_UNCLASSIFIED
    row["format"] = kind
    tally["loose_refpack_formats"][kind] += 1
    return row



#: A loose audio file larger than this has its header read and its stream walk
#: skipped: a 700 MB speech container answers the header row either way.
LOOSE_WALK_CAP = 16 << 20


def measure_loose_archive(extent: Any, path: str, ledger: Ledger, tally: Dict[str, Any],
                          *, passes: Dict[str, Any]) -> Dict[str, Any]:
    """One file on the disc whose magic is ``BIGF`` or ``BIG4``, under ``ea_big``.

    A ``BIG4`` file reaches this function and is **refused by name** by the
    reader; the row keeps the refusal, because "the reader will not open it"
    and "there is nothing there" must not render the same.
    """

    tally["big_archives"] += 1
    # The whole path, not the basename: an entry's label then says which archive
    # on which disc it came out of, and the database probe can see a name like
    # ``/DATA/DATABASE/SCHEDULE.BIG`` that its own basename does not carry.
    name = path
    try:
        head = extent.read(0, min(ea_big.BIG_HEADER_SIZE, extent.size))
    except (mapper.MapError, OSError, ValueError) as exc:
        tally["big_archives_refused"] += 1
        ledger.add("ps2_iso9660.read", path, exc)
        return {"error": str(exc)[:220], "iso_length": extent.size}
    view = None
    try:
        try:
            view = extent.view(extent.size)
            source: Any = view.data
        except (mapper.MapError, OSError, ValueError, MemoryError):
            view = None
            source = lambda offset, length: extent.read(offset, length)  # noqa: E731
        try:
            archive = ea_big.parse_big(source, size=extent.size, name=name)
        except (Refusal, mapper.MapError, ValueError, struct.error, OSError, MemoryError) as exc:
            tally["big_archives_refused"] += 1
            ledger.add("ea_big.parse_big", path, exc)
            return {"error": str(exc)[:220], "iso_length": extent.size,
                    "magic": head[:4].decode("latin-1", "replace")}
        row = measure_archive(archive, name, ledger, tally, head=head,
                              available=extent.size, **passes)
        row["iso_length"] = extent.size
        return row
    finally:
        if view is not None:
            view.close()


def measure_loose_bank(payload: bytes, path: str, ledger: Ledger,
                       tally: Dict[str, Any]) -> Dict[str, Any]:
    """A bare ``SHPS`` image bank sitting on the disc outside any archive."""

    out = _new_shps_row(1, 1)
    tally["shps_banks"] += 1
    tally["shps_sampled"] += 1
    _measure_one_shps(payload, path, ledger, tally, out)
    return out


# --------------------------------------------------------------------------
# The preload caches, checked against the containers they copy
# --------------------------------------------------------------------------
def measure_caches(handle: Any, image: Any, caches: Sequence[Any], by_name: Dict[str, Any],
                   ledger: Ledger) -> Dict[str, Any]:
    """Every ``QL01`` cache, parsed and its copies compared with the real bytes.

    The module's own parser (``containers.parse_preload_cache``) and the
    module's own rule for how long a copy is (``PreloadCopy.length_in``).  A
    cache whose copies do not match is the single fact that decides whether a
    writer for that disc can leave the caches alone.
    """

    out: Dict[str, Any] = {
        "files": len(caches), "parsed": 0, "refused": 0, "unread": 0,
        "copies": 0, "header_copies": 0, "member_copies": 0,
        "identical": 0, "differing": 0, "unresolved": 0,
        "containers_named": 0, "per_cache": {}, "unresolved_kinds": {},
    }
    unresolved_kinds: Counter = Counter()
    named: Dict[str, List[Any]] = {}
    for entry in caches:
        name = entry.path.rsplit("/", 1)[-1]
        if entry.length > CACHE_CAP:
            out["unread"] += 1
            ledger.add("ea_module_readiness", name,
                       "this preload cache is %d byte(s), past the tool's %d-byte cap; it is "
                       "listed unread." % (entry.length, CACHE_CAP))
            continue
        extent = mapper._Extent(handle, image, entry)
        try:
            data = extent.read(0, entry.length)
        except (mapper.MapError, OSError, ValueError) as exc:
            out["refused"] += 1
            ledger.add("ps2_iso9660.read", name, exc)
            continue
        try:
            copies = m09.parse_preload_cache(data, name)
        except (Refusal, ValueError, struct.error, IndexError) as exc:
            out["refused"] += 1
            ledger.add("containers.parse_preload_cache", name, exc)
            continue
        out["parsed"] += 1
        row = {"bytes": entry.length, "copies": len(copies),
               "header_copies": sum(1 for c in copies if c.is_header),
               "member_copies": sum(1 for c in copies if not c.is_header),
               "containers": len({c.container for c in copies}),
               "identical": 0, "differing": 0, "unresolved": 0}
        out["per_cache"][name] = row
        out["copies"] += len(copies)
        out["header_copies"] += row["header_copies"]
        out["member_copies"] += row["member_copies"]
        for copy in copies:
            named.setdefault(copy.container, []).append((name, copy, data))
    out["containers_named"] = len(named)
    for container_name, items in sorted(named.items()):
        entry = by_name.get(container_name.upper())
        if entry is None:
            out["unresolved"] += len(items)
            for cache_name, _copy, _data in items[:1]:
                ledger.add("containers.preload_copies", cache_name,
                           "the cache names %s and no file of that name is on this disc, so its "
                           "copies cannot be checked." % container_name)
            for cache_name, _copy, _data in items:
                out["per_cache"][cache_name]["unresolved"] += 1
            continue
        extent = mapper._Extent(handle, image, entry)
        view = None
        try:
            length, _short = mapper.container_span(extent)
            view = extent.view(length)
            parsed = ea_terf.parse_terf(view.data, allow_size_mismatch=True)
            for cache_name, copy, data in items:
                try:
                    want = copy.length_in(parsed)
                    original = (bytes(view.data[:want]) if copy.is_header
                                else parsed.stored(copy.member))
                except (Refusal, ValueError, struct.error, IndexError) as exc:
                    out["unresolved"] += 1
                    out["per_cache"][cache_name]["unresolved"] += 1
                    # The copy is still there; say what format its first bytes carry,
                    # so "unresolved" is a fact about the cache's bookkeeping rather
                    # than a shrug about its contents.
                    unresolved_kinds[mapper.identify_head(bytes(data[copy.offset:copy.offset + 16]))] += 1
                    ledger.add("containers.PreloadCopy.length_in", f"{cache_name}->{container_name}", exc)
                    continue
                stored = bytes(data[copy.offset:copy.offset + want])
                if stored == original:
                    out["identical"] += 1
                    out["per_cache"][cache_name]["identical"] += 1
                else:
                    out["differing"] += 1
                    out["per_cache"][cache_name]["differing"] += 1
                    ledger.add("containers.preload_copies", f"{cache_name}->{container_name}",
                               "a %s copy of %s is not byte-identical to what it copies; a writer "
                               "for this disc cannot assume the cache mirrors the container."
                               % ("header" if copy.is_header else "member", container_name))
        except (Refusal, mapper.MapError, ValueError, struct.error, OSError) as exc:
            out["unresolved"] += len(items)
            ledger.add("ea_terf.parse_terf", container_name, exc)
        finally:
            if view is not None:
                view.close()
    out["unresolved_kinds"] = dict(unresolved_kinds.most_common(8))
    return out


# --------------------------------------------------------------------------
# One disc
# --------------------------------------------------------------------------
def _new_tally() -> Dict[str, Any]:
    return {
        "members": 0, "members_head_decoded": 0, "members_refused": 0,
        "formats": Counter(), "codecs": Counter(), "chains": Counter(), "alignments": Counter(),
        "tdb_total": 0, "tdb_parsed": 0, "tdb_refused": 0, "tdb_tables": 0, "tdb_fields": 0,
        "crc_sites": 0, "crc_matched": 0, "crc_refused": 0,
        "mmap_members": 0, "mmap_sampled": 0, "mmap_parsed": 0, "mmap_refused": 0,
        "mmap_images": 0, "mmap_image0_decoded": 0, "mmap_image0_refused": 0,
        "mmap_dimensions": Counter(), "mmap_reasons": Counter(),
        "schl_members": 0, "schl_headers_parsed": 0, "schl_headers_refused": 0,
        "schl_decodable": 0, "schl_undecodable": 0, "schl_codecs": Counter(),
        "schl_platforms": Counter(), "schl_walked_members": 0, "schl_streams": 0,
        "schl_streams_complete": 0,
        "bnkl_members": 0, "bnkl_parsed": 0, "bnkl_refused": 0, "bnkl_sounds": 0,
        "table_names": Counter(), "schemas": {},
        # -- the EA BIG family ------------------------------------------------
        "big_archives": 0, "big_archives_opened": 0, "big_archives_refused": 0,
        "big_archives_with_layout_notes": 0,
        "big_nested": 0, "big_nested_opened": 0, "big_nested_unopened": 0,
        "big_entries": 0, "big_entries_classified": 0, "big_entries_refused": 0,
        "big_entry_formats": Counter(), "big_extensions": Counter(),
        "big_size_fields": Counter(), "big_alignments": Counter(),
        "refpack_entries": 0, "refpack_unpacked": 0, "refpack_refused": 0,
        "refpack_declared_bytes": 0,
        "loose_refpack": 0, "loose_refpack_unpacked": 0, "loose_refpack_refused": 0,
        "loose_refpack_formats": Counter(),
        "shps_banks": 0, "shps_sampled": 0, "shps_parsed": 0, "shps_refused": 0,
        "shps_images": 0, "shps_decoded": 0, "shps_image_refused": 0,
        "shps_mip_images": 0,
        "shps_block_codes": Counter(), "shps_decoded_codes": Counter(),
        "shps_refused_codes": Counter(), "shps_reasons": Counter(),
        "shps_dimensions": Counter(), "shps_endians": Counter(),
        "shps_directory_ids": Counter(),
        "data_probes": [], "data_magics": Counter(), "data_kinds": Counter(), "data_tdb": 0,
    }


def _reader_digests() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for name, relative in READER_FILES:
        path = _ROOT / relative
        try:
            out[name] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        except OSError:
            out[name] = "missing"
    return out


def measure_disc(iso_path: Path, *, label: str = "",
                 mmap_sample: Optional[int] = DEFAULT_MMAP_SAMPLE,
                 schl_sample: Optional[int] = DEFAULT_SCHL_SAMPLE,
                 shps_sample: Optional[int] = DEFAULT_SHPS_SAMPLE,
                 nested_sample: Optional[int] = DEFAULT_NESTED_SAMPLE,
                 archive_depth: int = ARCHIVE_MAX_DEPTH,
                 deep: bool = True, data_only: bool = False,
                 progress: Callable[[str], None] = lambda line: None) -> Dict[str, Any]:
    """Run the module's readers over one disc and return the readiness record."""

    started = time.time()
    ledger = Ledger()
    tally = _new_tally()
    timings: Dict[str, float] = {}

    try:
        image = iso.open_image(iso_path)
    except (iso.Iso9660Error, OSError, ValueError) as exc:
        raise ReadinessError(
            "%s could not be opened as a PlayStation 2 disc image: %s" % (iso_path.name, exc))
    summary = iso.summarise(image)
    identity = iso.boot_identity(image)
    boot_entry = iso.find(image, "/" + identity["boot_file"]) if identity.get("boot_file") else None
    elf = iso.read_file(image, boot_entry) if boot_entry is not None else b""
    identity["pcsx2_crc"] = ps2_elf.pcsx2_crc(elf) if elf[:4] == b"\x7fELF" else None
    identity["boot_segments"] = None
    if elf[:4] == b"\x7fELF":
        try:
            identity["boot_segments"] = len(ps2_elf.parse_program_headers(elf))
        except (Refusal, ValueError, struct.error) as exc:
            ledger.add("ps2_elf.parse_program_headers", identity.get("boot_file") or "boot", exc)
    del elf

    loose_audio: Dict[str, Any] = {}
    archive_passes: Dict[str, Any] = {
        "shps_sample": shps_sample, "schl_sample": schl_sample,
        "nested_sample": nested_sample, "mmap_sample": mmap_sample,
        "max_depth": archive_depth, "deep": deep}

    kinds: Counter = Counter()
    containers: Dict[str, Any] = {}
    databases: Dict[str, Any] = {}
    archives: Dict[str, Any] = {}
    banks: Dict[str, Any] = {}
    loose_refpack: Dict[str, Any] = {}
    caches: List[Any] = []
    by_name: Dict[str, Any] = {}
    data_files = 0
    files = 0
    container_started = time.time()
    with open(iso_path, "rb") as handle:
        for entry in iso.iter_entries(image):
            if entry.is_dir:
                continue
            files += 1
            in_data = entry.path.upper().startswith("/DATA/")
            if in_data:
                data_files += 1
                by_name[entry.path.rsplit("/", 1)[-1].upper()] = entry
            extent = mapper._Extent(handle, image, entry)
            try:
                head = extent.read(0, min(mapper.HEAD_BYTES, entry.length))
            except (mapper.MapError, OSError, ValueError) as exc:
                kinds["unreadable"] += 1
                ledger.add("ps2_iso9660.read", entry.path, exc)
                continue
            kind = mapper.identify_head(head, entry.path)
            kinds[kind] += 1
            if data_only and not in_data:
                continue
            if kind == "TERF":
                progress("container %s (%s bytes)" % (entry.path, format(entry.length, ",")))
                view = None
                try:
                    length, short_by = mapper.container_span(extent)
                    view = extent.view(length)
                    row = measure_container(view.data, entry.path.rsplit("/", 1)[-1], ledger, tally,
                                            mmap_sample=mmap_sample, schl_sample=schl_sample, deep=deep)
                    row["iso_length"] = entry.length
                    if short_by:
                        row["iso_short_by"] = short_by
                    containers[entry.path] = row
                except (Refusal, mapper.MapError, ValueError, struct.error, OSError, MemoryError) as exc:
                    containers[entry.path] = {"error": str(exc)[:220], "iso_length": entry.length}
                    ledger.add("ea_terf.parse_terf", entry.path, exc)
                finally:
                    if view is not None:
                        view.close()
            elif kind == "TDB":
                out = {"total": 1, "parsed": 0, "refused": 0, "crc_sites": 0,
                       "crc_matched": 0, "crc_refused": 0, "tables": 0, "fields": 0}
                tally["tdb_total"] += 1
                try:
                    payload = extent.read(0, entry.length)
                except (mapper.MapError, OSError, ValueError) as exc:
                    out["refused"] += 1
                    tally["tdb_refused"] += 1
                    ledger.add("ps2_iso9660.read", entry.path, exc)
                else:
                    _measure_one_tdb(payload, entry.path, ledger, tally, out)
                databases[entry.path] = out
            elif kind == "QL01":
                caches.append(entry)
            elif kind == "BIGF":
                progress("archive %s (%s bytes)" % (entry.path, format(entry.length, ",")))
                archives[entry.path] = measure_loose_archive(
                    extent, entry.path, ledger, tally, passes=archive_passes)
            elif kind == "SHPS":
                try:
                    payload = extent.read(0, min(entry.length, MEMBER_WHOLE_CAP))
                except (mapper.MapError, OSError, ValueError) as exc:
                    ledger.add("ps2_iso9660.read", entry.path, exc)
                else:
                    banks[entry.path] = measure_loose_bank(payload, entry.path, ledger, tally)
            elif kind == "SCHl":
                row = _new_schl_row(1)
                tally["schl_members"] += 1
                try:
                    audio_head = extent.read(0, min(entry.length, SCHL_HEAD_BYTES))
                except (mapper.MapError, OSError, ValueError) as exc:
                    row["headers_refused"] += 1
                    tally["schl_headers_refused"] += 1
                    ledger.add("ps2_iso9660.read", entry.path, exc)
                else:
                    _schl_header_row(audio_head, entry.path, ledger, tally, row)
                    if entry.length <= LOOSE_WALK_CAP:
                        _schl_walk(extent.read(0, entry.length), entry.path, ledger, tally, row)
                loose_audio[entry.path] = _finish_schl_row(row)
            elif kind == "BNKl":
                row = {"members": 1, "parsed": 0, "refused": 0, "sounds": 0}
                tally["bnkl_members"] += 1
                try:
                    payload = extent.read(0, min(entry.length, MEMBER_WHOLE_CAP))
                except (mapper.MapError, OSError, ValueError) as exc:
                    row["refused"] += 1
                    tally["bnkl_refused"] += 1
                    ledger.add("ps2_iso9660.read", entry.path, exc)
                else:
                    _measure_one_bnkl(payload, entry.path, ledger, tally, row)
                loose_audio[entry.path] = row
            elif ea_big.is_refpack(head[:2]) or head[:2] == ea_big.C0FB_HEAD:
                try:
                    payload = extent.read(0, min(entry.length, MEMBER_WHOLE_CAP))
                except (mapper.MapError, OSError, ValueError) as exc:
                    ledger.add("ps2_iso9660.read", entry.path, exc)
                else:
                    loose_refpack[entry.path] = measure_loose_refpack(
                        payload, entry.path, ledger, tally)
            if (kind not in CONTAINER_KINDS and DATA_TABLE_RE.search(entry.path)
                    and 0 < entry.length <= DATA_PROBE_CAP_BYTES):
                try:
                    _probe_data_table(extent.read(0, entry.length), entry.path, tally, "loose file")
                except (mapper.MapError, OSError, ValueError) as exc:
                    ledger.add("ps2_iso9660.read", entry.path, exc)
    timings["containers"] = round(time.time() - container_started, 1)

    cache_started = time.time()
    with open(iso_path, "rb") as handle:
        cache_row = measure_caches(handle, image, caches, by_name, ledger)
    timings["caches"] = round(time.time() - cache_started, 1)

    counts = _counts_of(tally, containers, databases, cache_row)
    schemas = {name: {sig: {k: v for k, v in shape.items()}
                      for sig, shape in shapes.items()}
               for name, shapes in tally["schemas"].items()
               if name in SCHEMA_TABLES}
    return {
        "schema": SCHEMA,
        "label": label or iso_path.stem,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "readers": _reader_digests(),
        "image": {"name": iso_path.name, "size": iso_path.stat().st_size,
                  **{k: summary[k] for k in ("sector_size", "layout", "volume_id", "files", "directories")
                     if k in summary}},
        "identity": {k: identity.get(k) for k in
                     ("serial", "boot_file", "boot_sha256", "boot_size", "pcsx2_crc", "boot_segments")},
        "settings": {"mmap_sample": mmap_sample, "schl_sample": schl_sample,
                     "shps_sample": shps_sample, "nested_sample": nested_sample,
                     "archive_depth": archive_depth,
                     "deep": deep, "data_only": data_only,
                     "member_head_bytes": MEMBER_HEAD, "schl_head_bytes": SCHL_HEAD_BYTES},
        "kinds": dict(kinds.most_common()),
        "files": files, "data_files": data_files,
        "counts": counts,
        "containers": containers,
        "databases": databases,
        "archives": archives,
        "image_banks": banks,
        "loose_audio": loose_audio,
        "loose_refpack": loose_refpack,
        "data_tables": tally["data_probes"],
        "caches": cache_row,
        "table_names": dict(tally["table_names"].most_common(40)),
        "schemas": schemas,
        "refusals": ledger.as_list(),
        "refusals_total": ledger.total(),
        "timings": timings,
        "seconds": round(time.time() - started, 1),
    }


def _counts_of(tally: Dict[str, Any], containers: Dict[str, Any], databases: Dict[str, Any],
               caches: Dict[str, Any]) -> Dict[str, Any]:
    parsed = [c for c in containers.values() if "error" not in c]
    bare_parsed = sum(row["parsed"] for row in databases.values())
    return {
        "containers": {"total": len(containers), "works": len(parsed),
                       "refused": len(containers) - len(parsed)},
        "members": {"total": tally["members"], "works": tally["members_head_decoded"],
                    "refused": tally["members_refused"]},
        "tdb": {"total": tally["tdb_total"], "works": tally["tdb_parsed"],
                "refused": tally["tdb_refused"], "bare_files": len(databases),
                "bare_parsed": bare_parsed, "tables": tally["tdb_tables"], "fields": tally["tdb_fields"]},
        "crc_sites": {"total": tally["crc_sites"], "works": tally["crc_matched"],
                      "refused": tally["crc_sites"] - tally["crc_matched"],
                      "databases_refused": tally["crc_refused"]},
        "mmap": {"members": tally["mmap_members"], "sampled": tally["mmap_sampled"],
                 "parsed": tally["mmap_parsed"], "members_refused": tally["mmap_refused"],
                 "total": tally["mmap_sampled"], "works": tally["mmap_image0_decoded"],
                 "refused": tally["mmap_sampled"] - tally["mmap_image0_decoded"],
                 "images_in_sample": tally["mmap_images"],
                 "dimensions": dict(tally["mmap_dimensions"].most_common(12)),
                 "reasons": dict(tally["mmap_reasons"].most_common(8))},
        "schl": {"total": tally["schl_members"], "works": tally["schl_decodable"],
                 "refused": tally["schl_members"] - tally["schl_decodable"],
                 "headers_parsed": tally["schl_headers_parsed"],
                 "headers_refused": tally["schl_headers_refused"],
                 "undecodable": tally["schl_undecodable"],
                 "codecs": dict(tally["schl_codecs"].most_common(8)),
                 "platforms": dict(tally["schl_platforms"].most_common(4)),
                 "walked_members": tally["schl_walked_members"],
                 "streams_in_sample": tally["schl_streams"],
                 "streams_complete": tally["schl_streams_complete"]},
        "bnkl": {"total": tally["bnkl_members"], "works": tally["bnkl_parsed"],
                 "refused": tally["bnkl_refused"], "sounds": tally["bnkl_sounds"]},
        "caches": {"total": caches["files"], "works": caches["parsed"],
                   "refused": caches["files"] - caches["parsed"],
                   "copies": caches["copies"], "identical": caches["identical"],
                   "differing": caches["differing"], "unresolved": caches["unresolved"]},
        "formats": dict(tally["formats"].most_common()),
        "codecs": dict(tally["codecs"]),
        "chains": dict(tally["chains"].most_common()),
        "alignments": dict(tally["alignments"].most_common()),
        "big": {"total": tally["big_archives"], "works": tally["big_archives_opened"],
                "refused": tally["big_archives_refused"],
                "loose": tally["big_archives"] - tally["big_nested"],
                "nested": tally["big_nested"], "nested_opened": tally["big_nested_opened"],
                "nested_unopened": tally["big_nested_unopened"],
                "with_layout_notes": tally["big_archives_with_layout_notes"],
                "size_fields": dict(tally["big_size_fields"].most_common()),
                "alignments": dict(tally["big_alignments"].most_common(8))},
        "big_entries": {"total": tally["big_entries"], "works": tally["big_entries_classified"],
                        "refused": tally["big_entries_refused"],
                        "formats": dict(tally["big_entry_formats"].most_common()),
                        "extensions": dict(tally["big_extensions"].most_common(16))},
        "refpack": {"total": tally["refpack_entries"] + tally["loose_refpack"],
                    "works": tally["refpack_unpacked"] + tally["loose_refpack_unpacked"],
                    "refused": tally["refpack_refused"] + tally["loose_refpack_refused"],
                    "packed_entries": tally["refpack_entries"],
                    "loose_files": tally["loose_refpack"],
                    "loose_unpacked": tally["loose_refpack_unpacked"],
                    "loose_formats": dict(tally["loose_refpack_formats"].most_common(8)),
                    "declared_bytes": tally["refpack_declared_bytes"]},
        "shps": {"total": tally["shps_images"], "works": tally["shps_decoded"],
                 "refused": tally["shps_image_refused"],
                 "banks": tally["shps_banks"], "sampled": tally["shps_sampled"],
                 "banks_parsed": tally["shps_parsed"], "banks_refused": tally["shps_refused"],
                 "mip_images": tally["shps_mip_images"],
                 # Every code, not a top-N: a block code that appears twice on a
                 # disc is exactly the kind of thing a truncated histogram hides,
                 # and the refused counts have to add up to the refused total.
                 "block_codes": dict(tally["shps_block_codes"].most_common()),
                 "decoded_codes": dict(tally["shps_decoded_codes"].most_common()),
                 "refused_codes": dict(tally["shps_refused_codes"].most_common()),
                 "reasons": dict(tally["shps_reasons"].most_common(6)),
                 "dimensions": dict(tally["shps_dimensions"].most_common(12)),
                 "endians": dict(tally["shps_endians"].most_common(4)),
                 "directory_ids": dict(tally["shps_directory_ids"].most_common(6))},
        "data_tables": {"total": sum(tally["data_magics"].values()),
                        "opens_as_tdb": tally["data_tdb"],
                        "magics": dict(tally["data_magics"].most_common()),
                        "formats": dict(tally["data_kinds"].most_common(8))},
    }


# --------------------------------------------------------------------------
# Schema comparison against the control
# --------------------------------------------------------------------------
def dominant_shape(shapes: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The most common shape a table name has on one disc, or ``None``."""

    if not shapes:
        return None
    return max(shapes.values(), key=lambda s: (s.get("count", 0), s.get("field_count", 0)))


def compare_table(mine: Optional[Dict[str, Any]], base: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """One table's schema against the control's, by field name and bit width."""

    if mine is None and base is None:
        return {"verdict": "absent from both"}
    if mine is None:
        return {"verdict": "absent here", "baseline_fields": base.get("field_count")}
    if base is None:
        return {"verdict": "absent from the control", "fields": mine.get("field_count")}
    my_fields = {f[0]: (f[1], f[2], f[3]) for f in (mine.get("fields") or [])}
    base_fields = {f[0]: (f[1], f[2], f[3]) for f in (base.get("fields") or [])}
    if not my_fields or not base_fields:
        return {"verdict": "field lists not recorded", "fields": mine.get("field_count"),
                "baseline_fields": base.get("field_count")}
    shared = sorted(set(my_fields) & set(base_fields))
    only_here = sorted(set(my_fields) - set(base_fields))
    only_base = sorted(set(base_fields) - set(my_fields))
    widths = [[name, my_fields[name][1], base_fields[name][1]]
              for name in shared if my_fields[name][1] != base_fields[name][1]]
    offsets = [name for name in shared if my_fields[name][2] != base_fields[name][2]]
    if not only_here and not only_base and not widths and not offsets:
        verdict = "identical"
    elif not only_here and not only_base and not widths:
        verdict = "same names and widths, %d field(s) at a different bit offset" % len(offsets)
    elif not only_here and not only_base:
        verdict = "same %d field names, %d width(s) differ" % (len(shared), len(widths))
    else:
        verdict = "%d shared name(s), %d only here, %d only in the control" % (
            len(shared), len(only_here), len(only_base))
    return {"verdict": verdict, "fields": mine.get("field_count"), "baseline_fields": base.get("field_count"),
            "record_bytes": mine.get("record_bytes"), "baseline_record_bytes": base.get("record_bytes"),
            "shared": len(shared), "only_here": only_here[:24], "only_baseline": only_base[:24],
            "width_differences": widths[:24], "offset_differences": len(offsets)}


def compare_schemas(mine: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    names = sorted(set(mine) | set(base), key=lambda n: (SCHEMA_TABLES.index(n) if n in SCHEMA_TABLES else 99, n))
    return {name: compare_table(dominant_shape(mine.get(name)), dominant_shape(base.get(name)))
            for name in names}


# --------------------------------------------------------------------------
# The per-disc page
# --------------------------------------------------------------------------
def _container_base(path: str) -> str:
    return path.rsplit("/", 1)[-1].rsplit(".", 1)[0].upper()


def _row(label: str, reader: str, block: Dict[str, Any], note: str = "") -> str:
    total, works, refused = block.get("total", 0), block.get("works", 0), block.get("refused", 0)
    pct = _pct(works, total)
    return "| %s | `%s` | %s | %s | %s | %s | %s |" % (
        label, reader, format(total, ","), format(works, ","), format(refused, ","),
        "—" if pct is None else "%.1f%%" % pct, note)


def _block(m: Dict[str, Any], key: str) -> Dict[str, Any]:
    """One family's counts, tolerant of a record written before it existed."""

    return m.get("counts", {}).get(key) or {}


def readiness_table(m: Dict[str, Any]) -> List[str]:
    c = m["counts"]
    big, entries, refpack, shps = (_block(m, "big"), _block(m, "big_entries"),
                                   _block(m, "refpack"), _block(m, "shps"))
    mmap_note = "sample of %s member(s) with an MMAP head" % format(c["mmap"]["members"], ",")
    schl_note = "one header per member; %s of %s header(s) parsed; %s stream(s) walked in %s sampled member(s)" % (
        format(c["schl"]["headers_parsed"], ","), format(c["schl"]["total"], ","),
        format(c["schl"]["streams_in_sample"], ","), format(c["schl"]["walked_members"], ","))
    lines = [
        "| lane | reader | total | works unchanged | refused | % | note |",
        "|---|---|---:|---:|---:|---:|---|",
        _row("containers", "ea_terf.parse_terf", c["containers"], "every `/DATA` file whose magic is `TERF`"),
        _row("members", "ea_terf.decompress_member", c["members"], "decoded to the 32-byte classify head"),
        _row("TDB databases", "ea_tdb.parse_tdb", c["tdb"],
             "%s table(s), %s field definition(s)" % (format(c["tdb"]["tables"], ","), format(c["tdb"]["fields"], ","))),
        _row("CRC sites", "ea_tdb.crc_sites", c["crc_sites"],
             "%s database(s) whose extents the reader would not guess at" % format(c["crc_sites"]["databases_refused"], ",")),
        _row("MMAP images", "mmap_art.decode_rgba", c["mmap"], mmap_note),
        _row("SCHl members", "ea_schl.parse_stream_header", c["schl"], schl_note),
        _row("BNKl banks", "ea_schl.parse_bank", c["bnkl"],
             "%s sound(s) in their directories" % format(c["bnkl"]["sounds"], ",")),
        _row("BIG archives", "ea_big.parse_big", big,
             "%s loose, %s nested (%s opened, %s left past the depth of %s)" % (
                 format(big.get("loose", 0), ","), format(big.get("nested", 0), ","),
                 format(big.get("nested_opened", 0), ","),
                 format(big.get("nested_unopened", 0), ","),
                 m.get("settings", {}).get("archive_depth", ARCHIVE_MAX_DEPTH))),
        _row("BIG entries", "ea_big.member", entries,
             "decoded to the 32-byte classify head, out of every opened archive"),
        _row("RefPack streams", "ea_big.refpack_decompress", refpack,
             "%s packed entr(ies) + %s loose file(s); %s byte(s) declared" % (
                 format(refpack.get("packed_entries", 0), ","),
                 format(refpack.get("loose_files", 0), ","),
                 format(refpack.get("declared_bytes", 0), ","))),
        _row("SHPS images", "ea_shps.decode_rgba", shps,
             "every image of %s bank(s) sampled from %s; %s bank(s) parsed, %s refused" % (
                 format(shps.get("sampled", 0), ","), format(shps.get("banks", 0), ","),
                 format(shps.get("banks_parsed", 0), ","), format(shps.get("banks_refused", 0), ","))),
        _row("preload caches", "containers.parse_preload_cache", c["caches"], "`QL01` files on the disc"),
    ]
    copies = c["caches"]
    lines.append("| cache copies | byte-compare vs the container | %s | %s | %s | %s | %s unresolved |" % (
        format(copies["copies"], ","), format(copies["identical"], ","),
        format(copies["differing"], ","),
        "—" if not copies["copies"] else "%.1f%%" % (100.0 * copies["identical"] / copies["copies"]),
        format(copies["unresolved"], ",")))
    return lines


def render_page(m: Dict[str, Any], baseline: Optional[Dict[str, Any]] = None,
                today: Optional[str] = None) -> str:
    today = today or time.strftime("%Y-%m-%d", time.gmtime())
    ident = m.get("identity", {})
    img = m.get("image", {})
    c = m["counts"]
    label = m.get("label") or img.get("name", "")
    is_control = baseline is not None and baseline.get("identity", {}).get("boot_sha256") == ident.get("boot_sha256")
    out: List[str] = [
        "# %s — how much of the Madden 09 module works on it" % label,
        "",
        "Measured %s with `tools/owner/ea_module_readiness.py` (`%s`), read-only. Source: "
        "`%s.%s.readiness.json`; every number below is copied from it."
        % (today, m.get("schema", SCHEMA), ident.get("serial"), slug(m.get("label", ""), "disc")),
        "",
        "The readers are the shipped Madden 09 ones, imported and not re-implemented: "
        "`ea_terf` `%s`, `ea_tdb` `%s`, `ea_schl` `%s`, `mmap_art` `%s`, `containers` `%s` "
        "(sha256, first 16)." % tuple(m.get("readers", {}).get(k, "?") for k in
                                      ("ea_terf", "ea_tdb", "ea_schl", "mmap_art", "containers")),
        "",
        "Retail-free: names, counts, digests and schema field names and widths. No member payload, "
        "no decoded pixel, no string out of a text bank.",
        "",
        "## Identity",
        "",
        "| field | value |",
        "|---|---|",
        "| image | `%s`, %s bytes, %s files%s |" % (
            img.get("name"), format(img.get("size", 0), ","), img.get("files"),
            "" if img.get("sector_size") in (None, 2048) else ", raw CD %d-byte sectors" % img.get("sector_size")),
        "| boot file / serial | `%s` / **%s** |" % (ident.get("boot_file"), ident.get("serial")),
        "| boot ELF sha256 | `%s` |" % (ident.get("boot_sha256") or "—"),
        "| PCSX2 CRC | `%s` |" % (ident.get("pcsx2_crc") or "—"),
        "| `/DATA` files | %s of %s files on the disc |" % (format(m.get("data_files", 0), ","), format(m.get("files", 0), ",")),
        "| wall time | %s s (containers %s s, caches %s s) |" % (
            m.get("seconds"), m.get("timings", {}).get("containers"), m.get("timings", {}).get("caches")),
        "",
        "## Readiness — what runs unchanged",
        "",
    ]
    if is_control:
        out.append("**This disc is the control.** Madden NFL 09 is the disc the readers were written "
                   "against, so its row is what \"works unchanged\" looks like at its ceiling.")
        out.append("")
    out += readiness_table(m)
    out += [
        "",
        "Definitions, so a percentage is not a decoration: *containers* is `parse_terf` returning; "
        "*members* is the stored bytes decoding as far as the 32-byte classify head, i.e. the codec is one "
        "of the three the module implements; *TDB databases* is `parse_tdb` returning; *CRC sites* is the "
        "stored CRC-32/MPEG-2 equalling the one recomputed from the file's own bytes; *MMAP images* is "
        "`decode_rgba` returning pixels for image 0 of a **sampled** member (the sample size is in the note, "
        "and the pixels are measured and dropped); *SCHl streams* is the header parsing **and** the codec "
        "being one the audio lane decodes; *BNKl banks* is `parse_bank` returning a directory; *preload "
        "caches* is `parse_preload_cache` returning, and *cache copies* is each copy being byte-identical to "
        "the container bytes it copies.",
        "",
        "### Container shapes",
        "",
        "| what | measured |",
        "|---|---|",
        "| chunk chains | %s |" % (_counts(c["chains"]) or "—"),
        "| member alignments | %s |" % (_counts(c["alignments"]) or "—"),
        "| codecs across every member directory | %s |" % (_counts(c["codecs"]) or "—"),
        "| member formats after decompression | %s |" % (_counts(c["formats"], 12) or "—"),
    ]
    if c["mmap"]["dimensions"]:
        out.append("| decoded texture sizes (sample) | %s |" % _counts(c["mmap"]["dimensions"], 8))
    if c["schl"]["codecs"]:
        out.append("| SCHl codecs (first stream of each member) | %s |" % _counts(c["schl"]["codecs"], 6))
    if c["schl"]["platforms"]:
        out.append("| SCHl platform tags | %s |" % _counts(c["schl"]["platforms"], 4))
    if c["mmap"]["reasons"]:
        out.append("| why a sampled texture would not draw | %s |" % _counts(c["mmap"]["reasons"], 4))
    out.append("")
    out += _big_section(m)
    out += _needs_section(m, baseline)
    out += _refusals_section(m)
    return "\n".join(out) + "\n"


def _big_section(m: Dict[str, Any]) -> List[str]:
    """Archives, RefPack, image banks and where the roster data lives."""

    big, entries = _block(m, "big"), _block(m, "big_entries")
    refpack, shps = _block(m, "refpack"), _block(m, "shps")
    data = _block(m, "data_tables")
    archives = m.get("archives") or {}
    if not big.get("total") and not refpack.get("total") and not shps.get("total"):
        return []
    out = ["### The EA BIG family", "",
           "| what | measured |", "|---|---|",
           "| archives | %s opened of %s (%s loose, %s nested) |" % (
               format(big.get("works", 0), ","), format(big.get("total", 0), ","),
               format(big.get("loose", 0), ","), format(big.get("nested", 0), ",")),
           "| size field, per the archive's own header | %s |" % (_counts(big.get("size_fields")) or "—"),
           "| payload alignments (measured, not declared) | %s |" % (_counts(big.get("alignments"), 6) or "—"),
           "| entry formats after RefPack | %s |" % (_counts(entries.get("formats"), 12) or "—"),
           "| entry extensions | %s |" % (_counts(entries.get("extensions"), 10) or "—"),
           "| RefPack | %s of %s stream(s) start cleanly; %s loose file(s) |" % (
               format(refpack.get("works", 0), ","), format(refpack.get("total", 0), ","),
               format(refpack.get("loose_files", 0), ",")),
           ]
    if refpack.get("loose_formats"):
        out.append("| what the loose RefPack files hold | %s |" % _counts(refpack["loose_formats"], 8))
    if big.get("with_layout_notes"):
        out.append("| archives whose layout a rewrite could not assume | %s |"
                   % format(big["with_layout_notes"], ","))
    if shps.get("banks"):
        out += ["| `SHPS` banks | %s parsed, %s refused, of %s sampled from %s |" % (
                    format(shps.get("banks_parsed", 0), ","), format(shps.get("banks_refused", 0), ","),
                    format(shps.get("sampled", 0), ","), format(shps.get("banks", 0), ",")),
                "| `SHPS` block codes, every block of every parsed bank | %s |"
                % (_counts(shps.get("block_codes")) or "—"),
                "| image codes that decoded | %s |" % (_counts(shps.get("decoded_codes")) or "—"),
                "| image codes the reader refused | %s |" % (_counts(shps.get("refused_codes")) or "—"),
                "| decoded image sizes | %s |" % (_counts(shps.get("dimensions"), 8) or "—"),
                "| bank byte order / directory ids | %s / %s |" % (
                    _counts(shps.get("endians"), 3) or "—", _counts(shps.get("directory_ids"), 4) or "—")]
        if shps.get("mip_images"):
            out.append("| images carrying a whole mip chain | %s |" % format(shps["mip_images"], ","))
    out.append("")
    rows = sorted(((row.get("entries", 0), path, row) for path, row in archives.items()
                   if "error" not in row), reverse=True)[:14]
    if rows:
        out += ["The largest archives on this disc, by declared entry count:", "",
                "| archive | bytes | size field | entries | classified | RefPack | entry formats | `SHPS` banks |",
                "|---|---:|---|---:|---:|---:|---|---:|"]
        for _count, path, row in rows:
            out.append("| `%s` | %s | %s | %s | %s | %s | %s | %s |" % (
                path, format(row.get("iso_length", row.get("length", 0)), ","),
                row.get("size_field", "—"), format(row.get("entries", 0), ","),
                format(row.get("entries_classified", 0), ","),
                format(row.get("refpack_entries", 0), ","),
                _counts(row.get("formats"), 4) or "—",
                format((row.get("shps") or {}).get("banks", 0), ",")))
        out.append("")
    refused = [(path, row) for path, row in sorted(archives.items()) if "error" in row]
    if refused:
        out += ["Archives the reader refused **by name**, which is a measurement and not a gap:", "",
                "| archive | magic | the reader's sentence |", "|---|---|---|"]
        for path, row in refused[:10]:
            out.append("| `%s` | `%s` | %s |" % (path, row.get("magic", "?"),
                                                 row["error"].replace("|", "\\|")))
        if len(refused) > 10:
            out.append("| … | | %d more, all in the refusal ledger below |" % (len(refused) - 10))
        out.append("")
    if data.get("total"):
        out += ["#### Where this disc keeps its roster and team data", "",
                "Every file and entry whose **name** is database-shaped, probed for its magic and "
                "its shape. `opens as TDB` is `ea_tdb.parse_tdb` returning; `CSV fields` is the "
                "number of comma-separated names on the first line, which is a count and not the "
                "line. A table that *is* text has no magic row at all, because the first four "
                "bytes of a CSV are four characters of its header. %s probe(s), %s of which open "
                "as an EA `TDB`." % (
                    format(data["total"], ","), format(data.get("opens_as_tdb", 0), ",")), "",
                "| magic (hex / printable), or the shape of a text table | files |", "|---|---:|"]
        for key, value in (data.get("magics") or {}).items():
            out.append("| `%s` | %s |" % (key, format(value, ",")))
        out.append("")
        probes = m.get("data_tables") or []
        if probes:
            out += ["| where | bytes | magic | first four words, LE | format | opens as TDB | CSV fields |",
                    "|---|---:|---|---|---|---|---:|"]
            for probe in probes[:24]:
                out.append("| `%s` | %s | %s | %s | %s | %s | %s |" % (
                    probe["where"], format(probe["bytes"], ","),
                    "`%s`" % probe["magic"] if probe["magic"] else "—",
                    ", ".join(str(word) for word in probe.get("first_words_le") or []) or "—",
                    probe["format"], "yes" if probe["opens_as_tdb"] else "no",
                    "—" if probe.get("csv_fields") is None else probe["csv_fields"]))
            if len(probes) > 24:
                out.append("| … | | | | | | %d more in the JSON |" % (len(probes) - 24))
            out.append("")
    return out


def _counts(d: Optional[Dict[str, Any]], limit: Optional[int] = None) -> str:
    items = sorted((d or {}).items(), key=lambda kv: (-(kv[1] if isinstance(kv[1], int) else 0), str(kv[0])))
    if limit is not None:
        items = items[:limit]
    return ", ".join("%s %s" % (k, format(v, ",") if isinstance(v, int) else v) for k, v in items)


def _holders(m: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Every opened container **and** every opened archive, by path.

    A ``BIG`` disc has no ``TERF`` container at all, so a section built from
    containers alone would print an empty cell on every row of a disc that is
    entirely readable.  An archive row carries a ``formats`` histogram of the
    same shape, so the rest of the section needs no special case.
    """

    out = {path: row for path, row in (m.get("containers") or {}).items() if "error" not in row}
    out.update({path: row for path, row in (m.get("archives") or {}).items() if "error" not in row})
    return out


def _page_containers(m: Dict[str, Any]) -> Dict[str, List[Tuple[str, Dict[str, Any]]]]:
    """``page -> [(container or archive path, its row)]`` from the mapper's name glossary."""

    out: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {page: [] for page in PAGE_ROWS}
    for path, row in sorted(_holders(m).items()):
        pages, _phrase, _grade = mapper._glossary(_container_base(path))
        for page in pages:
            out.setdefault(page, []).append((path, row))
    return out


def _needs_section(m: Dict[str, Any], baseline: Optional[Dict[str, Any]]) -> List[str]:
    c = m["counts"]
    by_page = _page_containers(m)
    formats = dict(c["formats"])
    for name, count in (_block(m, "big_entries").get("formats") or {}).items():
        formats[name] = formats.get(name, 0) + count
    out = ["## What a module for this disc would need", "",
           "One row per studio page. *Container* is the disc's own file whose name the mapper's "
           "glossary maps to that page — and, where the glossary (which is Madden 09's naming) "
           "names none, whichever containers carry the page's format, marked *(by format, not by "
           "name)*. *Feeding formats* are counted after decompression, across the whole disc, by "
           "the module's own `identify_member`. The number in brackets is that container's member "
           "count in the page's formats.", "",
           "| page | container or archive on this disc | feeding format(s) present | what the readers do with them |",
           "|---|---|---|---|"]
    for page in PAGE_ROWS:
        wanted = PAGE_FORMATS.get(page, ())
        present = {fmt: formats.get(fmt, 0) for fmt in wanted if formats.get(fmt, 0)}
        rows = by_page.get(page, [])
        names = []
        for path, row in rows:
            interesting = sum(row.get("formats", {}).get(fmt, 0) for fmt in wanted) if wanted else 0
            names.append((interesting, path.rsplit("/", 1)[-1], row.get("members", 0)))
        names.sort(key=lambda item: (-item[0], item[1]))
        by_format_note = ""
        if not names and wanted:
            # The glossary is Madden 09's naming; a disc that keeps the same
            # format under another name (NCAA's FLDDATA.DAT for Madden's
            # FIELDART.DAT) would otherwise show an empty cell that is not true.
            # Falling back to "whichever containers carry the page's format" is
            # mechanical -- no name is being interpreted.
            for path, row in sorted(_holders(m).items()):
                interesting = sum(row.get("formats", {}).get(fmt, 0) for fmt in wanted)
                if interesting:
                    names.append((interesting, path.rsplit("/", 1)[-1], row.get("members", 0)))
            names.sort(key=lambda item: (-item[0], item[1]))
            if names:
                by_format_note = " *(by format, not by name)*"
        listed = ", ".join("`%s`%s" % (name, "" if not n else " (%s)" % format(n, ","))
                           for n, name, _members in names[:4])
        if len(names) > 4:
            listed += " and %d more" % (len(names) - 4)
        listed += by_format_note
        out.append("| %s | %s | %s | %s |" % (
            page, listed or "—",
            ", ".join("%s %s" % (k, format(v, ",")) for k, v in present.items()) or "—",
            _page_verdict(page, present, c, m)))
    out.append("")
    out += _schema_section(m, baseline)
    out += _cache_section(m, baseline)
    return out


def _page_verdict(page: str, present: Dict[str, int], c: Dict[str, Any],
                  m: Dict[str, Any]) -> str:
    if page == "Gameplay":
        # The Gameplay page is fed by the executable, not by a container member,
        # so an empty container cell is not an empty answer.
        ident = m.get("identity", {})
        return ("the boot ELF `%s` opens: PCSX2 CRC `%s`, %s program header(s), sha256 `%s`. "
                "Every patch site is per-title research; nothing here is shared with Madden 09."
                % (ident.get("boot_file"), ident.get("pcsx2_crc") or "—",
                   ident.get("boot_segments") if ident.get("boot_segments") is not None else "?",
                   (ident.get("boot_sha256") or "")[:16]))
    if page == "Build & Share":
        return "the shell's own page; no game writes it"
    if page == "The Crib":
        return "an ESPN NFL 2K5 feature; a Madden or NCAA disc has no data for it"
    if page == "Saves":
        return "not on the disc; a memory-card save is a different source"
    if not present:
        return "no container on this disc carries this page's formats"
    parts = []
    if "TDB" in present:
        parts.append("`parse_tdb` opens %s of %s database(s); %s of %s CRC sites agree" % (
            format(c["tdb"]["works"], ","), format(c["tdb"]["total"], ","),
            format(c["crc_sites"]["works"], ","), format(c["crc_sites"]["total"], ",")))
    if "MMAP" in present:
        parts.append("`decode_rgba` draws %s of %s sampled texture(s)" % (
            format(c["mmap"]["works"], ","), format(c["mmap"]["total"], ",")))
    if "TEXT" in present:
        parts.append("%s TEXT member(s) classified by `identify_member`" % format(present["TEXT"], ","))
    if "SCHl" in present:
        parts.append("%s of %s SCHl member(s) carry a codec the audio lane decodes" % (
            format(c["schl"]["works"], ","), format(c["schl"]["total"], ",")))
    if "BNKl" in present:
        parts.append("`parse_bank` opens %s of %s bank(s)" % (
            format(c["bnkl"]["works"], ","), format(c["bnkl"]["total"], ",")))
    if "SHPS" in present:
        shps = _block(m, "shps")
        parts.append("`ea_shps.decode_rgba` draws %s of %s image(s) in %s sampled bank(s)%s" % (
            format(shps.get("works", 0), ","), format(shps.get("total", 0), ","),
            format(shps.get("sampled", 0), ","),
            ("; the refusals are " + _counts(shps.get("refused_codes"), 4))
            if shps.get("refused_codes") else ""))
    for fmt in ("SMF", "DMF", "MPCh", "FNTS"):
        if fmt in present:
            parts.append("%s %s member(s): no reader in this repository" % (format(present[fmt], ","), fmt))
    return "; ".join(parts) or "counted, not read"


def _schema_section(m: Dict[str, Any], baseline: Optional[Dict[str, Any]]) -> List[str]:
    out = ["### Do the databases have Madden 09's schema?", ""]
    if baseline is None:
        out += ["No control was given, so no comparison was made. The tables this disc carries, "
                "with their field counts, are in the JSON's `schemas` block.", ""]
        return out
    comparison = compare_schemas(m.get("schemas", {}), baseline.get("schemas", {}))
    out += ["Field names and bit widths from each disc's own field directory, dominant shape per table "
            "name. `identical` means the roster and identity lanes port with a schema table only; a "
            "width difference means the compiler's metadata-driven read still works and any hard-coded "
            "offset does not.", "",
            "| table | on this disc | on Madden 09 | verdict |", "|---|---:|---:|---|"]
    for name in SCHEMA_TABLES:
        row = comparison.get(name)
        if row is None or row.get("verdict") == "absent from both":
            continue
        out.append("| `%s` | %s field(s) | %s field(s) | %s |" % (
            name,
            "—" if row.get("fields") is None else row["fields"],
            "—" if row.get("baseline_fields") is None else row["baseline_fields"],
            row.get("verdict")))
    out.append("")
    widths = [(name, row) for name, row in comparison.items() if row.get("width_differences")]
    if widths:
        out.append("Width differences, field by field (this disc → Madden 09):")
        out.append("")
        for name, row in widths[:6]:
            out.append("- `%s`: %s" % (name, ", ".join(
                "`%s` %d→%d" % (f[0], f[1], f[2]) for f in row["width_differences"][:12])))
        out.append("")
    return out


def _cache_section(m: Dict[str, Any], baseline: Optional[Dict[str, Any]]) -> List[str]:
    caches = m.get("caches", {})
    c = m["counts"]["caches"]
    out = ["### The preload caches", ""]
    if not caches.get("files"):
        out += ["**No `QL01` preload cache is on this disc.** Every writer's cache-coherence step — the "
                "one that keeps a container's cached directory copies in step with the container — has "
                "nothing to keep in step here, which removes work rather than adding it. Whether this "
                "engine year preloads through some other file is not established by this measurement.", ""]
        return out
    rows = ["| cache | bytes | copies | header | member | containers named | identical | differing | unresolved |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, row in sorted(caches.get("per_cache", {}).items()):
        rows.append("| `%s` | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            name, format(row["bytes"], ","), format(row["copies"], ","), format(row["header_copies"], ","),
            format(row["member_copies"], ","), row["containers"], format(row["identical"], ","),
            format(row["differing"], ","), format(row["unresolved"], ",")))
    out += rows + [""]
    verdict = ("every copy is byte-identical to what it copies, which is Madden 09's own shape"
               if c["copies"] and not c["differing"] and not c["unresolved"]
               else "%s of %s copies are byte-identical; %s differ and %s could not be resolved to a "
                    "container on this disc" % (format(c["identical"], ","), format(c["copies"], ","),
                                                format(c["differing"], ","), format(c["unresolved"], ",")))
    out += ["The caches parse with the module's own `containers.parse_preload_cache`, and %s." % verdict, ""]
    if caches.get("unresolved_kinds"):
        out += ["An *unresolved* copy is one whose `DTLS` row names a member the container it names does "
                "not have, so the module's `PreloadCopy.length_in` refuses rather than guessing how long "
                "the copy is. The bytes at those offsets carry: %s." % _counts(caches["unresolved_kinds"]), ""]
    if baseline is not None:
        base = baseline["counts"]["caches"]
        out += ["Madden 09's control run: %s cache(s), %s copies, %s identical." % (
            format(base["total"], ","), format(base["copies"], ","), format(base["identical"], ",")), ""]
    return out


def _refusals_section(m: Dict[str, Any]) -> List[str]:
    rows = m.get("refusals", [])
    out = ["## What the readers refused, grouped by sentence", "",
           "%s refusal(s) in %s group(s). Numbers inside a sentence are blanked to `#` so one refusal "
           "seen many times is one row." % (format(m.get("refusals_total", 0), ","), len(rows)), ""]
    if not rows:
        out += ["Nothing was refused.", ""]
        return out
    out += ["| reader | refusals | sentence (numbers blanked) | where |", "|---|---:|---|---|"]
    for row in rows[:18]:
        out.append("| `%s` | %s | %s | %s |" % (
            row["reader"], format(row["count"], ","), row["sentence_class"].replace("|", "\\|"),
            ", ".join("`%s`" % w for w in row["where"][:3]) or "—"))
    if len(rows) > 18:
        out.append("| … | | %d further group(s) in the JSON | |" % (len(rows) - 18))
    out.append("")
    return out


# --------------------------------------------------------------------------
# The cross-title summary
# --------------------------------------------------------------------------
SUMMARY_FAMILIES: Tuple[Tuple[str, str], ...] = (
    ("containers", "containers"), ("members", "members"),
    ("big", "BIG"), ("refpack", "RefPack"), ("shps", "SHPS"),
    ("tdb", "TDB"), ("crc_sites", "CRC"), ("mmap", "MMAP"), ("schl", "SCHl"), ("bnkl", "BNKl"),
)

#: What a cell says when the family was not measured at all, because the record
#: predates the row.  Distinct from ``—``, which means the family is absent from
#: a disc that *was* measured for it.
NOT_MEASURED = "n/m"


def summary_row(m: Dict[str, Any]) -> Dict[str, Any]:
    c = m["counts"]
    row: Dict[str, Any] = {"disc": m.get("label"), "serial": m.get("identity", {}).get("serial"),
                           "seconds": m.get("seconds")}
    for key, label in SUMMARY_FAMILIES:
        block = c.get(key)
        if block is None:                 # a record written before this row existed
            row[label] = None
            row[label + "_n"] = None
            continue
        row[label] = _pct(block.get("works", 0), block.get("total", 0))
        row[label + "_n"] = "%s/%s" % (format(block.get("works", 0), ","), format(block.get("total", 0), ","))
    copies = c["caches"]
    row["caches"] = _pct(copies["identical"], copies["copies"])
    row["caches_n"] = "%s/%s" % (format(copies["identical"], ","), format(copies["copies"], ","))
    return row


def render_summary(maps: Sequence[Dict[str, Any]]) -> str:
    rows = [summary_row(m) for m in maps]
    head = ["disc", "serial"] + [label for _key, label in SUMMARY_FAMILIES] + ["caches", "seconds"]
    out = ["| " + " | ".join(head) + " |",
           "|" + "---|" * 2 + "---:|" * (len(SUMMARY_FAMILIES) + 2)]
    unmeasured = False
    for row in rows:
        cells = [str(row["disc"]), "`%s`" % row["serial"]]
        for _key, label in SUMMARY_FAMILIES:
            if row[label] is None and row[label + "_n"] is None:
                unmeasured = True
                cells.append(NOT_MEASURED)
            else:
                cells.append("—" if row[label] is None
                             else "%.1f%% (%s)" % (row[label], row[label + "_n"]))
        cells.append("—" if row["caches"] is None else "%.1f%% (%s)" % (row["caches"], row["caches_n"]))
        cells.append(str(row["seconds"]))
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    out.append("`—` the family is absent from a disc that was measured for it (0 of 0)."
               + ("  `%s` the disc was measured before that row existed "
                  "(`ea_module_readiness/v1`); re-run it to fill the cell." % NOT_MEASURED
                  if unmeasured else ""))
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Selftest: synthetic bytes only, no disc
# --------------------------------------------------------------------------
def _synthetic_shps_bank(*, big_endian: bool = False) -> bytes:
    """A four-image ``SHPS`` bank: two the reader decodes and two it refuses.

    Built from the layout ``EA_SHPS_FORMAT.md`` documents, so the ``SHPS`` row
    is proved on bytes this file computes -- including the two refusals that
    matter on a retail disc, block code ``0x0E`` (the compressed art codec) and
    ``0x01`` (the one-pixel stub).
    """

    order = ">" if big_endian else "<"
    end = "big" if big_endian else "little"

    def block(code: int, width: int, height: int, payload: bytes,
              declared: Optional[int] = None) -> bytes:
        size = (ea_shps.BLOCK_HEADER_SIZE + len(payload)) if declared is None else declared
        return (bytes((code,)) + size.to_bytes(3, end)
                + struct.pack(order + "HH", width, height)
                + struct.pack(order + "HHHH", 0, 0, 0, 0) + payload)

    palette = b"".join(bytes((v * 16, v * 16, v * 16, 0x80)) for v in range(16))
    tail = block(0x70, 0, 0, b"", declared=0)          # the zero block ends a chain
    images = [
        ("idx8", block(ea_shps.CODE_INDEXED8, 4, 2, bytes(range(8)))
                 + block(ea_shps.CODE_PALETTE32, 16, 1, palette) + tail),
        ("rgba", block(ea_shps.CODE_RGBA32, 2, 2, bytes(16)) + tail),
        ("cmpr", block(0x0E, 8, 8, bytes(24))
                 + block(ea_shps.CODE_PALETTE32, 16, 1, palette) + tail),
        ("stub", block(0x01, 1, 1, bytes(16)) + tail),
    ]
    cursor = ea_shps.SHPS_HEADER_SIZE + ea_shps.SHPS_ROW_SIZE * len(images)
    offsets = []
    for _tag, body in images:
        offsets.append(cursor)
        cursor += len(body)
    directory = b"".join(tag.encode("ascii").ljust(4, b" ") + struct.pack(order + "I", offset)
                         for (tag, _body), offset in zip(images, offsets))
    return (b"SHPS" + struct.pack(order + "II", cursor, len(images)) + b"G355"
            + directory + b"".join(body for _tag, body in images))


def _synthetic_tdb_member() -> bytes:
    return ea_tdb.build_tdb([
        ("TEAM", [("TGID", ea_tdb.FIELD_UINT, 8), ("TDNA", ea_tdb.FIELD_STRING, 32)],
         [{"TGID": 1}, {"TGID": 2}]),
        ("PLAY", [("PGID", ea_tdb.FIELD_UINT, 16), ("POVR", ea_tdb.FIELD_UINT, 7)],
         [{"PGID": 7, "POVR": 90}]),
    ])


def selftest() -> int:
    """Prove every measurement path on bytes this file computes.  Returns 0 or 1."""

    import tempfile

    checks = 0
    failures: List[str] = []

    def check(condition: object, what: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(what)

    # -- the refusal ledger --------------------------------------------------
    check(refusal_class("member 12 runs from 640 for 96 byte(s)")
          == refusal_class("member 913 runs from 40,960 for 64 byte(s)"),
          "two instances of one refusal group together")
    check(refusal_class("not an EA TERF container: it starts with b'QL01'")
          == refusal_class("not an EA TERF container: it starts with b'BIGF'"),
          "the quoted magic is blanked so one refusal is one row")
    ledger = Ledger()
    ledger.add("r", "a", ValueError("member 1 of 2"))
    ledger.add("r", "b", ValueError("member 3 of 4"))
    check(len(ledger.as_list()) == 1 and ledger.as_list()[0]["count"] == 2, "the ledger counts a class once")
    check(ledger.total() == 2, "the ledger totals its rows")

    # -- the even sample -----------------------------------------------------
    check(_evenly(list(range(100)), 5) == [0, 20, 40, 60, 80], "a sample is spread, not the head")
    check(_evenly([1, 2, 3], 10) == [1, 2, 3], "a sample smaller than its ceiling is the whole run")
    check(_evenly([1, 2, 3], None) == [1, 2, 3], "no ceiling means every member")

    with tempfile.TemporaryDirectory() as work:
        work_dir = Path(work)

        # -- the Madden 09 module's own synthetic disc -----------------------
        # ``build_tdb`` writes every CRC slot as zero on purpose, so the fixture
        # is put through the module's own ``recompute_crcs`` first: the CRC row
        # then has a right answer to find, and the tampered copy below has one
        # to miss.
        database = ea_tdb.recompute_crcs(_synthetic_tdb_member())
        image_bytes = m09.build_synthetic_disc(tdb_members=[database, database],
                                               stream_database=database)
        path = work_dir / "synthetic.iso"
        path.write_bytes(image_bytes)
        m = measure_disc(path, label="synthetic Madden 09 shape", mmap_sample=None, schl_sample=None)
        c = m["counts"]
        check(c["containers"]["total"] == 2 and c["containers"]["refused"] == 0,
              "both synthetic containers open")
        check(c["members"]["refused"] == 0, "no member of the synthetic disc is refused")
        check(c["mmap"]["works"] == 3 and c["mmap"]["refused"] == 0,
              "the three synthetic MMAP members decode (got %s/%s)" % (c["mmap"]["works"], c["mmap"]["total"]))
        check(c["tdb"]["works"] == 3, "two packed databases and the bare one parse (got %s)" % c["tdb"]["works"])
        check(c["crc_sites"]["total"] > 0, "the synthetic databases have CRC sites")
        check(c["crc_sites"]["works"] == c["crc_sites"]["total"],
              "every recomputed CRC site is found correct (got %s of %s)"
              % (c["crc_sites"]["works"], c["crc_sites"]["total"]))
        check(c["caches"]["total"] == 2 and c["caches"]["works"] == 2, "both preload caches parse")
        # Three, not four: ``m09.build_synthetic_disc`` writes two ``DTLS`` rows
        # into GAME.QKL and one into FE.QKL, and has since the day this check was
        # written.  The measurement was right; the constant beside it never was.
        check(c["caches"]["copies"] == 3 and c["caches"]["identical"] == 3 and c["caches"]["differing"] == 0,
              "every synthetic cache copy is byte-identical (got %s/%s)"
              % (c["caches"]["identical"], c["caches"]["copies"]))
        # The only refusal a clean synthetic disc raises is the fixture's own
        # boot ELF, which ``build_synthetic_disc`` writes as a 4 KiB stub with
        # no class byte; every reader this tool measures is silent.
        check({row["reader"] for row in m["refusals"]} <= {"ps2_elf.parse_program_headers"},
              "a clean disc refuses nothing but the fixture's stub boot ELF (got %s)"
              % sorted({row["reader"] for row in m["refusals"]}))
        check("TEAM" in m["schemas"] and "PLAY" in m["schemas"], "the recorded schemas carry TEAM and PLAY")
        check(dominant_shape(m["schemas"]["PLAY"])["fields"][0][0] == "PGID",
              "a recorded schema carries field names and widths")
        page = render_page(m, baseline=m)
        check("Readiness — what runs unchanged" in page, "the page renders its readiness table")
        check("identical" in page, "the page states the schema verdict against a control")
        check(render_summary([m]).count("|") > 10, "the summary renders a row")

        # -- a tampered database: the CRC row must stop agreeing ---------------
        tampered = bytearray(database)
        # A byte inside the first table's record array: covered by that table's
        # data block, so the *next* table's prior-block CRC must stop agreeing.
        tampered[ea_tdb.parse_tdb(database).record_offset("TEAM", 0)] ^= 0xFF
        (work_dir / "tampered.iso").write_bytes(
            m09.build_synthetic_disc(tdb_members=[bytes(tampered)], stream_database=database))
        t = measure_disc(work_dir / "tampered.iso", label="tampered", mmap_sample=None, schl_sample=None)
        check(t["counts"]["crc_sites"]["refused"] > 0,
              "a flipped record byte is caught by the CRC row (got %s wrong of %s)"
              % (t["counts"]["crc_sites"]["refused"], t["counts"]["crc_sites"]["total"]))
        check(any(row["reader"] == "ea_tdb.verify_crcs" for row in t["refusals"]),
              "the CRC mismatch is recorded with its own sentence")
        check(any("CRC at offset" in row["example"] for row in t["refusals"]),
              "the recorded CRC sentence is the reader's own")

        # -- a preload cache whose copy is stale: the byte-compare must notice --
        stale = m09.build_synthetic_disc(tdb_members=[database], stream_database=database)
        marker = stale.find(b"QL01")
        check(marker > 0, "the synthetic image carries a QL01 cache")
        hacked = bytearray(stale)
        hacked[marker + 400] ^= 0xFF              # inside the cache's copied payload
        (work_dir / "stale.iso").write_bytes(bytes(hacked))
        st = measure_disc(work_dir / "stale.iso", label="stale cache", mmap_sample=None, schl_sample=None)
        check(st["counts"]["caches"]["differing"] + st["counts"]["caches"]["unresolved"] > 0,
              "a byte changed inside a cache copy is caught (identical=%s differing=%s)"
              % (st["counts"]["caches"]["identical"], st["counts"]["caches"]["differing"]))

        # -- the mapper's own synthetic disc: TDB, SCHl, TEXT, nested TERF ----
        wide, _payloads = mapper.build_synthetic_disc()
        wide_path = work_dir / "wide.iso"
        wide_path.write_bytes(wide)
        w = measure_disc(wide_path, label="synthetic wide", mmap_sample=None, schl_sample=None)
        wc = w["counts"]
        check(wc["containers"]["works"] >= 2, "the wide synthetic disc's containers open")
        check(wc["schl"]["total"] >= 1 and wc["schl"]["headers_parsed"] >= 1,
              "an SCHl member's header parses (got %s of %s)"
              % (wc["schl"]["headers_parsed"], wc["schl"]["total"]))
        check(wc["formats"].get("TEXT", 0) >= 1, "a TEXT member is classified")
        check(wc["formats"].get("TERF", 0) >= 1, "a nested container is classified")
        check(wc["tdb"]["works"] >= 2, "the wide disc's databases parse")
        check(wc["big"]["total"] >= 3 and wc["big"]["refused"] == 0,
              "every BIG archive on the wide disc opens, nested ones included (got %s of %s)"
              % (wc["big"]["works"], wc["big"]["total"]))
        check(wc["big"]["size_fields"].get("big") == 1 and wc["big"]["size_fields"].get("little", 0) >= 2,
              "a big-endian size word is named on a sector-padded file (got %s)" % wc["big"]["size_fields"])
        check(wc["big_entries"]["total"] >= 9 and wc["big_entries"]["refused"] == 0,
              "every archive entry classifies (got %s of %s)"
              % (wc["big_entries"]["works"], wc["big_entries"]["total"]))
        check(wc["refpack"]["works"] >= 1, "a packed entry inside an archive unpacks")
        check(wc["shps"]["banks"] >= 4, "the archives' image banks are found (got %s)" % wc["shps"]["banks"])
        check(wc["data_tables"]["total"] >= 2 and wc["data_tables"]["opens_as_tdb"] >= 2,
              "the database probe finds this disc's databases (got %s)" % wc["data_tables"])
        page = render_page(w, today="1970-01-01")
        check("The EA BIG family" in page and "| BIG archives |" in page,
              "the page carries the BIG family's own section and rows")
        check("Where this disc keeps its roster and team data" in page,
              "the page says where the roster data lives")

        # -- a container the reader must refuse -------------------------------
        led = Ledger()
        tally = _new_tally()
        try:
            measure_container(b"NOPE" + bytes(60), "NOPE.DAT", led, tally)
        except Refusal as exc:
            check("not an EA TERF container" in str(exc), "a non-container refuses by name")
        else:
            check(False, "a non-container must refuse")

        # -- a member whose codec the module does not implement ---------------
        good = ea_terf.build_terf([b"MMAP" + bytes(60), b"plain ascii member, sixty-four bytes long, for the test."],
                                  chunk="COMP")
        parsed = ea_terf.parse_terf(good)
        comp = parsed.chunk("COMP")
        assert comp is not None
        hostile = bytearray(good)
        struct.pack_into("<I", hostile, comp.offset + ea_terf.CHUNK_HEADER_SIZE, ea_terf.CODEC_LZM1)
        led = Ledger()
        tally = _new_tally()
        row = measure_container(bytes(hostile), "HOSTILE.DAT", led, tally)
        check(row["members_refused"] == 1 and row["members_head_decoded"] == 1,
              "one member of two is refused for its codec")
        check(any("codec" in r["sentence_class"] for r in led.as_list()),
              "the codec refusal is recorded by its own sentence")

        # -- the EA BIG family, on archives this function builds ---------------
        bank = _synthetic_shps_bank()
        led = Ledger()
        tally = _new_tally()
        archive_bytes = ea_big.build_big([
            ("art/one.ssh", bank),
            ("art/packed.ssh", mapper._refpack_literal(bank)),
            ("data/six.db", database),
            ("notes.txt", b"a plain ascii entry for this test, sixty-four bytes long."),
            ("hole/", b""),
        ])
        archive = ea_big.parse_big(archive_bytes, name="Z.BIG")
        row = measure_archive(archive, "Z.BIG", led, tally, head=archive_bytes[:16],
                              available=len(archive_bytes))
        check(row["entries"] == 5 and row["entries_refused"] == 0,
              "every entry of a synthetic archive classifies (got %s refused)" % row["entries_refused"])
        check(row["size_field"] == "little", "the size word's byte order is named (got %s)" % row["size_field"])
        check((row["refpack_entries"], row["refpack_unpacked"]) == (1, 1),
              "the one packed entry is found and unpacked (got %s of %s)"
              % (row["refpack_unpacked"], row["refpack_entries"]))
        check(row["formats"].get("SHPS") == 2 and row["formats"].get("TDB") == 1
              and row["formats"].get(ea_big.FORMAT_EMPTY) == 1,
              "an entry is classified after RefPack, not before (got %s)" % row["formats"])
        check(tally["shps_parsed"] == 2 and tally["shps_images"] == 8,
              "both banks parse and every image is looked at (got %s image(s))" % tally["shps_images"])
        check(tally["shps_decoded"] == 4 and tally["shps_image_refused"] == 4,
              "two images per bank decode and two are refused (got %s / %s)"
              % (tally["shps_decoded"], tally["shps_image_refused"]))
        check(tally["shps_refused_codes"].get("0x0e") == 2
              and tally["shps_refused_codes"].get("0x01") == 2,
              "the refusals are counted by block code (got %s)" % dict(tally["shps_refused_codes"]))
        check(any("does not decode" in r["sentence_class"] for r in led.as_list()),
              "the SHPS refusal keeps the reader's own sentence")
        check(tally["tdb_parsed"] == 1, "a database inside an archive parses")
        check(tally["data_tdb"] == 1 and tally["data_probes"][0]["opens_as_tdb"],
              "a database-shaped entry name is probed and opens as a TDB")

        # -- a big-endian bank, and the archive shapes the reader refuses ------
        led = Ledger()
        tally = _new_tally()
        out = _new_shps_row(1, 1)
        _measure_one_shps(_synthetic_shps_bank(big_endian=True), "be.ssh", led, tally, out)
        check(out["decoded"] == 2 and tally["shps_endians"].get("big") == 1,
              "a big-endian bank reads the same way (got %s)" % out)
        for magic, wanted in ((b"BIG4", "BIG4"), (ea_big.C0FB_HEAD, "C0 FB")):
            try:
                ea_big.parse_big(magic.ljust(4, b"\x00") + bytes(60), name="A.BIG")
            except Refusal as exc:
                check(wanted in str(exc), "a %s archive is refused by name" % wanted)
            else:
                check(False, "a %s archive must be refused" % wanted)

        # -- loose RefPack files, both spellings --------------------------------
        led = Ledger()
        tally = _new_tally()
        good = measure_loose_refpack(mapper._refpack_literal(b"MMAP" + bytes(60)),
                                     "/FE/XLAY_FE.BIN", led, tally)
        check(good["format"] == "MMAP" and tally["loose_refpack_unpacked"] == 1,
              "a loose RefPack file unpacks and is classified (got %s)" % good["format"])
        bad = measure_loose_refpack(ea_big.C0FB_HEAD + bytes(30), "/FE/XAFEBG.BIN", led, tally)
        check(bad["format"] == ea_big.FORMAT_UNDECODABLE and tally["loose_refpack_refused"] == 1,
              "the C0 FB spelling is refused, not silently read as empty")
        check(any("RefPack" in r["example"] for r in led.as_list()),
              "the loose-RefPack refusal keeps the reader's own sentence")

        # -- schema comparison -------------------------------------------------
        mine = {"TEAM": {"a": {"count": 1, "field_count": 2, "record_bytes": 6,
                               "fields": [["TGID", "uint", 8, 0], ["TDNA", "string", 32, 8]]}}}
        same = compare_table(dominant_shape(mine["TEAM"]), dominant_shape(mine["TEAM"]))
        check(same["verdict"] == "identical", "a table compared with itself is identical")
        wider = {"a": {"count": 1, "field_count": 2, "record_bytes": 6,
                       "fields": [["TGID", "uint", 9, 0], ["TDNA", "string", 32, 9]]}}
        differ = compare_table(dominant_shape(wider), dominant_shape(mine["TEAM"]))
        check("width" in differ["verdict"] and differ["width_differences"][0][0] == "TGID",
              "a widened field is named with both widths")
        gone = compare_table(None, dominant_shape(mine["TEAM"]))
        check(gone["verdict"] == "absent here", "a table the disc lacks says so")

    print("EA_MODULE_READINESS_SELFTEST checks=%d failures=%d" % (checks, len(failures)))
    for failure in failures:
        print("  FAIL: %s" % failure)
    if failures:
        return 1
    print("EA_MODULE_READINESS_SELFTEST_PASS")
    return 0


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def slug(label: str, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", label or fallback).strip("-")
    return text or "disc"


def _load(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--iso", type=Path, help="the disc image to measure")
    parser.add_argument("--out", type=Path, help="output directory (or file, with --page / --summary)")
    parser.add_argument("--label", default="", help='title, e.g. "Madden NFL 08 (USA)"')
    parser.add_argument("--page", type=Path, help="render the Markdown page from a readiness JSON")
    parser.add_argument("--summary", type=Path, help="render one table over every readiness JSON in a directory")
    parser.add_argument("--baseline", type=Path, help="the Madden 09 control's readiness JSON, for the schema comparison")
    parser.add_argument("--mmap-sample", type=int, default=DEFAULT_MMAP_SAMPLE,
                        help="MMAP members decoded per container (0 = every one)")
    parser.add_argument("--schl-sample", type=int, default=DEFAULT_SCHL_SAMPLE,
                        help="SCHl members whose streams are walked per container (0 = every one)")
    parser.add_argument("--shps-sample", type=int, default=DEFAULT_SHPS_SAMPLE,
                        help="SHPS banks decoded per BIG archive (0 = every one)")
    parser.add_argument("--nested-sample", type=int, default=DEFAULT_NESTED_SAMPLE,
                        help="nested BIG archives opened per archive (0 = every one)")
    parser.add_argument("--archive-depth", type=int, default=ARCHIVE_MAX_DEPTH,
                        help="how deep a chain of archives-inside-archives is walked")
    parser.add_argument("--shallow", action="store_true", help="classify members only; skip every deep pass")
    parser.add_argument("--data-only", action="store_true", help="measure only files under /DATA")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.page is not None:
        record = _load(args.page)
        baseline = _load(args.baseline) if args.baseline else None
        text = render_page(record, baseline)
        target = args.out if args.out and args.out.suffix == ".md" else (
            (args.out or args.page.parent) /
            ("%s.%s.md" % (record["identity"]["serial"], slug(record.get("label", ""), args.page.stem))))
        _write_text(target, text)
        print("EA_MODULE_READINESS_PAGE %s" % target)
        return 0

    if args.summary is not None:
        records = [_load(p) for p in sorted(args.summary.glob("*.readiness.json"))]
        if not records:
            print("no *.readiness.json in %s" % args.summary, file=sys.stderr)
            return 2
        text = render_summary(records)
        if args.out:
            _write_text(args.out, text)
            print("EA_MODULE_READINESS_SUMMARY %s discs=%d" % (args.out, len(records)))
        else:
            print(text)
        return 0

    if args.iso is None or args.out is None:
        parser.error("--iso and --out are both needed (or use --page / --summary / --selftest)")
    if not args.iso.is_file():
        print("no such image: %s" % args.iso, file=sys.stderr)
        return 2

    progress = (lambda line: None) if args.quiet else (lambda line: print("  " + line, file=sys.stderr))
    try:
        record = measure_disc(args.iso, label=args.label,
                              mmap_sample=args.mmap_sample or None,
                              schl_sample=args.schl_sample or None,
                              shps_sample=args.shps_sample or None,
                              nested_sample=args.nested_sample or None,
                              archive_depth=max(0, args.archive_depth),
                              deep=not args.shallow, data_only=args.data_only,
                              progress=progress)
    except ReadinessError as exc:
        print("REFUSED %s" % exc, file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    name = "%s.%s.readiness.json" % (record["identity"]["serial"], slug(args.label, args.iso.stem))
    target = args.out / name
    _write_text(target, json.dumps(record, indent=1, sort_keys=True, default=str) + "\n")
    c = record["counts"]
    print("EA_MODULE_READINESS_DONE serial=%s containers=%d/%d members=%d/%d big=%d/%d "
          "entries=%d/%d refpack=%d/%d shps=%d/%d tdb=%d/%d crc=%d/%d "
          "mmap=%d/%d schl=%d/%d caches=%d/%d copies=%d/%d refusals=%d seconds=%s file=%s"
          % (record["identity"]["serial"],
             c["containers"]["works"], c["containers"]["total"],
             c["members"]["works"], c["members"]["total"],
             c["big"]["works"], c["big"]["total"],
             c["big_entries"]["works"], c["big_entries"]["total"],
             c["refpack"]["works"], c["refpack"]["total"],
             c["shps"]["works"], c["shps"]["total"],
             c["tdb"]["works"], c["tdb"]["total"],
             c["crc_sites"]["works"], c["crc_sites"]["total"],
             c["mmap"]["works"], c["mmap"]["total"],
             c["schl"]["works"], c["schl"]["total"],
             c["caches"]["works"], c["caches"]["total"],
             c["caches"]["identical"], c["caches"]["copies"],
             record["refusals_total"], record["seconds"], target))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
