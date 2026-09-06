#!/usr/bin/env python3
"""Resolve the mechanical conflicts of one rebase or merge step in a 2k-football-mod-tools worktree.

Usage: python3 resolve_step.py <worktree>

Every module branch registers its rows against the sixteen shared files (registry, allowlist,
count pins, runtime checkers, STATUS, getting-started, three tests, ...), so two module branches
stacked on one lane conflict in all of them, and the resolutions are the same every time. For
every file git reports as unmerged (UU):

* ``registry.v1.json``          -> three-way by row id: rows added or changed by THEIRS applied onto
                                   OURS, then sorted; ``games`` sorted canonically
* ``game.json``                 -> three-way JSON merge (product_modules union; page_notes: drops + changes)
* ``*.fragment.json``, ``pins.json``, ``CONTRACT_PINS.json`` -> theirs (the caller regenerates them)
* ``release-allowlist.txt``, ``allowlist.fragment.txt``     -> ours then theirs, exact duplicates dropped
* runtime checkers             -> hunk union, then ``len(registry.capabilities) == N`` re-set
* ``validate_all_...py``       -> theirs, then ``EXPECTED_*`` recomputed from the merged registry
* ``validate_registry.py``     -> hunk union, then every ``SURFACE_GAMES[...]`` key reduced to ONE line
                                   that is the UNION of every variant's ``+`` terms (keeping the widest
                                   line dropped a side when both branches widened by the same length:
                                   the NCAA 09 + MVP 2005 stack, 2026-09-06)
* everything else              -> hunk union (ours lines, then theirs lines not already present), with
                                   a digit-only difference (a count, a version) keeping OURS for the
                                   count re-set to fix, and consecutive exact duplicate lines collapsed

Prints one line per file. Exit 1 if any marker survives. The caller then regenerates fragments and
pins, re-cuts contract pins, runs ``tools/check_registry_counts.py`` and fixes the prose count sites it
names, and runs the gates. Owner tooling: never shipped.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def hunk_union(text: str) -> Tuple[str, int]:
    """Replace every conflict hunk with OURS followed by the THEIRS lines OURS lacks.

    A hunk whose two sides differ only in digits is a count or a version: keep OURS and let the
    count re-set fix the number."""
    def fix(m: re.Match) -> str:
        a = m.group(1).splitlines(keepends=True)
        b = m.group(2).splitlines(keepends=True)
        if len(a) == len(b) and all(re.sub(r"\d", "", x) == re.sub(r"\d", "", y) for x, y in zip(a, b)):
            return "".join(a)
        out = list(a)
        for line in b:
            if line not in out:
                out.append(line)
        return "".join(out)
    return re.subn(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", fix, text, flags=re.S)


def collapse_dupes(text: str) -> str:
    out: List[str] = []
    for line in text.splitlines(keepends=True):
        if out and line.strip() and line == out[-1]:
            continue
        out.append(line)
    return "".join(out)


def union_surface_games(text: str) -> Tuple[str, int]:
    """Per ``SURFACE_GAMES["key"]`` key, keep one line whose right-hand side is the union of every
    variant's ``' + '`` terms in first-seen order. Returns the text and how many lines were folded."""
    lines = text.splitlines(keepends=True)
    first: Dict[str, int] = {}
    terms: Dict[str, List[str]] = {}
    drop = set()
    for i, line in enumerate(lines):
        m = re.match(r'(SURFACE_GAMES\["(\w+)"\]\s*=\s*)(.*?)\s*$', line)
        if not m:
            continue
        key = m.group(2)
        parts = [x.strip() for x in m.group(3).split(" + ")]
        if key not in first:
            first[key] = i
            terms[key] = []
        else:
            drop.add(i)
        for x in parts:
            if x not in terms[key]:
                terms[key].append(x)
    for key, i in first.items():
        head = re.match(r'(SURFACE_GAMES\["\w+"\]\s*=\s*)', lines[i]).group(1)
        lines[i] = head + " + ".join(terms[key]) + "\n"
    return "".join(l for i, l in enumerate(lines) if i not in drop), len(drop)


def rid(r: dict) -> str:
    return r.get("id") or r.get("capability_id")


def merge_registry(base: dict, ours: dict, theirs: dict) -> dict:
    b = {rid(r): r for r in base["capabilities"]}
    o = {rid(r): r for r in ours["capabilities"]}
    theirs_ids = {rid(r) for r in theirs["capabilities"]}
    for r in theirs["capabilities"]:
        k = rid(r)
        if k not in b or r != b[k]:          # added or changed by theirs
            o[k] = r
    for k in list(o):                        # removed by theirs
        if k in b and k not in theirs_ids:
            o.pop(k)
    merged = dict(ours)
    merged["capabilities"] = sorted(o.values(), key=rid)
    for kind in ("games", "surfaces"):
        bl, ol, tl = base.get(kind, []), ours.get(kind, []), theirs.get(kind, [])
        key = (lambda x: x["id"]) if (tl and isinstance(tl[0], dict)) else (lambda x: x)
        have = {key(x): x for x in ol}
        bk = {key(x) for x in bl}
        for x in tl:
            if key(x) not in bk or x not in bl:
                have[key(x)] = x
        merged[kind] = sorted(have.values(), key=key) if kind == "games" else list(have.values())
    return merged


def merge_game_json(base: dict, ours: dict, theirs: dict) -> dict:
    out = dict(ours)
    mods = list(base.get("product_modules", []))
    for side in (ours, theirs):
        for m in side.get("product_modules", []):
            if m not in mods:
                mods.append(m)
    out["product_modules"] = mods
    notes = dict(base.get("page_notes", {}))
    for side in (ours, theirs):
        for k in list(notes):
            if k not in side.get("page_notes", {}):
                notes.pop(k, None)
        for k, v in side.get("page_notes", {}).items():
            if k in notes and v != base.get("page_notes", {}).get(k):
                notes[k] = v
    out["page_notes"] = notes
    for k, v in theirs.items():
        if k not in ("product_modules", "page_notes") and v != base.get(k) and ours.get(k) == base.get(k):
            out[k] = v
    return out


def merge_allowlist(text: str) -> Tuple[str, str]:
    out: List[str] = []
    side = None
    for l in text.split("\n"):
        if l.startswith("<<<<<<< "):
            side = "ours"; continue
        if l.startswith("=======") and side == "ours":
            side = "theirs"; continue
        if l.startswith(">>>>>>> "):
            side = None; continue
        out.append(l)
    seen: set = set(); final: List[str] = []; dropped = 0
    for l in out:
        k = l.strip()
        if k and not k.startswith("#"):
            if k in seen:
                dropped += 1; continue
            seen.add(k)
        final.append(l)
    return f"entries={len(seen)} dropped={dropped}", "\n".join(final)


def deferred_ids(rows: List[dict]) -> List[str]:
    """The rule ``validate_all`` and ``tools/check_registry_counts.py`` use: deferred = names no validator."""
    return [rid(r) for r in rows if not r.get("validation_command")]


def main(root: Path) -> int:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True).stdout

    def stage(n: int, path: str) -> str:
        return git("show", f":{n}:{path}")

    unmerged = [p for p in git("diff", "--name-only", "--diff-filter=U").splitlines() if p]
    if not unmerged:
        print("nothing unmerged")
        return 0
    for rel in unmerged:
        p = root / rel
        name = p.name
        if name == "registry.v1.json":
            merged = merge_registry(*(json.loads(stage(n, rel)) for n in (1, 2, 3)))
            p.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            note = f"rows={len(merged['capabilities'])}"
        elif name == "game.json":
            merged = merge_game_json(*(json.loads(stage(n, rel)) for n in (1, 2, 3)))
            p.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            note = f"modules={len(merged['product_modules'])} notes={sorted(merged['page_notes'])}"
        elif name in ("pins.json", "registry.fragment.json", "CONTRACT_PINS.json"):
            p.write_text(stage(3, rel), encoding="utf-8"); note = "theirs (regenerate)"
        elif name.endswith("allowlist.txt") or name == "allowlist.fragment.txt":
            note, text = merge_allowlist(p.read_text(encoding="utf-8")); p.write_text(text, encoding="utf-8")
        elif name == "validate_all_mod_editor_capabilities.py":
            p.write_text(stage(3, rel), encoding="utf-8"); note = "theirs (counts recomputed below)"
        else:
            text, k = hunk_union(p.read_text(encoding="utf-8")); text = collapse_dupes(text); note = f"hunk union x{k}"
            if name == "validate_registry.py":
                text, folded = union_surface_games(text); note += f", {folded} coverage line(s) unioned"
            if name.startswith("check_") and name.endswith("_runtime.py"):
                lines = text.splitlines(keepends=True); out = []; seen_summary = False; drop_next = False
                for l in lines:
                    if "len(registry.capabilities) ==" in l and out and "len(registry.capabilities) ==" in out[-1]:
                        continue
                    if drop_next and l.strip().startswith('"reports='):
                        drop_next = False; continue
                    drop_next = False
                    if re.match(r'\s*"registry=\d+ sections=', l):
                        if seen_summary:
                            drop_next = True; continue
                        seen_summary = True
                    out.append(l)
                text = "".join(out)
            p.write_text(text, encoding="utf-8")
        print(f"  {rel}: {note}")

    reg = json.loads((root / "mod_editor/capabilities/registry.v1.json").read_text(encoding="utf-8"))
    rows = reg["capabilities"]; n = len(rows); deferred = deferred_ids(rows)
    validators = len({r.get("validation_command") for r in rows if r.get("validation_command")})
    va = root / "tools/validate_all_mod_editor_capabilities.py"; t = va.read_text(encoding="utf-8")
    for name, val in (("EXPECTED_CAPABILITIES", n), ("EXPECTED_COVERED_CAPABILITIES", n - len(deferred)),
                      ("EXPECTED_DEFERRED_CAPABILITIES", len(deferred)), ("EXPECTED_UNIQUE_VALIDATORS", validators)):
        t = re.sub(rf"^{name}\s*=\s*\d+", f"{name} = {val}", t, flags=re.M)
    m = re.search(r"EXPECTED_DEFERRED_IDS = \((.*?)\n\)", t, flags=re.S)
    if m:
        t = t[:m.start()] + "EXPECTED_DEFERRED_IDS = (\n" + "".join(f'    "{i}",\n' for i in deferred) + ")" + t[m.end():]
    va.write_text(t, encoding="utf-8")
    for chk in ("packaging/check_2k5_mod_studio_runtime.py", "packaging/check_apf2k8_mod_studio_runtime.py"):
        c = root / chk
        if not c.is_file():
            continue
        ct = c.read_text(encoding="utf-8")
        ct = re.sub(r"len\(registry\.capabilities\)\s*==\s*\d+", f"len(registry.capabilities) == {n}", ct)
        ct = re.sub(r"registry=\d+ sections=", f"registry={n} sections=", ct)
        c.write_text(ct, encoding="utf-8")
    print(f"  counts: rows={n} covered={n - len(deferred)} deferred={len(deferred)} validators={validators}")
    left = [rel for rel in unmerged if "<<<<<<<" in (root / rel).read_text(encoding="utf-8", errors="replace")]
    if left:
        print("  MARKERS SURVIVE:", left)
        return 1
    print("  resolved", len(unmerged), "file(s); now: fragments --write per game, pins --write, check_registry_counts.py, gates")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.splitlines()[2]); sys.exit(2)
    sys.exit(main(Path(sys.argv[1]).resolve()))
