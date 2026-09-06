"""PROTOTYPE: one walk over a disc, one index out.

Writes the artefact ``docs/owner/specs/ONE_DISC_INDEX.md`` specifies: JSON Lines,
one row per disc / file / container / member, every row self-describing.  It
exists to prove that the censuses several independent walkers produce today can
be regenerated from the index alone (``regen.py``), and it is deleted when the
specification is built for real.

Read-only.  Retail-free: names, offsets, lengths, counts, format identities,
cheap shape facts and digests.  No payload, no decoded pixel, no game string.
``retail_free_violations`` in :mod:`regen` is the check, and it is run over both
indexes in the round-trip.

Bounded by construction.  Every member is identified from a
:data:`identify.HEAD_BYTES`-byte window; ``--deep`` additionally digests each
member's stored bytes and reads TDB table/field schemas, and says so in the disc
row so a consumer can never mistake a head-only index for a deep one.

    PYTHONPATH=. python3 -m tools.owner.prototypes.disc_index.walk \\
        --iso IMAGE.iso --out DIR [--label "Title (USA)"] [--deep]
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import mmap
from pathlib import Path
import sys
import time
import zlib
from typing import Any, Callable, Dict, List, Optional

_HERE = Path(globals().get("__file__", "walk.py")).resolve().parent
_ROOT = _HERE.parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mod_editor.games._formats import blitz_zip, ea_big, ea_tdb, ea_terf  # noqa: E402
from tools import ps2_iso9660 as iso  # noqa: E402

from . import identify as ident  # noqa: E402

SCHEMA = "disc_index/proto1"

#: A container this walk opens.  Anything else is a file row and nothing more.
CONTAINER_FORMATS = ("TERF", "BIGF", "ZIP")

#: Files whose size makes a whole-file map pointless and whose format is known
#: from the head alone.
NEVER_MAP = ("MPEG-PS", "MPEG-video")


# --------------------------------------------------------------------------
# reading a file out of the image, on 2048-byte and raw-CD layouts alike
# --------------------------------------------------------------------------
class Extent:
    """One ISO9660 file, readable in ranges or as a memoryview."""

    def __init__(self, handle: Any, image: Any, entry: Any) -> None:
        self.handle, self.image, self.entry = handle, image, entry
        self.lba = entry.lba
        self.size = entry.length
        self.contiguous = (image.sector_size == iso.SECTOR_USER_BYTES and image.data_offset == 0)
        self.offset = iso.extent_byte_offset(image, self.lba)

    def available(self, wanted: int) -> int:
        if self.contiguous:
            return max(0, min(wanted, self.image.file_size - self.offset))
        last = iso.extent_byte_offset(self.image, self.lba, max(0, wanted - 1)) + 1
        return wanted if last <= self.image.file_size else 0

    def read(self, start: int, length: int) -> bytes:
        if length <= 0:
            return b""
        if self.contiguous:
            self.handle.seek(self.offset + start)
            return self.handle.read(length)
        parts, position, end = [], start, start + length
        while position < end:
            within = position % iso.SECTOR_USER_BYTES
            take = min(iso.SECTOR_USER_BYTES - within, end - position)
            self.handle.seek(iso.extent_byte_offset(self.image, self.lba, position))
            parts.append(self.handle.read(take))
            position += take
        return b"".join(parts)

    def view(self, length: Optional[int] = None):
        length = self.size if length is None else length
        if not self.contiguous or length == 0:
            data = memoryview(self.read(0, length))
            return data, data.release
        granularity = mmap.ALLOCATIONGRANULARITY
        base = self.offset - self.offset % granularity
        mapped = mmap.mmap(self.handle.fileno(), (self.offset - base) + length,
                           access=mmap.ACCESS_READ, offset=base)
        whole = memoryview(mapped)
        sliced = whole[self.offset - base:self.offset - base + length]

        def close() -> None:
            try:
                sliced.release(); whole.release(); mapped.close()
            except BufferError:  # pragma: no cover - a reader still holds a slice
                gc.collect()
                mapped.close()
        return sliced, close


def _ext(path: str) -> str:
    name = path.rsplit("/", 1)[-1].lower()
    return name.rsplit(".", 1)[-1] if "." in name else ""


# --------------------------------------------------------------------------
# containers
# --------------------------------------------------------------------------
def _terf_rows(key: str, data: Any, *, deep: bool, depth: int,
               emit: Callable[[Dict[str, Any]], None], counts: Dict[str, int]) -> None:
    """One TERF container: its chain and alignment, then one row per member."""
    try:
        container = ea_terf.parse_terf(data, allow_size_mismatch=True)
    except ea_terf.TerfError as exc:
        emit({"row": "container", "key": key, "kind": "TERF", "depth": depth,
              "refused": str(exc)[:200]})
        counts["containers_refused"] += 1
        return
    counts["containers"] += 1
    emit({"row": "container", "key": key, "kind": "TERF", "depth": depth,
          "bytes": int(container.declared_length), "members": int(container.member_count),
          "shape": {"chain": " -> ".join(c.tag for c in container.chunks),
                    "alignment": int(container.alignment),
                    "compressed": bool(container.compressed),
                    "size_mismatch": int(container.size_mismatch)}})
    for member in container.members:
        counts["members"] += 1
        row: Dict[str, Any] = {
            "row": "member", "key": "%s!%d" % (key, member.index), "container": key,
            "index": int(member.index), "offset": int(member.offset),
            "size": int(member.decompressed_size), "stored_size": int(member.stored_size),
            "codec": member.codec_name, "depth": depth,
        }
        if member.stored_size == 0:
            row["format"] = "empty"
            emit(row)
            continue
        try:
            head = container.member(member.index, max_output=ident.HEAD_BYTES)
        except ea_terf.TerfError as exc:
            row["format"] = "undecodable"
            row["refused"] = str(exc)[:160]
            counts["members_undecodable"] += 1
            emit(row)
            continue
        identity = ident.identify(head, member.decompressed_size)
        row.update(identity.as_row())
        if identity.format == "TERF" and depth < 3:
            emit(row)
            _terf_rows("%s!%d" % (key, member.index), container.member(member.index),
                       deep=deep, depth=depth + 1, emit=emit, counts=counts)
            continue
        if identity.format == "TDB" and deep:
            try:
                database = ea_tdb.parse_tdb(container.member(member.index))
            except Exception as exc:                      # noqa: BLE001 - a refusal is a fact
                row["tdb_refused"] = str(exc)[:160]
            else:
                row["tdb"] = _tdb_shape(database)
        if deep:
            row["stored_sha256"] = hashlib.sha256(container.stored(member.index)).hexdigest()
        emit(row)


def _tdb_shape(database: Any) -> Dict[str, Any]:
    """Table names, record strides, row counts and field name/type/width triples.

    A field name is the schema and is identical on every copy of the game; no
    record is read.
    """
    tables = []
    for table in database.tables:
        tables.append({
            "name": table.name, "records": int(table.current_records),
            "max_records": int(table.max_records),
            "record_bytes": int(table.record_bytes),
            "fields": [[f.name, int(f.type_id), int(f.bit_width), int(f.bit_offset)]
                       for f in table.fields],
        })
    return {"tables": tables, "table_count": len(tables)}


def _big_rows(key: str, archive: Any, *, deep: bool, depth: int,
              emit: Callable[[Dict[str, Any]], None], counts: Dict[str, int]) -> None:
    counts["archives"] += 1
    emit({"row": "container", "key": key, "kind": "BIGF", "depth": depth,
          "bytes": int(archive.total_bytes) if hasattr(archive, "total_bytes") else None,
          "members": len(archive.entries)})
    for entry in archive.entries:
        counts["members"] += 1
        row: Dict[str, Any] = {
            "row": "member", "key": "%s!%s" % (key, entry.name), "container": key,
            "index": int(entry.index), "name": entry.name, "offset": int(entry.offset),
            "size": int(entry.size), "depth": depth,
        }
        if entry.size == 0:
            row["format"] = "empty"
            emit(row)
            continue
        try:
            head = archive.member(entry.index, max_output=ident.HEAD_BYTES)
        except Exception as exc:                          # noqa: BLE001
            row["format"] = "undecodable"
            row["refused"] = str(exc)[:160]
            emit(row)
            continue
        identity = ident.identify(head, entry.size)
        row.update(identity.as_row())
        emit(row)
        if identity.format == "BIGF" and depth < 2:
            try:
                nested = archive.nested(entry.index)
            except Exception:                             # noqa: BLE001
                continue
            _big_rows("%s!%s" % (key, entry.name), nested, deep=deep, depth=depth + 1,
                      emit=emit, counts=counts)


def _zip_rows(key: str, extent: Extent, *, deep: bool,
              emit: Callable[[Dict[str, Any]], None], counts: Dict[str, int]) -> None:
    """A Midway stored ZIP, read through its central directory only."""
    archive = blitz_zip.read_zip(extent.read, extent.size)
    counts["archives"] += 1
    emit({"row": "container", "key": key, "kind": "ZIP", "depth": 0,
          "bytes": int(extent.size), "members": len(archive.members),
          "shape": {"central_offset": int(archive.central_offset),
                    "central_bytes": int(archive.central_bytes)}})
    for number, member in enumerate(archive.members):
        counts["members"] += 1
        size = int(member.size)
        head = extent.read(member.data_offset, min(size, ident.HEAD_BYTES))

        def read_at(offset: int, length: int, _base: int = member.data_offset) -> bytes:
            return extent.read(_base + offset, length)

        identity = ident.identify(head, size, read=read_at, name=member.name)
        row: Dict[str, Any] = {
            "row": "member", "key": "%s!%s" % (key, member.name), "container": key,
            "index": number, "name": member.name, "ext": _ext(member.name),
            "offset": int(member.data_offset), "size": size, "stored_size": size,
            "codec": "stored", "depth": 0, "crc32": "%08x" % member.crc32,
        }
        row.update(identity.as_row())
        if deep:
            payload = extent.read(member.data_offset, size)
            row["stored_sha256"] = hashlib.sha256(payload).hexdigest()
            # Recomputed, not copied: the archive's own CRC column is ``crc32``
            # above, so a consumer can compare the two without re-reading 361 MB.
            row["payload_crc32"] = "%08x" % (zlib.crc32(payload) & 0xFFFFFFFF)
        emit(row)


def _zih_row(key: str, extent: Extent, emit: Callable[[Dict[str, Any]], None]) -> None:
    """The ``.ZIH`` beside a Midway ZIP: its own shape, and one row per record."""
    try:
        index = blitz_zip.read_index(extent.read(0, extent.size))
    except Exception as exc:                              # noqa: BLE001
        emit({"row": "container", "key": key, "kind": "ZIH", "depth": 0, "refused": str(exc)[:200]})
        return
    emit({"row": "container", "key": key, "kind": "ZIH", "depth": 0,
          "bytes": int(extent.size), "members": len(index.entries),
          "shape": {"variant": index.shape, "declared_entries": int(index.declared_entries),
                    "declared_body_bytes": int(index.declared_body_bytes),
                    "directory_bytes": int(index.directory_bytes),
                    "consumed_whole_file": bool(index.consumed_whole_file),
                    "has_crc_column": bool(index.has_crc_column)}})
    for number, entry in enumerate(index.entries):
        row = {"row": "member", "key": "%s!%s" % (key, entry.name), "container": key,
               "index": number, "name": entry.name, "ext": _ext(entry.name),
               "offset": int(entry.data_offset), "size": int(entry.size),
               "format": "ZIH-record", "depth": 0}
        if entry.crc32 is not None:
            row["crc32"] = "%08x" % entry.crc32
        emit(row)


# --------------------------------------------------------------------------
# the walk
# --------------------------------------------------------------------------
def index_disc(iso_path: Path, out_path: Path, *, label: str = "", deep: bool = False,
               progress: bool = False) -> Dict[str, Any]:
    started = time.time()
    image = iso.open_image(iso_path)
    identity = iso.boot_identity(image)
    counts = {"files": 0, "containers": 0, "containers_refused": 0, "archives": 0,
              "members": 0, "members_undecodable": 0, "rows": 0}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(iso_path, "rb")
    with open(out_path, "w", encoding="utf-8", newline="\n") as sink:
        def emit(row: Dict[str, Any]) -> None:
            sink.write(json.dumps(row, sort_keys=True) + "\n")
            counts["rows"] += 1

        entries = [e for e in iso.iter_entries(image) if not e.is_dir]
        emit({"row": "disc", "schema": SCHEMA, "serial": identity.get("serial"),
              "label": label or Path(iso_path).name, "image_bytes": int(image.file_size),
              "sector_size": int(image.sector_size), "files": len(entries),
              "boot_file": identity.get("boot_file"), "walk": "deep" if deep else "head",
              "head_bytes": ident.HEAD_BYTES})
        for entry in entries:
            counts["files"] += 1
            extent = Extent(handle, image, entry)
            head = extent.read(0, min(extent.size, ident.HEAD_BYTES)) if extent.size else b""
            file_identity = ident.identify(head, extent.size, read=extent.read, name=entry.path)
            row: Dict[str, Any] = {"row": "file", "path": entry.path, "bytes": int(extent.size),
                                   "lba": int(entry.lba), "ext": _ext(entry.path)}
            row.update(file_identity.as_row())
            fmt = file_identity.format
            if fmt == "TDB" and deep:
                try:
                    row["tdb"] = _tdb_shape(ea_tdb.parse_tdb(extent.read(0, extent.size)))
                except Exception as exc:                   # noqa: BLE001
                    row["tdb_refused"] = str(exc)[:160]
            emit(row)
            if fmt in NEVER_MAP or extent.size == 0:
                continue
            if fmt == "TERF":
                span = extent.size
                try:
                    declared = ea_terf.declared_length(extent.read(0, min(extent.size, 8192)))
                    if declared > extent.size:
                        span = extent.available(declared) or extent.size
                except Exception:                          # noqa: BLE001
                    pass
                data, close = extent.view(span)
                try:
                    _terf_rows(entry.path, data, deep=deep, depth=0, emit=emit, counts=counts)
                finally:
                    close()
            elif fmt == "BIGF":
                data, close = extent.view(extent.size)
                try:
                    archive = ea_big.parse_big(data, name=entry.path)
                except Exception as exc:                   # noqa: BLE001
                    emit({"row": "container", "key": entry.path, "kind": "BIGF", "depth": 0,
                          "refused": str(exc)[:200]})
                    close()
                else:
                    try:
                        _big_rows(entry.path, archive, deep=deep, depth=0, emit=emit, counts=counts)
                    finally:
                        close()
            elif fmt == "ZIP":
                try:
                    _zip_rows(entry.path, extent, deep=deep, emit=emit, counts=counts)
                except Exception as exc:                   # noqa: BLE001
                    emit({"row": "container", "key": entry.path, "kind": "ZIP", "depth": 0,
                          "refused": str(exc)[:200]})
            elif row["ext"] == "zih":
                _zih_row(entry.path, extent, emit)
            if progress:
                print("%6.1fs %s" % (time.time() - started, entry.path), file=sys.stderr, flush=True)
        seconds = time.time() - started
        emit({"row": "totals", "seconds": round(seconds, 2), **counts})
    handle.close()
    counts["seconds"] = round(time.time() - started, 2)
    return counts


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="disc_index.walk",
                                     description="PROTOTYPE: index one PlayStation 2 disc into JSON Lines. Read-only.")
    parser.add_argument("--iso", required=True)
    parser.add_argument("--out", required=True, help="directory for <serial>.index.jsonl")
    parser.add_argument("--label", default="")
    parser.add_argument("--deep", action="store_true",
                        help="also digest each member's stored bytes and read TDB schemas")
    parser.add_argument("--progress", action="store_true")
    arguments = parser.parse_args(argv)
    image = iso.open_image(Path(arguments.iso))
    serial = iso.boot_identity(image).get("serial") or Path(arguments.iso).stem
    out = Path(arguments.out) / ("%s.index.jsonl" % serial)
    counts = index_disc(Path(arguments.iso), out, label=arguments.label,
                        deep=arguments.deep, progress=arguments.progress)
    print("DISC_INDEX_DONE serial=%s out=%s %s" % (
        serial, out, " ".join("%s=%s" % kv for kv in sorted(counts.items()))))
    return 0


__all__ = ["CONTAINER_FORMATS", "Extent", "SCHEMA", "index_disc"]


if __name__ == "__main__":
    raise SystemExit(_main())
