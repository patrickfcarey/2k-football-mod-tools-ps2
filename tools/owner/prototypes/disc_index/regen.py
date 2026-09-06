"""PROTOTYPE: regenerate published censuses from a disc index, and diff them.

This is the load-bearing claim of ``docs/owner/specs/ONE_DISC_INDEX.md``: if one
index can reproduce what several independent walkers publish today, those
walkers can read the index instead of walking.  Every function here opens **only**
the index JSONL -- never a disc image, never a format reader -- so a match is a
statement about the index and not about a second walk that happens to agree.

    PYTHONPATH=. python3 -m tools.owner.prototypes.disc_index.regen \\
        --index DIR/SLUS-20051.index.jsonl --check blitz2002 [--out result.json]
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = Path(globals().get("__file__", "regen.py")).resolve().parent
_ROOT = _HERE.parents[3]

#: Recomputed over the 600 smallest members under this cap, exactly as
#: ``blitz_zip.cross_check`` samples them.
CRC_CHECK_LIMIT = 1 << 22
CRC_SAMPLE = 600


def load(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def rows_of(index: Sequence[Dict[str, Any]], kind: str) -> List[Dict[str, Any]]:
    return [row for row in index if row.get("row") == kind]


def members_of(index: Sequence[Dict[str, Any]], container: str) -> List[Dict[str, Any]]:
    return [row for row in index if row.get("row") == "member" and row.get("container") == container]


# --------------------------------------------------------------------------
# retail-free check: the rule the specification asserts, applied to the artefact
# --------------------------------------------------------------------------
#: Fields allowed to carry hexadecimal.  Everything else that looks like a long
#: hex run is a payload sample and is a violation.
_HEX_FIELDS = {"magic", "crc32", "payload_crc32", "stored_sha256", "sha256",
               "library_version", "format_id", "top_level_sequence"}
_LONG_HEX = re.compile(r"^[0-9a-fA-F]{9,}$")


def retail_free_violations(index: Sequence[Dict[str, Any]]) -> List[str]:
    """Every place a row carries something that is not a name, number or digest.

    The rule the specification states, made executable: a row may carry a member
    or file **name**, an offset, a length, a count, a format identity, a
    four-byte tag, a schema field name/type/width, and a digest.  Nothing else
    that came off the disc.  A base64 or long-hex string in any other field, or
    a text value longer than a name, is a payload sample that has escaped.
    """
    bad: List[str] = []

    def check(row_key: str, path: str, value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                check(row_key, "%s.%s" % (path, key), item)
        elif isinstance(value, list):
            for number, item in enumerate(value):
                check(row_key, "%s[%d]" % (path, number), item)
        elif isinstance(value, str):
            leaf = path.rsplit(".", 1)[-1].split("[", 1)[0]
            if leaf in _HEX_FIELDS or leaf in ("key", "container", "name", "path",
                                               "label", "refused", "rule", "tdb_refused",
                                               "chain", "note"):
                return
            if _LONG_HEX.match(value):
                bad.append("%s: %s carries a %d-character hex run" % (row_key, path, len(value)))
            elif len(value) > 120:
                bad.append("%s: %s carries a %d-character string" % (row_key, path, len(value)))

    for row in index:
        check(row.get("key") or row.get("path") or row.get("row", "?"), row.get("row", "?"), row)
    return bad


# --------------------------------------------------------------------------
# census 1 -- nflblitz<year>_ps2/containers.json
# --------------------------------------------------------------------------
def blitz_containers(index: Sequence[Dict[str, Any]], *, archive: str, schema: str,
                     produced_by: str) -> Dict[str, Any]:
    """Rebuild the Blitz ZIP module's container census from index rows alone.

    The lane iterates members **sorted by name** within each suffix, and its
    sequence histogram keeps the top six by count with ties broken by
    first-seen order; both are reproduced here because a census whose tail is an
    insertion-order tie-break is otherwise not reproducible from a differently
    ordered walk.  That is a finding, and the specification says so.
    """
    members = sorted(members_of(index, archive), key=lambda row: row.get("name", ""))
    cameras = [row for row in members if row["ext"] == "cap"]
    wiffs = [row for row in members if row["ext"] in ("wip", "wom", "wmp")]
    clumps = [row for row in members if row["ext"] == "dff"]

    word1 = collections.Counter(row["shape"]["header_word1"] for row in cameras)
    forms = collections.Counter(row["shape"]["form"] for row in wiffs)
    sequences: Dict[str, int] = {}
    versions: Dict[str, int] = {}
    consumed = 0
    for row in clumps:
        shape = row.get("shape") or {}
        key = shape.get("top_level_sequence", "")
        sequences[key] = sequences.get(key, 0) + 1
        version = shape.get("library_version")
        if version:
            versions[version] = versions.get(version, 0) + 1
        consumed += 1 if shape.get("walk_consumes_the_member") else 0
    return {
        "camera_header_word1_census": {str(k): v for k, v in sorted(word1.items())},
        "camera_paths": len(cameras),
        "camera_records": sum(row["shape"]["records"] for row in cameras),
        "clump_library_versions": dict(sorted(versions.items())),
        "clump_members": len(clumps),
        "clump_top_level_sequences": dict(sorted(sorted(sequences.items(),
                                                        key=lambda item: -item[1])[:6])),
        "clumps_whose_walk_consumes_the_member": consumed,
        "note": "Counts and header words only. No container's payload is here.",
        "produced_by": produced_by,
        "refusals": sum(1 for row in members if "refused" in row),
        "schema": schema,
        "wiff_forms": dict(sorted(forms.items())),
        "wiff_members": len(wiffs),
    }


# --------------------------------------------------------------------------
# census 2 -- nflblitz<year>_ps2/zip-index.json
# --------------------------------------------------------------------------
def blitz_zip_index(index: Sequence[Dict[str, Any]], *, archive: str, zih: str,
                    schema: str) -> Dict[str, Any]:
    """Rebuild the Blitz ZIP-vs-index cross-check from index rows alone."""
    disc = rows_of(index, "disc")[0]
    files = {row["path"]: row for row in rows_of(index, "file")}
    containers = {row["key"]: row for row in rows_of(index, "container")}
    zip_members = members_of(index, archive)
    zih_entries = members_of(index, zih)

    by_name = {row["name"]: row for row in zip_members}
    sizes = offsets = crc_column = 0
    for entry in zih_entries:
        member = by_name.get(entry["name"])
        if member is None:
            continue
        sizes += 1 if member["size"] == entry["size"] else 0
        offsets += 1 if member["offset"] == entry["offset"] else 0
        if entry.get("crc32") is not None:
            crc_column += 1 if member.get("crc32") == entry["crc32"] else 0

    shape = containers[zih]["shape"]
    has_crc = bool(shape["has_crc_column"])
    smallest = sorted((entry for entry in zih_entries
                       if entry.get("crc32") is not None and 0 < entry["size"] <= CRC_CHECK_LIMIT),
                      key=lambda entry: entry["size"])[:CRC_SAMPLE]
    recomputed = agreed = 0
    for entry in smallest:
        member = by_name.get(entry["name"])
        if member is None or "payload_crc32" not in member:
            continue
        recomputed += 1
        agreed += 1 if member["payload_crc32"] == entry["crc32"] else 0

    return {
        "cross_check": {
            "crc_column_agrees": crc_column if has_crc else None,
            "crc_recomputed": recomputed,
            "crc_recomputed_agrees": agreed,
            "data_offsets_agree": offsets,
            "index_entries": len(zih_entries),
            "index_order_is_by_name": [e["name"] for e in zih_entries]
                                      == sorted(e["name"] for e in zih_entries),
            "index_shape": shape["variant"],
            "names_in_both": len({e["name"] for e in zih_entries} & set(by_name)),
            "names_match_as_sets": {e["name"] for e in zih_entries} == set(by_name),
            "sizes_agree": sizes,
            "zip_entries": len(zip_members),
            "zip_order_is_by_data_offset": [m["name"] for m in zip_members]
                                           == [m["name"] for m in sorted(zip_members,
                                                                         key=lambda m: m["offset"])],
        },
        "disc": {
            "archive": archive,
            "archive_bytes": files[archive]["bytes"],
            "index": zih,
            "index_bytes": files[zih]["bytes"],
            "serial": disc["serial"],
        },
        "index_has_crc_column": has_crc,
        "index_shape": shape["variant"],
        "member_extensions": dict(sorted(collections.Counter(
            row["ext"] for row in zip_members).items())),
        "members": len(zip_members),
        "note": "Counts, names, offsets and lengths only. No member's bytes are here.",
        "schema": schema,
    }


# --------------------------------------------------------------------------
# census 3 -- the disc map's "File kinds" and "Totals" tables
# --------------------------------------------------------------------------
#: Names this identifier gives that ``ea_terf.identify_member`` -- and so the
#: mapper and the readiness tool -- report as *unclassified*.  A consumer that
#: wants the coarser answer projects these back; the index keeps the finer one.
MAPPER_CALLS_UNCLASSIFIED = ("unknown", "PS2-ICO", "zero-head")


def _mapper_unclassified(row: Dict[str, Any]) -> bool:
    fmt = row.get("format", "")
    return fmt in MAPPER_CALLS_UNCLASSIFIED or fmt.endswith("?")


def as_mapper_names_a_file(row: Dict[str, Any]) -> str:
    """The mapper's ``identify_head`` vocabulary for a *file* row.

    ``identify_head`` knows ``PS2-ICO`` and ``zero-head`` and renders anything
    else it cannot name as ``other:<forward hex of the first four bytes>``.
    ``identify_member`` -- the member-level answer -- knows neither and says
    ``unclassified``.  Two vocabularies for one question, which is the argument
    for one identifier and is why this projection has to exist at all.
    """
    fmt = row.get("format", "")
    if fmt == "unknown" or fmt.endswith("?"):
        return "other:" + (row.get("magic") or "")
    return fmt


def as_mapper_names_a_member(row: Dict[str, Any]) -> str:
    """The mapper's ``identify_member`` vocabulary for a *member* row."""
    return "unclassified" if _mapper_unclassified(row) else row.get("format", "unclassified")


#: EA table/field types, as the mapper's ``TDB_FIELD_TYPES`` names them.
TDB_FIELD_TYPES = {0: "string", 1: "binary", 2: "sint", 3: "uint", 4: "float"}


def tdb_signature(shape: Dict[str, Any]) -> str:
    """The mapper's ``schema_signature``: table and field names, types and widths.

    Deliberately excludes record counts and bit offsets, so two databases with
    the same schema and different row counts count once.  The index carries the
    counts and the offsets as well; this is the projection, not the storage.
    """
    tables = [(table["name"],
               tuple((field[0], TDB_FIELD_TYPES.get(field[1], str(field[1])), field[2])
                     for field in table["fields"]))
              for table in shape["tables"]]
    return hashlib.sha256(repr(tables).encode("utf-8")).hexdigest()[:16]


def terf_totals(index: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The numbers a disc-map page quotes, rebuilt from index rows alone."""
    files = rows_of(index, "file")
    containers = rows_of(index, "container")
    terf_keys = {row["key"] for row in containers if row.get("kind") == "TERF"}
    big_keys = {row["key"] for row in containers if row.get("kind") == "BIGF"}
    top = [row for row in containers if row.get("kind") == "TERF" and row.get("depth") == 0]
    members = [row for row in rows_of(index, "member") if row.get("container") in terf_keys]
    level1 = [row for row in members if row.get("depth") == 0]
    big_members = [row for row in rows_of(index, "member") if row.get("container") in big_keys]

    mmap_rows = [row for row in level1 if row.get("format") == "MMAP"]
    dimensions = collections.Counter(
        "%dx%d" % (row["shape"]["width"], row["shape"]["height"])
        for row in mmap_rows if row["shape"].get("format_id") != "0x400")
    version_format = collections.Counter(
        "v%d/fmt%s" % (row["shape"]["version"], row["shape"]["format_id"]) for row in mmap_rows)
    schl_rows = [row for row in level1 if row.get("format") == "SCHl"]
    text_rows = [row for row in level1 if row.get("format") == "TEXT"]
    tdb_rows = [row for row in level1 if row.get("format") == "TDB"]

    return {
        "file_kinds_measured": dict(collections.Counter(row["format"] for row in files).most_common()),
        "file_kinds": dict(collections.Counter(
            as_mapper_names_a_file(row) for row in files).most_common()),
        "terf_containers": len(top),
        "terf_containers_refused": sum(1 for row in containers
                                       if row.get("kind") == "TERF" and "refused" in row),
        "chains": dict(collections.Counter(row["shape"]["chain"] for row in top).most_common()),
        "alignments": dict(collections.Counter(str(row["shape"]["alignment"])
                                               for row in top).most_common()),
        "members_level_1": len(level1),
        "codecs": dict(collections.Counter(row.get("codec", "-") for row in level1).most_common()),
        "decompressed_formats_measured": dict(collections.Counter(
            row.get("format", "unknown") for row in level1).most_common()),
        "decompressed_formats": dict(collections.Counter(
            as_mapper_names_a_member(row) for row in level1).most_common()),
        "mmap_members": len(mmap_rows),
        "mmap_containers": len({row["container"] for row in mmap_rows}),
        "mmap_dimensions_top10": dict(dimensions.most_common(10)),
        "mmap_version_format": dict(version_format.most_common()),
        "text_members": len(text_rows),
        "text_bytes": sum(row["size"] for row in text_rows),
        "text_containers": len({row["container"] for row in text_rows}),
        "schl_members": len(schl_rows),
        "schl_containers": sorted({row["container"] for row in schl_rows}),
        "schl_platforms": dict(collections.Counter(
            str(row["shape"].get("platform")) for row in schl_rows).most_common()),
        "schl_codec2": dict(collections.Counter(
            ("c2=0x%02x" % row["shape"]["codec2"]) if row["shape"].get("codec2") is not None else "-"
            for row in schl_rows).most_common()),
        "nested_terf": sum(1 for row in level1 if row.get("format") == "TERF"),
        "tdb_members": len(tdb_rows),
        "bare_tdb_files": sum(1 for row in files if row.get("format") == "TDB"),
        "distinct_tdb_schemas": len({tdb_signature(row["tdb"])
                                     for row in tdb_rows + files if "tdb" in row}),
        "unclassified_level_1": sum(1 for row in level1 if _mapper_unclassified(row)),
        "undecodable_level_1": sum(1 for row in level1 if row.get("format") == "undecodable"),
        "unclassified_all_depths": sum(1 for row in members if _mapper_unclassified(row)),
        "big_archives": sum(1 for row in files if row.get("format") == "BIGF"),
        "big_entries": sum(1 for row in big_members if row.get("depth") == 0),
        "big_entries_all_depths": len(big_members),
        "big_shps": sum(1 for row in big_members if row.get("format") == "SHPS"),
        "big_nested": sum(1 for row in big_members if row.get("format") == "BIGF"),
    }


# --------------------------------------------------------------------------
# diffing
# --------------------------------------------------------------------------
def diff(regenerated: Any, published: Any, path: str = "") -> List[Dict[str, Any]]:
    """Every place two JSON documents disagree, leaf by leaf."""
    out: List[Dict[str, Any]] = []
    if isinstance(regenerated, dict) and isinstance(published, dict):
        for key in sorted(set(regenerated) | set(published)):
            here = "%s.%s" % (path, key) if path else key
            if key not in regenerated:
                out.append({"at": here, "regenerated": None, "published": published[key],
                            "why": "the index does not carry this"})
            elif key not in published:
                out.append({"at": here, "regenerated": regenerated[key], "published": None,
                            "why": "the index carries more than the census does"})
            else:
                out += diff(regenerated[key], published[key], here)
    elif regenerated != published:
        out.append({"at": path or "<root>", "regenerated": regenerated, "published": published})
    return out


def check_terf_map(index_path: Path, map_path: Path) -> Dict[str, Any]:
    """Regenerate a disc-map page's numbers from the index and diff them against the page.

    Only the keys the page carries are compared; a key the index has and the
    page does not is not a difference, and is reported separately so the extra
    is visible without being counted as a mismatch.
    """
    from . import map_md

    index = load(index_path)
    regenerated = terf_totals(index)
    published = map_md.parse(map_path)
    projected = {key: regenerated[key] for key in published if key in regenerated}
    missing = sorted(key for key in published if key not in regenerated)
    differences = diff(projected, published)
    return {"index": str(index_path), "checks": [{
        "census": str(map_path), "label": map_path.name,
        "identical": not differences and not missing,
        "keys_compared": sorted(projected), "keys_the_index_cannot_answer": missing,
        "differences": differences}],
        "index_carries_beyond_the_page": sorted(set(regenerated) - set(published)),
        "retail_free_violations": retail_free_violations(index)}


CHECKS: Dict[str, Dict[str, Any]] = {
    "blitz2002": {
        "containers": "docs/product/measured/nflblitz2002_ps2/containers.json",
        "zip_index": "docs/product/measured/nflblitz2002_ps2/zip-index.json",
        "containers_schema": "nflblitz_ps2_containers_measured/v1",
        "zip_schema": "nflblitz_ps2_zip_index_measured/v1",
        "produced_by": "python3 -m mod_editor.games.nflblitz2002_ps2.camera_lane",
    },
    "blitz2003": {
        "containers": "docs/product/measured/nflblitz2003_ps2/containers.json",
        "zip_index": "docs/product/measured/nflblitz2003_ps2/zip-index.json",
        "containers_schema": "nflblitz_ps2_containers_measured/v1",
        "zip_schema": "nflblitz_ps2_zip_index_measured/v1",
        "produced_by": "python3 -m mod_editor.games.nflblitz2003_ps2.camera_lane",
    },
}


def zip_pair(index: Sequence[Dict[str, Any]]) -> Tuple[str, str]:
    """The disc's ZIP and its ``.ZIH``, discovered from the index, never pinned.

    The two Blitz discs name the pair differently (``BASSETS`` / ``BERTHA``); a
    consumer that reads the index does not have to know which.
    """
    containers = rows_of(index, "container")
    zips = [row["key"] for row in containers if row.get("kind") == "ZIP"]
    zihs = [row["key"] for row in containers if row.get("kind") == "ZIH"]
    if len(zips) != 1 or len(zihs) != 1:
        raise SystemExit("expected exactly one ZIP and one ZIH container, found %d and %d"
                         % (len(zips), len(zihs)))
    return zips[0], zihs[0]


def check_blitz(index_path: Path, name: str, root: Path) -> Dict[str, Any]:
    spec = dict(CHECKS[name])
    index = load(index_path)
    spec["archive"], spec["zih"] = zip_pair(index)
    results = []
    for label, builder, published in (
        ("containers.json", lambda: blitz_containers(
            index, archive=spec["archive"], schema=spec["containers_schema"],
            produced_by=spec["produced_by"]), spec["containers"]),
        ("zip-index.json", lambda: blitz_zip_index(
            index, archive=spec["archive"], zih=spec["zih"],
            schema=spec["zip_schema"]), spec["zip_index"]),
    ):
        regenerated = builder()
        with open(root / published, "r", encoding="utf-8") as handle:
            checked_in = json.load(handle)
        differences = diff(regenerated, checked_in)
        results.append({"census": published, "label": label,
                        "identical": not differences, "differences": differences})
    return {"index": str(index_path), "checks": results,
            "retail_free_violations": retail_free_violations(index)}


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="disc_index.regen",
                                     description="PROTOTYPE: regenerate published censuses from a disc index.")
    parser.add_argument("--index", required=True)
    parser.add_argument("--check", choices=sorted(CHECKS) + ["terf-totals", "terf-map"], required=True)
    parser.add_argument("--map", help="the checked-in <SERIAL>.<label>.map.md to diff against")
    parser.add_argument("--root", default=str(_ROOT))
    parser.add_argument("--out")
    arguments = parser.parse_args(argv)
    root = Path(arguments.root)
    if arguments.check == "terf-map":
        if not arguments.map:
            parser.error("--check terf-map needs --map <disc map .md>")
        result = check_terf_map(Path(arguments.index), Path(arguments.map))
        check = result["checks"][0]
        verdict = "REGEN terf-map identical=%s compared=%d unanswerable=%d retail_free_violations=%d" % (
            check["identical"], len(check["keys_compared"]),
            len(check["keys_the_index_cannot_answer"]), len(result["retail_free_violations"]))
    elif arguments.check == "terf-totals":
        result = {"index": arguments.index,
                  "totals": terf_totals(load(Path(arguments.index))),
                  "retail_free_violations": retail_free_violations(load(Path(arguments.index)))}
        verdict = "TERF_TOTALS rows=%d" % len(result["totals"])
    else:
        result = check_blitz(Path(arguments.index), arguments.check, root)
        identical = sum(1 for check in result["checks"] if check["identical"])
        verdict = "REGEN %s identical=%d/%d retail_free_violations=%d" % (
            arguments.check, identical, len(result["checks"]),
            len(result["retail_free_violations"]))
    if arguments.out:
        Path(arguments.out).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                       encoding="utf-8", newline="\n")
    print(verdict)
    for check in result.get("checks", []):
        print("  %-16s %s" % (check["label"], "IDENTICAL" if check["identical"]
                              else "%d difference(s)" % len(check["differences"])))
        for difference in check["differences"][:12]:
            print("      %s: regenerated=%r published=%r" % (
                difference["at"], difference.get("regenerated"), difference.get("published")))
    return 0


__all__ = ["as_mapper_names_a_file", "as_mapper_names_a_member", "blitz_containers", "blitz_zip_index", "check_blitz", "diff", "load",
           "members_of", "retail_free_violations", "rows_of", "tdb_signature",
           "terf_totals", "zip_pair"]


if __name__ == "__main__":
    raise SystemExit(_main())
