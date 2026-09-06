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
    madden09_ps2.containers.parse_preload_cache / preload copies
    ps2_elf.pcsx2_crc, tools/ps2_iso9660

so a number here is a measurement of the product, not of a re-implementation::

    python3 tools/owner/ea_module_readiness.py --iso IMAGE.iso --out DIR [--label "Madden NFL 08 (USA)"]
    python3 tools/owner/ea_module_readiness.py --page DIR/<serial>.<label>.readiness.json [--baseline DIR/SLUS-21770.*.json]
    python3 tools/owner/ea_module_readiness.py --summary DIR --baseline DIR/SLUS-21770.*.json [--out SUMMARY.md]
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
from mod_editor.games._formats import ea_schl, ea_tdb, ea_terf, ps2_elf  # noqa: E402
from mod_editor.games.madden09_ps2 import containers as m09  # noqa: E402
from mod_editor.games.madden09_ps2 import mmap_art  # noqa: E402

SCHEMA = "ea_module_readiness/v1"

#: The reader modules whose behaviour this tool measures.  Their digests go in
#: the JSON so a page can say which build of the module was run.
READER_FILES: Tuple[Tuple[str, str], ...] = (
    ("ea_terf", "mod_editor/games/_formats/ea_terf.py"),
    ("ea_tdb", "mod_editor/games/_formats/ea_tdb.py"),
    ("ea_schl", "mod_editor/games/_formats/ea_schl.py"),
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

#: The studio's fourteen pages, in the shell's order.  ``mapper.PAGE_ROWS``
#: carries thirteen; Build & Share is the shell's own and no game writes it.
PAGE_ROWS: Tuple[str, ...] = mapper.PAGE_ROWS + ("Build & Share",)

#: Which decompressed format feeds which page, for the "what a module needs"
#: section.  A page with no format here is answered from the glossary alone.
PAGE_FORMATS: Dict[str, Tuple[str, ...]] = {
    "Uniforms & Equipment": ("MMAP",),
    "Names, Numbers & Faces": ("TDB", "MMAP"),
    "Text & Team Identity": ("TDB", "TEXT"),
    "Field Art & Create-Team Art": ("MMAP",),
    "Stadiums": ("MMAP", "SMF", "DMF"),
    "Presentation": ("MMAP", "MPCh"),
    "Menus & UI": ("TEXT", "MMAP", "FNTS"),
    "Audio": ("SCHl", "BNKl"),
    "Gameplay": ("ELF",),
    "Playbooks & Plays": ("TDB",),
    "All Textures": ("MMAP",),
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

    kinds: Counter = Counter()
    containers: Dict[str, Any] = {}
    databases: Dict[str, Any] = {}
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
                     "deep": deep, "data_only": data_only,
                     "member_head_bytes": MEMBER_HEAD, "schl_head_bytes": SCHL_HEAD_BYTES},
        "kinds": dict(kinds.most_common()),
        "files": files, "data_files": data_files,
        "counts": counts,
        "containers": containers,
        "databases": databases,
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


def readiness_table(m: Dict[str, Any]) -> List[str]:
    c = m["counts"]
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
    out += _needs_section(m, baseline)
    out += _refusals_section(m)
    return "\n".join(out) + "\n"


def _counts(d: Optional[Dict[str, Any]], limit: Optional[int] = None) -> str:
    items = sorted((d or {}).items(), key=lambda kv: (-(kv[1] if isinstance(kv[1], int) else 0), str(kv[0])))
    if limit is not None:
        items = items[:limit]
    return ", ".join("%s %s" % (k, format(v, ",") if isinstance(v, int) else v) for k, v in items)


def _page_containers(m: Dict[str, Any]) -> Dict[str, List[Tuple[str, Dict[str, Any]]]]:
    """``page -> [(container path, its row)]`` from the mapper's own name glossary."""

    out: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {page: [] for page in PAGE_ROWS}
    for path, row in sorted(m.get("containers", {}).items()):
        if "error" in row:
            continue
        pages, _phrase, _grade = mapper._glossary(_container_base(path))
        for page in pages:
            out.setdefault(page, []).append((path, row))
    return out


def _needs_section(m: Dict[str, Any], baseline: Optional[Dict[str, Any]]) -> List[str]:
    c = m["counts"]
    by_page = _page_containers(m)
    formats = c["formats"]
    out = ["## What a module for this disc would need", "",
           "One row per studio page. *Container* is the disc's own file whose name the mapper's "
           "glossary maps to that page — and, where the glossary (which is Madden 09's naming) "
           "names none, whichever containers carry the page's format, marked *(by format, not by "
           "name)*. *Feeding formats* are counted after decompression, across the whole disc, by "
           "the module's own `identify_member`. The number in brackets is that container's member "
           "count in the page's formats.", "",
           "| page | container(s) on this disc | feeding format(s) present | what the readers do with them |",
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
            for path, row in sorted(m.get("containers", {}).items()):
                if "error" in row:
                    continue
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
    ("containers", "containers"), ("members", "members"), ("tdb", "TDB"),
    ("crc_sites", "CRC"), ("mmap", "MMAP"), ("schl", "SCHl"), ("bnkl", "BNKl"),
)


def summary_row(m: Dict[str, Any]) -> Dict[str, Any]:
    c = m["counts"]
    row: Dict[str, Any] = {"disc": m.get("label"), "serial": m.get("identity", {}).get("serial"),
                           "seconds": m.get("seconds")}
    for key, label in SUMMARY_FAMILIES:
        block = c[key]
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
    for row in rows:
        cells = [str(row["disc"]), "`%s`" % row["serial"]]
        for _key, label in SUMMARY_FAMILIES:
            cells.append("—" if row[label] is None else "%.1f%% (%s)" % (row[label], row[label + "_n"]))
        cells.append("—" if row["caches"] is None else "%.1f%% (%s)" % (row["caches"], row["caches_n"]))
        cells.append(str(row["seconds"]))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# Selftest: synthetic bytes only, no disc
# --------------------------------------------------------------------------
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
        check(c["caches"]["copies"] == 4 and c["caches"]["identical"] == 4 and c["caches"]["differing"] == 0,
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
    print("EA_MODULE_READINESS_DONE serial=%s containers=%d/%d members=%d/%d tdb=%d/%d crc=%d/%d "
          "mmap=%d/%d schl=%d/%d caches=%d/%d copies=%d/%d refusals=%d seconds=%s file=%s"
          % (record["identity"]["serial"],
             c["containers"]["works"], c["containers"]["total"],
             c["members"]["works"], c["members"]["total"],
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
