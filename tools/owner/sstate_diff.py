#!/usr/bin/env python3
"""Diff two PCSX2 savestates and say which bytes carry a value the screen changed.

Two states captured seconds apart on the same menu, with exactly one thing
different on screen, are a controlled experiment: everything the game changed
by itself is noise and the one thing the player changed is the answer.  The
answer is a handful of bytes; the noise is one to three per cent of a 32 MB EE
image.  This tool is the sieve between them, and it is written to be run again
on the next title rather than done once by hand::

    python3 tools/owner/sstate_diff.py inventory  DIR                      # what states are here
    python3 tools/owner/sstate_diff.py diff       A.p2s B.p2s              # runs, ranked by shape
    python3 tools/owner/sstate_diff.py transition A.p2s B.p2s --from 54 --to 56 --width 7
    python3 tools/owner/sstate_diff.py sections   A.p2s B.p2s --elf BOOT.ELF
    python3 tools/owner/sstate_diff.py tdb        A.p2s B.p2s              # resident EA databases
    python3 tools/owner/sstate_diff.py record     A.p2s B.p2s --at 0x01DF996C --schema S.json
    python3 tools/owner/sstate_diff.py extract    A.p2s --member Screenshot.png --out DIR
    python3 tools/owner/sstate_diff.py --selftest

Why each pass exists
--------------------
``diff`` alone drowns you.  On a Madden NFL 09 pair whose only on-screen
difference was one jersey number, 1,097,719 of 33,554,432 bytes differed [M]:
frame counters, timers, RNG, audio ring buffers, render and DMA packets, and a
free-running cycle count.  Clustering into runs gets 2,915 runs at a 16-byte
gap; the answer is a two-byte run and is nowhere near the top by size.  So size
is not the ranking, **shape** is: a value a menu writes is a small change inside
a region that is otherwise identical, and noise is either a scattered single or
a large churning buffer.

``transition`` is the pass that actually finds a known value, and it is the one
to run first on any title where the ground truth is known.  A field of *w* bits
going *x* to *y* XORs its record by ``(x ^ y) << p`` for the field's bit offset
*p*; searching every ``p`` in 0..(8 + w) over a rolling little-endian window
finds every site in the image that holds that value at any alignment, byte-
aligned or not.  On the Madden pair that took 1,097,719 differing bytes to 15
raw hits at 10 distinct sites, of which one sat at a declared field offset.

``sections`` is the pass that says *what kind of memory* a hit is in.  A PS2
boot ELF's own section table maps an EE address to ``.text`` (which must not
change, so a change there means the diff is wrong), ``.data`` (a global whose
default is on the disc, at a file offset this prints), ``.sdata``/``.sbss``/
``.bss`` (a global with no disc image) or above the ELF (heap).  A single line
of that table -- ".data: 41 differing bytes, .text: 0" -- turned a 516,983-byte
NCAA Football 09 diff into a two-candidate shortlist.

``tdb`` and ``record`` close the loop: they ask whether a hit is a *record* in
the disc's own schema, by finding the EA databases resident in the image and
decoding the bytes at a candidate offset against a field directory.  When that
answers yes, a RAM diff has become a disc-format question.

Retail-free.  Nothing here prints a game byte, a decoded string or a pixel.
It prints offsets, lengths, counts, run statistics, four-character field names,
bit offsets and widths, and integer field values a caller asked for by name.
``extract`` writes a member to a directory the caller names and refuses to write
inside a repository checkout, because a screenshot and an EE image are payload
and belong in scratch space that gets deleted.

Bit order is the shared reader's [S]: fields are packed least-significant-bit
first, both within each byte and within the field, so a record read as one
little-endian integer and shifted by the field's bit offset is the same mapping
by construction.  See ``mod_editor/games/_formats/ea_tdb.py``.

Standard library only, plus the ``zstd`` command for the codec PCSX2 packs its
savestate members with (zip method 93).  Importable without Qt.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

#: The zip compression method PCSX2 stores savestate members with.
ZIP_ZSTD = 93
ZIP_DEFLATE = 8
ZIP_STORED = 0

#: The EE image member of a ``.p2s``, and its size on every PS2 title.
EE_MEMORY = "eeMemory.bin"
EE_SIZE = 32 * 1024 * 1024

#: What a PS2 boot ELF's program header loads at, used as the floor for
#: "this address is inside the executable image" [M].
PS2_ELF_BASE = 0x00100000


class SstateError(Exception):
    """This tool could not do what was asked; the sentence says why."""


# ---------------------------------------------------------------- savestates


def _zstd_decompress(blob: bytes, expect: int) -> bytes:
    """A zstd frame, through whichever decoder this box has."""
    try:
        import zstandard  # type: ignore

        out = zstandard.ZstdDecompressor().decompress(blob, max_output_size=expect)
        return out
    except ImportError:
        pass
    exe = shutil.which("zstd") or shutil.which("unzstd")
    if exe is None:
        raise SstateError(
            "this savestate member is zstd-compressed (zip method 93) and this box has "
            "neither the zstandard module nor the zstd command; install one "
            "(pip install zstandard, or apt install zstd) and run again.")
    done = subprocess.run([exe, "-d", "-q", "-c", "--"], input=blob, capture_output=True)
    if done.returncode != 0:
        raise SstateError("zstd refused this member: %s"
                          % done.stderr.decode("utf-8", "replace").strip()[:200])
    return done.stdout


class Savestate:
    """One PCSX2 ``.p2s``: a zip whose members this reads and never writes."""

    def __init__(self, path: os.PathLike | str) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise SstateError("no savestate at %s; pass the path to a .p2s file." % self.path)
        try:
            self._zip = zipfile.ZipFile(self.path)
        except zipfile.BadZipFile as error:
            raise SstateError("%s is not a zip, so it is not a PCSX2 savestate (%s)."
                              % (self.path.name, error)) from error

    def members(self) -> List[Tuple[str, int, int, int]]:
        """``(name, method, stored size, real size)`` for every member, in file order."""
        return [(i.filename, i.compress_type, i.compress_size, i.file_size)
                for i in self._zip.infolist()]

    def has(self, name: str) -> bool:
        return any(i.filename == name for i in self._zip.infolist())

    def member(self, name: str) -> bytes:
        """Member *name*, decompressed, whatever codec the zip used."""
        try:
            info = self._zip.getinfo(name)
        except KeyError:
            raise SstateError(
                "%s holds no member %r; it has %s."
                % (self.path.name, name, ", ".join(n for n, _, _, _ in self.members()))) from None
        with open(self.path, "rb") as handle:
            handle.seek(info.header_offset)
            head = handle.read(30)
            if head[:4] != b"PK\x03\x04":
                raise SstateError("member %r has no local header where the directory says it does; "
                                  "this savestate is damaged." % name)
            name_len, extra_len = struct.unpack_from("<HH", head, 26)
            handle.seek(name_len + extra_len, os.SEEK_CUR)
            blob = handle.read(info.compress_size)
        if info.compress_type == ZIP_ZSTD:
            raw = _zstd_decompress(blob, info.file_size)
        elif info.compress_type == ZIP_DEFLATE:
            raw = zlib.decompress(blob, -15)
        elif info.compress_type == ZIP_STORED:
            raw = blob
        else:
            raise SstateError("member %r uses zip compression method %d, which this reader does "
                              "not decode; add it here rather than working round it."
                              % (name, info.compress_type))
        if len(raw) != info.file_size:
            raise SstateError("member %r decompressed to %d byte(s), not the %d the directory "
                              "declares; this savestate is damaged."
                              % (name, len(raw), info.file_size))
        return raw

    def ee(self) -> bytes:
        """The EE main memory image."""
        return self.member(EE_MEMORY)


# ---------------------------------------------------------------------- diff


def differing_offsets(a: bytes, b: bytes) -> List[int]:
    """Every offset at which *a* and *b* differ.  Both must be the same length."""
    if len(a) != len(b):
        raise SstateError("these two images are %d and %d bytes; a diff needs the same length, "
                          "so pass two states of the same console." % (len(a), len(b)))
    try:
        import numpy  # type: ignore

        va = numpy.frombuffer(a, dtype=numpy.uint8)
        vb = numpy.frombuffer(b, dtype=numpy.uint8)
        return numpy.nonzero(va != vb)[0].tolist()
    except ImportError:
        return [i for i, (x, y) in enumerate(zip(a, b)) if x != y]


def cluster(offsets: Sequence[int], gap: int = 16) -> List[Tuple[int, int, int]]:
    """Group *offsets* into ``(start, end, differing)`` runs, joining across *gap*.

    *end* is exclusive and is one past the last differing byte, so ``end - start``
    is the run's span and *differing* is how many bytes in it actually differ.
    A run whose span far exceeds its differing count is a scattered region; a
    run whose two numbers are equal and small is a value.
    """
    if gap < 0:
        raise SstateError("a gap of %d makes no sense; pass 0 or more." % gap)
    runs: List[Tuple[int, int, int]] = []
    if not offsets:
        return runs
    start = prev = offsets[0]
    count = 1
    for off in offsets[1:]:
        if off - prev <= gap:
            count += 1
        else:
            runs.append((start, prev + 1, count))
            start = off
            count = 1
        prev = off
    runs.append((start, prev + 1, count))
    return runs


def isolation(offsets: Sequence[int], window: int = 512) -> Dict[int, int]:
    """For each differing offset, how many differing bytes lie within +/- *window*.

    This is the ranking that works.  A menu value scores 1 or 2; a counter in a
    busy structure scores tens; a churning buffer scores hundreds.
    """
    import bisect

    out: Dict[int, int] = {}
    for off in offsets:
        lo = bisect.bisect_left(offsets, off - window)
        hi = bisect.bisect_right(offsets, off + window)
        out[off] = hi - lo
    return out


# -------------------------------------------------------------- transitions


def find_transition(a: bytes, b: bytes, old: int, new: int, width: int,
                    max_bit: Optional[int] = None) -> List[Tuple[int, int]]:
    """Every ``(byte offset, bit offset in that byte)`` where a *width*-bit field
    reads *old* in *a* and *new* in *b*, at any bit alignment.

    The window is ``(width + 7) // 8 + 1`` bytes read little-endian, which covers
    a field starting anywhere in its first byte.  Returns one entry per (offset,
    bit) pair; a byte-aligned value therefore appears once, and a field that
    straddles a byte boundary appears at the byte it starts in.
    """
    if width < 1 or width > 32:
        raise SstateError("a field width of %d is not one this searches; pass 1 to 32." % width)
    if not 0 <= old < (1 << width) or not 0 <= new < (1 << width):
        raise SstateError("%d and %d do not both fit in %d bit(s); widen the field or fix the "
                          "values." % (old, new, width))
    if old == new:
        raise SstateError("the value did not change, so there is nothing to find; pass the two "
                          "different values the screen showed.")
    span = (width + 7) // 8 + 1
    mask = (1 << width) - 1
    delta = old ^ new
    top = span * 8 - width if max_bit is None else max_bit
    hits: List[Tuple[int, int]] = []
    for off in differing_offsets(a, b):
        for start in range(max(0, off - span + 1), off + 1):
            if start + span > len(a):
                continue
            wa = int.from_bytes(a[start:start + span], "little")
            wb = int.from_bytes(b[start:start + span], "little")
            x = wa ^ wb
            for bit in range(0, top + 1):
                if x != (delta << bit):
                    continue
                if ((wa >> bit) & mask) == old and ((wb >> bit) & mask) == new:
                    #: one site, one entry: a field whose first bit lands in a later
                    #: byte of the window is named by the byte it actually starts in.
                    site = (start + bit // 8, bit % 8)
                    if site not in hits:
                        hits.append(site)
    hits.sort()
    return hits


# ------------------------------------------------------------- ELF sections


class ElfSections:
    """A PS2 boot ELF's section table, used to say what kind of memory an address is."""

    def __init__(self, data: bytes) -> None:
        if data[:4] != b"\x7fELF":
            raise SstateError("this file does not start with the ELF magic, so it is not a boot "
                              "executable; pass the SLUS_xxx.xx file from the disc.")
        sh_off, = struct.unpack_from("<I", data, 32)
        sh_entsize, = struct.unpack_from("<H", data, 46)
        sh_num, = struct.unpack_from("<H", data, 48)
        sh_strndx, = struct.unpack_from("<H", data, 50)
        if not sh_num:
            raise SstateError("this ELF has no section table, so an address cannot be attributed "
                              "to a section; use the program headers instead.")
        def entry(i: int) -> Tuple[int, ...]:
            return struct.unpack_from("<10I", data, sh_off + i * sh_entsize)
        str_off = entry(sh_strndx)[4]
        self.sections: List[Tuple[str, int, int, int, int]] = []
        for i in range(sh_num):
            name_off, type_id, _flags, addr, off, size = entry(i)[:6]
            end = data.index(b"\x00", str_off + name_off)
            name = data[str_off + name_off:end].decode("latin-1")
            if size and addr:
                #: type 8 is SHT_NOBITS -- .bss and .sbss, which have no disc image.
                self.sections.append((name, addr, size, off, type_id))
        self.sections.sort(key=lambda s: s[1])

    def at(self, address: int) -> Optional[Tuple[str, int, int, int, int]]:
        for section in self.sections:
            _name, addr, size, _off, _type = section
            if addr <= address < addr + size:
                return section
        return None

    def file_offset(self, address: int) -> Optional[int]:
        """Where this address's initial value sits in the ELF file, or ``None`` for ``.bss``."""
        found = self.at(address)
        if found is None:
            return None
        name, addr, _size, off, type_id = found
        if type_id == 8:          # SHT_NOBITS
            return None
        return off + (address - addr)


# ------------------------------------------------------------- EA databases


TDB_MAGIC_V8 = b"DB\x00\x08"


def scan_tdb(image: bytes, max_tables: int = 4096) -> List[Dict[str, object]]:
    """Every little-endian EA ``TDB`` header resident in *image*, with its table list.

    A database the game read from the disc sits in EE RAM with its own header,
    table directory and field directories intact, which is what makes a RAM
    diff answerable in disc-schema terms.
    """
    out: List[Dict[str, object]] = []
    start = 0
    while True:
        at = image.find(TDB_MAGIC_V8, start)
        if at < 0:
            break
        start = at + 1
        if at + 24 > len(image):
            continue
        _unk, db_size, zero, tables, _cks = struct.unpack_from("<IIIII", image, at + 4)
        if zero or not 1 <= tables <= max_tables:
            continue
        if not 24 <= db_size <= len(image):
            continue
        dir_end = at + 24 + tables * 8
        if dir_end > len(image):
            continue
        names: List[str] = []
        ok = True
        for i in range(tables):
            raw = image[at + 24 + i * 8:at + 24 + i * 8 + 4]
            if not all(0x20 <= c <= 0x7E or c == 0 for c in raw):
                ok = False
                break
            names.append("".join(chr(c) if 0x20 <= c <= 0x7E else "\\x%02x" % c for c in raw))
        if not ok:
            continue
        out.append({"offset": at, "table_count": tables, "db_size": db_size,
                    "directory_end": dir_end, "tables": names})
    return out


def read_table_header(image: bytes, at: int) -> Dict[str, int]:
    """The 40-byte table header at *at*, as the shared reader lays it out."""
    (prior, _unk, length_bytes, length_bits, _zero, max_records, current,
     _unk2, field_count, index_count) = struct.unpack_from("<IIIIIHHIBB", image, at)
    return {"offset": at, "prior_crc": prior, "record_bytes": length_bytes,
            "record_bits": length_bits, "max_records": max_records,
            "current_records": current, "field_count": field_count,
            "index_count": index_count, "fields_offset": at + 40,
            "records_offset": at + 40 + field_count * 16}


def read_field_directory(image: bytes, at: int, count: int) -> Dict[str, Dict[str, int]]:
    """*count* 16-byte field definitions at *at*: name -> type, bit offset, bit width."""
    fields: Dict[str, Dict[str, int]] = {}
    for i in range(count):
        base = at + i * 16
        type_id, bit_offset = struct.unpack_from("<II", image, base)
        raw = image[base + 8:base + 12]
        bit_width, = struct.unpack_from("<I", image, base + 12)
        name = "".join(chr(c) if 0x20 <= c <= 0x7E else "\\x%02x" % c for c in raw)
        fields[name] = {"type": type_id, "bit_offset": bit_offset, "bit_width": bit_width}
    return fields


def find_field_directory(image: bytes, lo: int, hi: int,
                         min_fields: int = 8) -> Optional[Tuple[int, int]]:
    """The longest run of plausible 16-byte field definitions in ``[lo, hi)``.

    A runtime table can carry a copy of its schema without the database header
    that would announce it; this finds that copy so a record array beside it can
    be decoded.  Returns ``(offset, field count)``.
    """
    def plausible(at: int) -> bool:
        if at + 16 > hi:
            return False
        type_id, bit_offset = struct.unpack_from("<II", image, at)
        raw = image[at + 8:at + 12]
        bit_width, = struct.unpack_from("<I", image, at + 12)
        return (type_id <= 4 and bit_offset < 1 << 16 and 1 <= bit_width <= 512
                and all(0x20 <= c <= 0x7E for c in raw))

    best: Optional[Tuple[int, int]] = None
    at = lo
    while at < hi:
        if plausible(at):
            start = at
            n = 0
            while at < hi and plausible(at):
                at += 16
                n += 1
            if n >= min_fields and (best is None or n > best[1]):
                best = (start, n)
        else:
            at += 4
    return best


def decode_field(record: bytes, spec: Dict[str, int]) -> int:
    """One integer field of *record*, least-significant-bit first, sign-extended if signed."""
    width = spec["bit_width"]
    value = (int.from_bytes(record, "little") >> spec["bit_offset"]) & ((1 << width) - 1)
    if spec["type"] == 2 and value >> (width - 1):
        value -= 1 << width
    return value


def decode_record(image: bytes, at: int, stride: int,
                  fields: Dict[str, Dict[str, int]],
                  names: Optional[Sequence[str]] = None) -> Dict[str, int]:
    """The named integer fields of the record at *at*.  String fields are skipped."""
    record = image[at:at + stride]
    if len(record) < stride:
        raise SstateError("the record at 0x%08X runs past the end of this image; check the "
                          "offset and the stride." % at)
    wanted = list(names) if names else [n for n, f in fields.items() if f["type"] in (2, 3)]
    out: Dict[str, int] = {}
    for name in wanted:
        spec = fields.get(name)
        if spec is None or spec["type"] not in (2, 3):
            continue
        out[name] = decode_field(record, spec)
    return out


# ----------------------------------------------------------------- commands


def cmd_inventory(args: argparse.Namespace) -> int:
    root = Path(args.directory)
    states = sorted(p for p in root.glob("*.p2s") if p.is_file())
    if not states:
        print("no .p2s savestates in %s" % root)
        return 1
    print("%-44s %10s %8s %s" % ("state", "bytes", "members", "EE image"))
    for path in states:
        state = Savestate(path)
        members = state.members()
        ee = [m for m in members if m[0] == EE_MEMORY]
        print("%-44s %10s %8d %s" % (path.name, f"{path.stat().st_size:,}", len(members),
                                     f"{ee[0][3]:,}" if ee else "-"))
    print("SSTATE_INVENTORY states=%d" % len(states))
    return 0


def _two(args: argparse.Namespace) -> Tuple[bytes, bytes]:
    a = Savestate(args.a).member(args.member)
    b = Savestate(args.b).member(args.member)
    return a, b


def cmd_diff(args: argparse.Namespace) -> int:
    a, b = _two(args)
    offsets = differing_offsets(a, b)
    print("images %s bytes; differing %s (%.3f%%)"
          % (f"{len(a):,}", f"{len(offsets):,}", 100.0 * len(offsets) / max(1, len(a))))
    runs = cluster(offsets, args.gap)
    print("runs at gap=%d: %d" % (args.gap, len(runs)))
    scores = isolation(offsets, args.window)
    ranked = sorted(runs, key=lambda r: (scores.get(r[0], 1 << 30), r[1] - r[0]))
    print("\nthe %d most isolated runs (a menu value looks like the top of this list):" % args.top)
    print("  %-12s %-12s %7s %9s %s" % ("start", "end", "span", "differing", "neighbours+/-%d" % args.window))
    for start, end, count in ranked[:args.top]:
        print("  0x%08X 0x%08X %7d %9d %d"
              % (start, end, end - start, count, scores.get(start, 0)))
    print("\nthe %d largest runs (the churn a naive diff drowns in):" % args.top)
    for start, end, count in sorted(runs, key=lambda r: r[0] - r[1])[:args.top]:
        print("  0x%08X 0x%08X %7d %9d" % (start, end, end - start, count))
    print("SSTATE_DIFF differing=%d runs=%d" % (len(offsets), len(runs)))
    return 0


def cmd_transition(args: argparse.Namespace) -> int:
    a, b = _two(args)
    hits = find_transition(a, b, args.from_value, args.to_value, args.width)
    print("a %d-bit field going %d -> %d: %d site(s) in %s bytes"
          % (args.width, args.from_value, args.to_value, len(hits), f"{len(a):,}"))
    for off, bit in hits:
        print("  byte 0x%08X bit %d   %s"
              % (off, bit, "byte-aligned" if bit == 0 else "straddles the byte boundary"))
    print("SSTATE_TRANSITION sites=%d" % len(hits))
    return 0


def cmd_sections(args: argparse.Namespace) -> int:
    a, b = _two(args)
    elf = ElfSections(Path(args.elf).read_bytes())
    offsets = differing_offsets(a, b)
    counts: Dict[str, int] = {}
    for off in offsets:
        found = elf.at(off)
        counts[found[0] if found else "(outside the executable image)"] = \
            counts.get(found[0] if found else "(outside the executable image)", 0) + 1
    print("%-22s %-12s %10s %10s" % ("section", "vaddr", "size", "differing"))
    for name, addr, size, _off, type_id in elf.sections:
        n = counts.get(name, 0)
        print("%-22s 0x%08X %10s %10d%s"
              % (name, addr, f"{size:,}", n, "   (no disc image)" if type_id == 8 else ""))
        if 0 < n <= args.list_under:
            for off in offsets:
                if addr <= off < addr + size:
                    fo = elf.file_offset(off)
                    print("      0x%08X  %3d -> %-3d%s"
                          % (off, a[off], b[off],
                             "   ELF file offset 0x%08X" % fo if fo is not None else ""))
    outside = counts.get("(outside the executable image)", 0)
    print("%-22s %-12s %10s %10d" % ("(outside)", "", "", outside))
    print("SSTATE_SECTIONS sections=%d differing=%d" % (len(elf.sections), len(offsets)))
    return 0


def cmd_tdb(args: argparse.Namespace) -> int:
    a, b = _two(args)
    found = scan_tdb(a)
    print("EA TDB databases resident in this image: %d" % len(found))
    for db in found:
        extent = min(int(db["db_size"]), len(a) - int(db["offset"]))
        start = int(db["offset"])
        differing = sum(1 for i in range(start, start + extent) if a[i] != b[i])
        print("  0x%08X tables=%-4d dbSize=%-10s differing over that extent: %d"
              % (start, db["table_count"], f'{db["db_size"]:,}', differing))
        print("    %s" % " ".join(db["tables"]))
    print("SSTATE_TDB databases=%d" % len(found))
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    a, b = _two(args)
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    fields = schema.get("fields", schema)
    stride = args.stride or schema.get("stride_bytes")
    if not stride:
        raise SstateError("this schema does not say a record's stride; pass --stride.")
    names = args.field or None
    before = decode_record(a, args.at, stride, fields, names)
    after = decode_record(b, args.at, stride, fields, names)
    changed = [k for k in before if before[k] != after[k]]
    print("record at 0x%08X, stride %d, %d field(s) decoded" % (args.at, stride, len(before)))
    for name in sorted(before):
        mark = "  <<<" if name in changed else ""
        print("  %-6s %10d -> %-10d%s" % (name, before[name], after[name], mark))
    print("SSTATE_RECORD fields=%d changed=%d" % (len(before), len(changed)))
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    out = Path(args.out).resolve()
    if (out / ".git").exists() or any((p / ".git").exists() for p in out.parents):
        raise SstateError(
            "%s is inside a git checkout and a savestate member is game payload; pass a scratch "
            "directory outside the repository and delete it when you are done." % out)
    out.mkdir(parents=True, exist_ok=True)
    state = Savestate(args.a)
    blob = state.member(args.member)
    target = out / ("%s.%s" % (Path(args.a).stem, args.member))
    target.write_bytes(blob)
    print("wrote %s (%s bytes)" % (target, f"{len(blob):,}"))
    print("SSTATE_EXTRACT bytes=%d" % len(blob))
    return 0


# ----------------------------------------------------------------- selftest


def _pack_bits(values: Sequence[Tuple[Dict[str, int], int]], stride: int) -> bytes:
    """Build a record from ``(spec, value)`` pairs, least-significant-bit first."""
    acc = 0
    for spec, value in values:
        acc |= (value & ((1 << spec["bit_width"]) - 1)) << spec["bit_offset"]
    return acc.to_bytes(stride, "little")


def _synthetic_pair() -> Tuple[bytes, bytes, Dict[str, object]]:
    """Two synthetic 'EE images' that differ the way two real states do.

    Every byte here is built by this function.  The image holds, in order: a
    static region, a churning buffer, scattered single-byte counters, a
    bit-packed record array carrying a 7-bit field that goes 54 -> 56 in exactly
    one record, and a small EA TDB with its own header and field directory.
    """
    size = 1 << 16
    a = bytearray(size)
    b = bytearray(size)
    for i in range(0, size, 7):                        # a static, non-zero backdrop
        a[i] = b[i] = (i * 31 + 7) & 0xFF

    churn = (0x2000, 0x3000)                           # a buffer that rewrites itself
    for i in range(*churn):
        a[i] = (i * 13) & 0xFF
        b[i] = (i * 29 + 5) & 0xFF

    counters = [0x0400, 0x0C00, 0x1400, 0x1C00]        # scattered singles that increment
    for off in counters:
        a[off] = 0x10
        b[off] = 0x11

    stride = 132
    fields = {
        "PJEN": {"type": 3, "bit_offset": 734, "bit_width": 7},
        "POVR": {"type": 3, "bit_offset": 848, "bit_width": 7},
        "PPOS": {"type": 3, "bit_offset": 943, "bit_width": 5},
        "PHGT": {"type": 3, "bit_offset": 983, "bit_width": 7},
        "PWGT": {"type": 3, "bit_offset": 256, "bit_width": 8},
        "TGID": {"type": 3, "bit_offset": 549, "bit_width": 10},
        "PLHY": {"type": 2, "bit_offset": 1040, "bit_width": 6},
    }
    array_at = 0x8000
    rows = 24
    target_row = 7
    for row in range(rows):
        values = [
            (fields["PJEN"], 54 if row == target_row else (row * 3) % 100),
            (fields["POVR"], 98 if row == target_row else 40 + row),
            (fields["PPOS"], 14 if row == target_row else row % 21),
            (fields["PHGT"], 76),
            (fields["PWGT"], 94),
            (fields["TGID"], 1),
            (fields["PLHY"], -3),
        ]
        record = _pack_bits(values, stride)
        at = array_at + row * stride
        a[at:at + stride] = record
        b[at:at + stride] = record
    at = array_at + target_row * stride
    after = list(a[at:at + stride])
    acc = int.from_bytes(bytes(after), "little")
    acc &= ~(0x7F << 734)
    acc |= 56 << 734
    b[at:at + stride] = acc.to_bytes(stride, "little")

    # a small TDB: header, one table directory entry, a table header, a field directory
    tdb_at = 0xC000
    tables = 1
    directory_end = tdb_at + 24 + tables * 8
    table_header = directory_end
    db_size = (table_header - tdb_at) + 40 + len(fields) * 16 + stride * 2
    head = struct.pack("<4sIIIII", TDB_MAGIC_V8, 0, db_size, 0, tables, 0)
    a[tdb_at:tdb_at + len(head)] = head
    a[tdb_at + 24:tdb_at + 28] = b"PLAY"
    struct.pack_into("<I", a, tdb_at + 28, 0)
    struct.pack_into("<IIIIIHHIBB", a, table_header,
                     0, 0, stride, stride * 8 - 1, 0, 2, 2, 0, len(fields), 0)
    for i, (name, spec) in enumerate(fields.items()):
        base = table_header + 40 + i * 16
        struct.pack_into("<II", a, base, spec["type"], spec["bit_offset"])
        a[base + 8:base + 12] = name.encode("ascii")
        struct.pack_into("<I", a, base + 12, spec["bit_width"])
    b[tdb_at:tdb_at + db_size] = a[tdb_at:tdb_at + db_size]

    facts = {"stride": stride, "fields": fields, "array_at": array_at, "rows": rows,
             "target_row": target_row, "tdb_at": tdb_at, "churn": churn,
             "counters": counters,
             "answer_byte": array_at + target_row * stride + 734 // 8,
             "answer_bit": 734 % 8}
    return bytes(a), bytes(b), facts



def _write_zip_member(path: Path, name: str, packed: bytes, raw_size: int,
                      crc: int, method: int) -> None:
    """A one-member zip written by hand, so a codec Python cannot compress can be tested."""
    raw_name = name.encode("ascii")
    local = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 0, method, 0, 0,
                        crc, len(packed), raw_size, len(raw_name), 0)
    body = local + raw_name + packed
    central = struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 20, 20, 0, method, 0, 0,
                          crc, len(packed), raw_size, len(raw_name), 0, 0, 0, 0, 0, 0)
    central += raw_name
    eocd = struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 1, 1, len(central), len(body), 0)
    path.write_bytes(body + central + eocd)

def _synthetic_savestate(path: Path, ee: bytes) -> None:
    """A zip shaped like a ``.p2s``, with a deflated and a stored member."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("PCSX2 Savestate Version.id", b"\x00" * 8, zipfile.ZIP_STORED)
        zf.writestr(EE_MEMORY, ee, zipfile.ZIP_DEFLATED)


def selftest() -> int:
    checks = 0
    failures: List[str] = []

    def check(what: str, ok: object) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(what)

    a, b, facts = _synthetic_pair()

    offsets = differing_offsets(a, b)
    check("the synthetic pair differs in more than the answer", len(offsets) > 1000)
    runs = cluster(offsets, 16)
    answer_runs = [r for r in runs if r[0] <= facts["answer_byte"] < r[1]]
    check("the answer clusters into one short run", len(answer_runs) == 1 and answer_runs[0][1] - answer_runs[0][0] <= 2)
    check("the churn clusters into one long run",
          any(r[1] - r[0] > 3000 for r in runs))
    scores = isolation(offsets, 512)
    check("the answer is more isolated than the churn",
          scores[facts["answer_byte"]] <= 2
          and max(scores[o] for o in range(*facts["churn"]) if o in scores) > 100)
    check("a counter is isolated too, which is why value matters",
          scores[facts["counters"][0]] <= 2)

    hits = find_transition(a, b, 54, 56, 7)
    check("the transition search finds the planted field",
          (facts["answer_byte"], facts["answer_bit"]) in hits)
    check("and names each site once", len(hits) == len(set(hits)))
    check("a transition that did not happen is not found at the planted site",
          all(site != (facts["answer_byte"], facts["answer_bit"])
              for site in find_transition(a, b, 12, 13, 7)))
    try:
        find_transition(a, b, 54, 54, 7)
    except SstateError as error:
        check("an unchanged value refuses with a sentence", "did not change" in str(error))
    else:
        check("an unchanged value refuses with a sentence", False)
    try:
        find_transition(a, b, 54, 200, 7)
    except SstateError as error:
        check("a value too wide for the field refuses", "do not both fit" in str(error))
    else:
        check("a value too wide for the field refuses", False)

    databases = scan_tdb(a)
    check("the planted database is found", any(db["offset"] == facts["tdb_at"] for db in databases))
    planted = [db for db in databases if db["offset"] == facts["tdb_at"]][0]
    check("its table is named", planted["tables"] == ["PLAY"])
    header = read_table_header(a, planted["directory_end"])
    check("its table header reads back", header["record_bytes"] == facts["stride"]
          and header["field_count"] == len(facts["fields"]))
    fields = read_field_directory(a, header["fields_offset"], header["field_count"])
    check("its field directory reads back", fields == facts["fields"])
    window = (header["fields_offset"] - 64,
              header["fields_offset"] + header["field_count"] * 16 + 64)
    found = find_field_directory(a, *window, min_fields=4)
    check("a bare field directory is found without its header",
          found == (header["fields_offset"], header["field_count"]))
    check("a run shorter than min_fields is not reported",
          find_field_directory(a, *window, min_fields=header["field_count"] + 1) is None)

    at = facts["array_at"] + facts["target_row"] * facts["stride"]
    before = decode_record(a, at, facts["stride"], fields)
    after = decode_record(b, at, facts["stride"], fields)
    check("the record decodes to the planted values",
          before["PJEN"] == 54 and before["POVR"] == 98 and before["PPOS"] == 14
          and before["PHGT"] == 76 and before["PWGT"] == 94 and before["TGID"] == 1)
    check("a signed field sign-extends", before["PLHY"] == -3)
    check("exactly one field changed",
          [k for k in before if before[k] != after[k]] == ["PJEN"] and after["PJEN"] == 56)

    elf = _synthetic_elf()
    sections = ElfSections(elf)
    check("an ELF section table reads back",
          [s[0] for s in sections.sections] == [".text", ".data", ".bss"])
    check("a .data address has a file offset", sections.file_offset(0x00200004) == 0x1004)
    check("a .bss address has none", sections.file_offset(0x00300004) is None)
    check("an address outside every section is outside", sections.at(0x00900000) is None)

    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "SYNTH (00000000).01.p2s"
        _synthetic_savestate(state_path, a)
        state = Savestate(state_path)
        check("a savestate lists its members", state.has(EE_MEMORY))
        check("a deflated member round-trips", state.ee() == a)
        try:
            state.member("nope.bin")
        except SstateError as error:
            check("a missing member refuses by name", "holds no member" in str(error))
        else:
            check("a missing member refuses by name", False)
        if shutil.which("zstd"):
            zstd_state = Path(tmp) / "SYNTH-ZSTD.p2s"
            packed = subprocess.run(["zstd", "-q", "-c", "--"], input=a, capture_output=True).stdout
            _write_zip_member(zstd_state, EE_MEMORY, packed, len(a), zlib.crc32(a), ZIP_ZSTD)
            check("a zstd member round-trips", Savestate(zstd_state).ee() == a)
            bad = Path(tmp) / "SYNTH-BAD.p2s"
            _write_zip_member(bad, EE_MEMORY, packed, len(a) + 1, zlib.crc32(a), ZIP_ZSTD)
            try:
                Savestate(bad).ee()
            except SstateError as error:
                check("a member that decompresses short refuses", "damaged" in str(error))
            else:
                check("a member that decompresses short refuses", False)
        else:
            print("  (skipped: no zstd command on this box, so the method-93 leg was not run)")

    try:
        differing_offsets(a, a[:-1])
    except SstateError as error:
        check("a length mismatch refuses with a sentence", "same length" in str(error))
    else:
        check("a length mismatch refuses with a sentence", False)

    print("SSTATE_DIFF_SELFTEST checks=%d failures=%d" % (checks, len(failures)))
    for what in failures:
        print("  FAILED: %s" % what)
    if failures:
        print("SSTATE_DIFF_SELFTEST_FAIL")
        return 1
    print("SSTATE_DIFF_SELFTEST_PASS checks=%d" % checks)
    return 0


def _synthetic_elf() -> bytes:
    """A minimal 32-bit little-endian ELF with three named sections."""
    sections = [("", 0, 0, 0, 0),
                (".text", 1, 0x00100000, 0x1000, 0x1000),
                (".data", 1, 0x00200000, 0x1000, 0x1000),
                (".bss", 8, 0x00300000, 0x2000, 0x1000),
                (".shstrtab", 3, 0, 0, 0)]
    names = b"\x00"
    offsets = {}
    for name, *_ in sections:
        if name:
            offsets[name] = len(names)
            names += name.encode("ascii") + b"\x00"
    body_off = 0x1000
    str_off = body_off + 0x3000
    sh_off = str_off + len(names)
    out = bytearray(sh_off + len(sections) * 40)
    out[:4] = b"\x7fELF"
    out[4] = 1
    out[5] = 1
    out[6] = 1
    struct.pack_into("<HH", out, 16, 2, 8)
    struct.pack_into("<I", out, 32, sh_off)
    struct.pack_into("<HHH", out, 46, 40, len(sections), 4)
    out[str_off:str_off + len(names)] = names
    for i, (name, type_id, addr, size, off) in enumerate(sections):
        base = sh_off + i * 40
        struct.pack_into("<10I", out, base,
                         offsets.get(name, 0), type_id, 0, addr,
                         str_off if name == ".shstrtab" else off,
                         len(names) if name == ".shstrtab" else size,
                         0, 0, 0, 0)
    return bytes(out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selftest", action="store_true",
                        help="prove every pass on bytes this tool builds, and exit")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("inventory", help="list the savestates in a directory")
    p.add_argument("directory")
    p.set_defaults(run=cmd_inventory)

    def pair(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("a")
        p.add_argument("b")
        p.add_argument("--member", default=EE_MEMORY, help="which savestate member to diff")
        return p

    p = pair(sub.add_parser("diff", help="cluster the differing bytes and rank the runs"))
    p.add_argument("--gap", type=int, default=16)
    p.add_argument("--window", type=int, default=512)
    p.add_argument("--top", type=int, default=20)
    p.set_defaults(run=cmd_diff)

    p = pair(sub.add_parser("transition", help="find a known value change at any bit alignment"))
    p.add_argument("--from", dest="from_value", type=int, required=True)
    p.add_argument("--to", dest="to_value", type=int, required=True)
    p.add_argument("--width", type=int, required=True, help="the field's width in bits")
    p.set_defaults(run=cmd_transition)

    p = pair(sub.add_parser("sections", help="attribute the diff to a boot ELF's sections"))
    p.add_argument("--elf", required=True, help="the disc's boot executable, read-only")
    p.add_argument("--list-under", type=int, default=64,
                   help="list the individual bytes of any section with at most this many")
    p.set_defaults(run=cmd_sections)

    p = pair(sub.add_parser("tdb", help="find the EA databases resident in the image"))
    p.set_defaults(run=cmd_tdb)

    p = pair(sub.add_parser("record", help="decode one record against a schema"))
    p.add_argument("--at", type=lambda s: int(s, 0), required=True)
    p.add_argument("--schema", required=True, help="JSON: {stride_bytes, fields:{NAME:{type,bit_offset,bit_width}}}")
    p.add_argument("--stride", type=int, default=0)
    p.add_argument("--field", action="append", help="decode only these fields (repeatable)")
    p.set_defaults(run=cmd_record)

    p = sub.add_parser("extract", help="write one member to a scratch directory outside the repo")
    p.add_argument("a")
    p.add_argument("--member", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(run=cmd_extract)

    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not getattr(args, "run", None):
        parser.print_help()
        return 2
    try:
        return int(args.run(args))
    except SstateError as error:
        print("refused: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
