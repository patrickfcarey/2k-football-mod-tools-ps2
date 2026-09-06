"""PROTOTYPE: read the numbers out of a checked-in disc-map page.

``docs/owner/disc_maps/<SERIAL>.<label>.map.md`` is the published census for a
disc; its ``.map.json`` source is not in the repository, so the page itself is
what a round-trip has to be diffed against.  This module parses the two tables
that carry every number a page quotes -- **File kinds** and **Totals** -- into
the same shape :func:`regen.terf_totals` builds from an index, so the two can be
compared leaf by leaf.

It parses; it never measures.  A number it cannot find is reported as absent
rather than guessed, because a round-trip that silently skips a row proves
nothing.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

_ROW = re.compile(r"^\|\s*(?P<key>[^|]+?)\s*\|\s*(?P<value>.*?)\s*\|\s*$")
_INT = re.compile(r"-?[\d,]+")


def _int(text: str) -> int:
    return int(text.replace(",", ""))


def _rows(markdown: str, heading: str) -> List[Tuple[str, str]]:
    """The ``| key | value |`` rows of the table under ``## heading``."""
    lines = markdown.splitlines()
    out: List[Tuple[str, str]] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            inside = line[3:].strip().startswith(heading)
            continue
        if not inside:
            continue
        match = _ROW.match(line)
        if not match:
            continue
        key, value = match.group("key"), match.group("value")
        if set(key) <= set("-: ") or key in ("kind", "measure"):
            continue
        out.append((key, value))
    return out


def _counts(text: str, separator: str = " ") -> Dict[str, int]:
    """``"NONE (stored) 22801, LZH1 7157"`` -> ``{"NONE (stored)": 22801, ...}``.

    The mapper renders a histogram as ``name<sep>count`` pairs joined by ", ";
    the MMAP dimension row uses ``×`` as the separator instead of a space.
    """
    out: Dict[str, int] = {}
    for part in text.split(", "):
        part = part.strip()
        if not part:
            continue
        if separator == "×":
            name, _, count = part.rpartition("×")
        else:
            name, _, count = part.rpartition(" ")
        try:
            out[name.strip()] = _int(count)
        except ValueError:
            continue
    return out


def parse(path: Path) -> Dict[str, Any]:
    """Every comparable number in a disc-map page, keyed as :func:`regen.terf_totals` keys them."""
    markdown = Path(path).read_text(encoding="utf-8")
    kinds = {key.strip("`"): _int(value) for key, value in _rows(markdown, "File kinds")}
    totals = dict(_rows(markdown, "Totals"))
    out: Dict[str, Any] = {"file_kinds": kinds}

    def take(key: str) -> Optional[str]:
        return totals.get(key)

    row = take("TERF containers")
    if row:
        numbers = _INT.findall(row)
        out["terf_containers"] = _int(numbers[0])
        out["terf_containers_refused"] = _int(numbers[1])
    for source, target, separator in (
        ("chains", "chains", " "),
        ("alignments", "alignments", " "),
        ("codecs", "codecs", " "),
        ("decompressed formats", "decompressed_formats", " "),
        ("MMAP version / format id", "mmap_version_format", " "),
    ):
        if take(source):
            out[target] = _counts(totals[source], separator)
    row = take("members (level 1)")
    if row:
        out["members_level_1"] = _int(_INT.findall(row)[0])
    row = take("MMAP members")
    if row:
        numbers = _INT.findall(row)
        out["mmap_members"], out["mmap_containers"] = _int(numbers[0]), _int(numbers[1])
    for key in totals:
        if key.startswith("MMAP dimensions"):
            out["mmap_dimensions_top10"] = _counts(totals[key], "×")
    row = take("TEXT members")
    if row:
        numbers = _INT.findall(row)
        out["text_members"], out["text_bytes"], out["text_containers"] = (
            _int(numbers[0]), _int(numbers[1]), _int(numbers[2]))
    row = take("SCHl members")
    if row:
        numbers = _INT.findall(row)
        out["schl_members"] = _int(numbers[0])
        out["schl_containers"] = sorted(re.findall(r"`([^`]+)`", row))
    for key in totals:
        if key.startswith("SCHl platform"):
            left, _, right = totals[key].partition(" / ")
            out["schl_platforms"] = _counts(left)
            out["schl_codec2"] = _counts(right)
    row = take("nested TERF")
    if row:
        out["nested_terf"] = _int(_INT.findall(row)[0])
    row = take("TDB members")
    if row:
        # Targeted, not positional: the row's prose carries a literal "v8" that
        # a bare "every integer in order" reading picks up as a count.
        out["tdb_members"] = _int(re.match(r"\s*([\d,]+)", row).group(1))
        for pattern, key in ((r"bare TDB files ([\d,]+)", "bare_tdb_files"),
                             (r"distinct schema shapes ([\d,]+)", "distinct_tdb_schemas")):
            found = re.search(pattern, row)
            if found:
                out[key] = _int(found.group(1))
    row = take("unclassified / undecodable members")
    if row:
        numbers = _INT.findall(row)
        out["unclassified_level_1"] = _int(numbers[0])
        out["undecodable_level_1"] = _int(numbers[1])
        out["unclassified_all_depths"] = _int(numbers[3])
    row = take("EA BIG archives")
    if row:
        numbers = _INT.findall(row)
        out["big_archives"], out["big_entries"] = _int(numbers[0]), _int(numbers[1])
        out["big_shps"] = _int(numbers[3])
    return out


__all__ = ["parse"]
