#!/usr/bin/env python3
"""Pre-push pin audit for a 2k-football-mod-tools worktree.

Usage: python3 pin_audit.py <worktree>

Checks the three things that have actually broken CI on this lane:
  1. every dict-shaped sha256 pin in BOTH runtime checkers matches the file
     it pins (require() stops at the first mismatch, so we list them all);
  2. the capability-count literals agree with the registry as it stands
     (row count in both checkers, EXPECTED_* in validate_all);
  3. validate_registry.py passes the way CI invokes it (--skip-file-checks).
Exit 0 only if all three hold.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
bad = 0

# --- 1. dict-shaped sha256 pins -------------------------------------------
for checker in ("packaging/check_2k5_mod_studio_runtime.py",
                "packaging/check_apf2k8_mod_studio_runtime.py"):
    src = (root / checker).read_text(encoding="utf-8")
    pins = re.findall(r'"([^"]+\.\w+)"\s*:\s*\n?\s*"([0-9a-f]{64})"', src)
    mism = []
    for rel, pinned in pins:
        p = root / rel
        cur = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"
        if cur != pinned:
            mism.append((rel, pinned[:12], cur[:12]))
    print(f"[pins] {checker.split('/')[-1]}: {len(pins)} pins, {len(mism)} mismatch")
    for rel, old, new in mism:
        print(f"       ✗ {rel}  pinned {old}…  current {new}…")
    bad += len(mism)

# --- 2. count literals vs the registry ------------------------------------
reg = json.loads((root / "mod_editor/capabilities/registry.v1.json").read_text(encoding="utf-8"))
rows = reg["capabilities"]
n_rows = len(rows)
# Same rule validate_all_mod_editor_capabilities.py / tools/check_registry_counts.py use:
# a row is deferred when it names NO validator (classification alone drifted: 106+5 != 112).
n_deferred = sum(1 for r in rows if not r.get("validation_command"))
n_covered = n_rows - n_deferred
n_validators = len({r.get("validation_command") for r in rows if r.get("validation_command")})
print(f"[registry] rows={n_rows} deferred={n_deferred} covered={n_covered} unique_validators={n_validators}")

def lit(path: str, pattern: str) -> list[str]:
    return re.findall(pattern, (root / path).read_text(encoding="utf-8"))

for checker in ("packaging/check_2k5_mod_studio_runtime.py",
                "packaging/check_apf2k8_mod_studio_runtime.py"):
    for v in lit(checker, r"len\(registry\.capabilities\)\s*==\s*(\d+)"):
        ok = int(v) == n_rows
        bad += 0 if ok else 1
        print(f"[count] {checker.split('/')[-1]}: len(registry.capabilities) == {v}  {'ok' if ok else '✗ expected '+str(n_rows)}")

va = "tools/validate_all_mod_editor_capabilities.py"
for name, want in (("EXPECTED_CAPABILITIES", n_rows),
                   ("EXPECTED_COVERED_CAPABILITIES", n_covered),
                   ("EXPECTED_UNIQUE_VALIDATORS", n_validators)):
    vals = lit(va, rf"{name}\s*=\s*(\d+)")
    for v in vals:
        ok = int(v) == want
        bad += 0 if ok else 1
        print(f"[count] {name} = {v}  {'ok' if ok else '✗ registry implies '+str(want)}")
    if not vals:
        print(f"[count] {name}: not found")

# --- 2b. allowlist duplicate lines (fatal in stage_release.py) -------------
for al in ("packaging/release-allowlist.txt", "packaging/apf2k8-release-allowlist.txt"):
    lines = [l.strip() for l in (root / al).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    dups = sorted({l for l in lines if lines.count(l) > 1})
    print(f"[allowlist] {al.split('/')[-1]}: {len(lines)} entries, {len(dups)} duplicate")
    for d in dups:
        print(f"       ✗ duplicate: {d}")
    bad += len(dups)

# --- 2c. ALLOWLISTED launcher scripts must carry the executable bit in the INDEX
# check_2k5_mod_studio_release.py:564 refuses "launcher script is not executable"
# for a staged *.sh whose st_mode lacks S_IXUSR; on the Linux runner the mode
# comes from the git index (core.fileMode=false here, so chmod alone is lost --
# use `git update-index --chmod=+x`). Only allowlisted files are staged, which
# is why ~30 legacy 100644 .sh files outside the 2K5 allowlist never tripped it.
# Bit WP4's launcher on 2026-09-05.
ls = subprocess.run(["git", "ls-files", "-s", "--", "*.sh"], cwd=root, capture_output=True, text=True).stdout
mode_of = {l.split("\t", 1)[1]: l.split()[0] for l in ls.splitlines() if l}
al_lines = [l.strip() for l in (root / "packaging/release-allowlist.txt").read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]
exact = {l for l in al_lines if not l.endswith("/")}
prefixes = tuple(l for l in al_lines if l.endswith("/"))
staged_sh = [p for p in mode_of if p in exact or p.startswith(prefixes)]
nonexec = [p for p in staged_sh if mode_of[p] != "100755"]
print(f"[exec-bit] allowlisted .sh: {len(staged_sh)}, non-executable in index: {len(nonexec)}")
for p in nonexec:
    print(f"       ✗ {p}  (git update-index --chmod=+x)")
bad += len(nonexec)

# --- 2d. the registry-shape unit tests CI runs (bit 6912de2: test_ps2_lane pinned
#         "every PS2 writer is the exposed save writer"; fast, so run them here) ----
t = subprocess.run([sys.executable, "-m", "unittest", "-q",
                    "tests.mod_editor.test_ps2_lane", "tests.mod_editor.test_beta45_honesty_freeze"],
                   cwd=root, capture_output=True, text=True, env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
tl = (t.stderr.strip().splitlines() or ["(no output)"])[-1]
print(f"[unit] test_ps2_lane + honesty_freeze: rc={t.returncode}: {tl[:120]}")
bad += 0 if t.returncode == 0 else 1

# --- 3. registry validator as CI runs it ----------------------------------
r = subprocess.run([sys.executable, "mod_editor/capabilities/validate_registry.py", "--skip-file-checks"],
                   cwd=root, capture_output=True, text=True)
last = (r.stdout.strip().splitlines() or r.stderr.strip().splitlines() or ["(no output)"])[-1]
print(f"[validate] rc={r.returncode}: {last[:160]}")
bad += 0 if r.returncode == 0 else 1

print("PIN AUDIT:", "CLEAN" if bad == 0 else f"{bad} PROBLEM(S)")
sys.exit(1 if bad else 0)
