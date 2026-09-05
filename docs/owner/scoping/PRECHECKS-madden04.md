# Pre-checks — Madden NFL 2004 (PS2, SLUS-20752)

Ordered, **read-only** checks with exact commands and expected results, so a later
agent can reproduce or extend this study without re-deriving anything.

Two sections:

- **§A — agent-doable.** Read-only, no rig, no emulator, no repo writes. P1–P10.
- **§H — human-required.** Cannot be done by an agent at all. H1–H4.

---

## 0. Environment

```bash
LANE=/tmp/claude-1000/-mnt-c-GitHub-NCAA-Draft-Class-Editor/fd4470c7-7f37-4a40-88e2-054f7c50a442/scratchpad/ps2-lane
VENV=/tmp/claude-1000/-mnt-c-GitHub-NCAA-Draft-Class-Editor/fd4470c7-7f37-4a40-88e2-054f7c50a442/scratchpad/venv311
ISO="/mnt/c/Roms/PS2/Madden NFL 2004 (USA).iso"
PY="$VENV/bin/python"                       # Python 3.11.13, has Pillow
export PYTHONPATH="$LANE:$LANE/tools"
cd "$LANE"
```

**Two environment traps, both hit during this study:**

1. **The system `python3` is 3.9 and cannot import `mod_editor`** — `mod_editor/core/model.py`
   does `from datetime import UTC`, which is 3.11+. Use `$PY`.
2. **`mod_editor` imports Pillow**, which is *not* in the system site-packages but
   *is* in `venv311`. `tools/ps2_iso9660.py` is standalone and works anywhere;
   `tools/ea_terf_inspect.py` and anything under `mod_editor.games` need `$PY`.

Also note `tools/ea_terf_inspect.py --extract` uses `write_bytes` and **will silently
overwrite `--out`**, unlike `ps2_iso9660.py --extract` which refuses an existing file.

---

# §A — agent-doable, read-only

## P1 — Image and boot identity  ✅ done

```bash
$PY tools/ps2_iso9660.py --inspect "$ISO" --json > m04.inspect.json
sha256sum "$ISO"                      # ~3 GB read, a few minutes
```

**Expected** (all measured 2026-09-05):

```
serial            SLUS-20752
boot_file         SLUS_207.52
volume_id         MADDEN04
boot_sha256       5cb956b62a32a9aeed804c94efdc9a5da6f24ef9eb5b57d7bd8d6116170bd36c
boot_size         5354036
file_size         3207397376
slack_bytes       0
sector_size       2048        data_offset 0
directories 6     files 124   declared_file_bytes 3206411063
ISO sha256        b6488caf903920cddd25a9c74e1d2963b505ae302bc2faed9dfa1a0bffadccc5
```

**Fail signal:** a different `boot_sha256` means a different rip; **stop** and re-scope
§5 (the pnach library is keyed to an ELF, not to an image).

## P2 — PCSX2 ELF CRC  ✅ done

```bash
$PY -m mod_editor.games.nfl2k5_ps2.code_patches --crc "$ISO"
```

**Expected:** `"pcsx2_crc": "14F8B841"`, `"serial": "SLUS-20752"`.

Ignore `"retail": false` — that flag is evaluated against the **2K5** module's own
allow-list, not against Madden. It becomes meaningful only once a Madden 04 module
declares its own `executable_sha256`.

Platform-independent equivalent, for a bare ELF with no module:

```bash
$PY -c "import sys;from mod_editor.games._formats import ps2_elf; \
print(ps2_elf.pcsx2_crc(open(sys.argv[1],'rb').read()))" SLUS_207.52
```

**Cross-check:** `grep -c . /mnt/c/GitHub/nfl-online-revival/patches/14F8B841.*` — 34
files carry this CRC. **[S]** `nfl-online-revival/docs/binary-identity.md:91` records
the same value *and* the zlib CRC-32 `CFABB64D`; do not confuse them.

## P3 — Container inventory  ✅ done

```bash
for p in DB_TEAMS TEMPLATE GAMEDATA STADIUMS FIELDART PLADATA COACHES PLYRFACE \
         COACFACE ANIMDATA STADATA LOADDATA ONLINE FACEGEOM SPCHHDRS; do
  $PY tools/ea_terf_inspect.py --iso "$ISO" --path /DATA/$p.DAT --json --limit 0 \
      > terf/$p.json || echo "FAIL $p"
done
# ...and every UIS_*.DAT the same way (36 of them)
```

**Expected, aggregated over 51 containers:**

```
members            14,981
layout violations       0        ← the load-bearing number
codecs             stored 11,700 | LZH1 3,281 | unknown 0
formats            MMAP 8,255 | unclassified 4,634 | SMF 1,190 | empty 319
                   TDB 308 | DMF 221 | TERF 28 | SKL1 10 | FNTS 9
                   TEXT 3 | SEVT 2 | MPCh 1 | ELF 1
version word       02020005 in all 51
```

**This must match `docs/product/EA_TERF_FORMAT.md` §8's "Madden NFL 2004" row exactly**
(`51 | 14,981 | 11,700 | 3,281 | 0 | 0 | 0`). It did. If it ever does not, the disc or
the reader changed.

The four containers over the 96 MB guard need `--allow-large`, or header-probe them:
`MOVIEDAT` (116 members), `SPCHDATA` (7,659), `SOUNDDAT` (447), `UIS_FMV` (128).

## P4 — TDB substrate proof  ✅ done

```bash
$PY tools/ea_terf_inspect.py --iso "$ISO" --path /DATA/TEMPLATE.DAT \
    --extract 0 --out /tmp/m04_template_0.bin
$PY /mnt/c/GitHub/NCAA-Draft-Class-Editor/tools/parse_madden_tdb.py \
    /tmp/m04_template_0.bin /tmp/m04_template_0.json
rm -f /tmp/m04_template_0.bin        # delete the payload
```

**Expected** — an *unmodified* Madden-08-era parser reading a Madden 2004 disc member:

```
magic 'DB'  version 2048 (0x0800)  dbSize 253044  tableCount 4  preambleBytes 0
DCHT 1887/2912    8 B / 63 bits    4 fields
INJY    1/320     8 B / 63 bits    5 fields
PLAY 1990/2048  108 B / 863 bits  112 fields
TEAM   33/33     88 B / 703 bits   59 fields
```

**Control** (proves the parser, not the disc):

```bash
$PY /mnt/c/GitHub/NCAA-Draft-Class-Editor/tools/parse_madden_tdb.py \
    /mnt/c/GitHub/NCAA-Draft-Class-Editor/tests/fixtures/madden08-roster-sample.bin /tmp/ctl.json
```
→ same header shape; `DCHT` and `INJY` **identical field-for-field** to Madden 2004.

**Expected drift** (Madden 04 vs Madden 08): `PLAY` 112 vs 110 fields, 104 shared, 96
of those identically sized; `TEAM` 58 vs 66, 57 shared, 56 identically sized;
`DCHT`/`INJY` 100 % identical. Bit *offsets* shift freely — irrelevant to a
metadata-driven reader.

## P5 — Roster / coach / uniform census  ✅ done

Walk all 232 `DB_TEAMS.DAT` members; for each read the `TEAM` table's first record.

**Expected:**

```
232 members, all TDB, all codec 0 (stored), 0 layout violations
member   0        Free Agents (FA)            247 players
members  1..32    the 32 NFL teams, TGID 1..32 alphabetical by mascot
                  Bears(1) … Vikings(32),      53-55 players, 4 coaches each
members 33..231   199 classic teams: '02 Bucs', '01 Rams', '99 Titans', …
total PLAY 11,527   (1,743 across TGID 1..32)   total COCH 128
tables in all 232 : PLAY, TUNI, TEAM     (DCHT in 231)
tables in 33      : INJY PCDE PCKI PCKP PCNG PCOF PCOL PSDE PSKI PSKP PSNG PSOF PSOL
tables in 32      : CPSE COCH OCIS OTGO OTRS
```

Spot-check member 1 = `TDNA 'Bears' / TLNA 'Chicago' / TSNA 'CHI'`, coaches
`D.Jauron (CHTY=1)`, `J.Shoop`, `G.Blache`, `M.Sweatman`, and Brad Maynard P #4 OVR 95.

**[S]** Cross-check against `nfl-online-revival/docs/xbox-data-layer.md:128-136`:
`DB_TEAMS.DAT` 8,439,360 B, 232 members, **1,743 players teams 1–32**. All three agree.

## P6 — ⚠ The `QL01` duplication check  **NOT DONE — do this before any writer**

**[S]** `docs/product/EA_TERF_FORMAT.md` warns that `GAME.QKL` / `FE.QKL` carry
byte-identical **packed** copies of members *and* directories, so *"an edit must be
applied in both places."* **[M]** Madden 04 has both (`FE.QKL` 9,672,716 B,
`GAME.QKL` 6,947,672 B, magic `QL01`, a `FILS` chunk naming `animdata.dat` …).

```bash
# extract both, then search each for a member digest known to live in a /DATA container
$PY tools/ps2_iso9660.py --image "$ISO" --extract /DATA/GAME.QKL --output /tmp/GAME.QKL
$PY tools/ps2_iso9660.py --image "$ISO" --extract /DATA/FE.QKL   --output /tmp/FE.QKL
# then: parse the QL01 FILS table; for each named .dat, check whether the QKL holds a
# byte-identical copy of that container's members
rm -f /tmp/GAME.QKL /tmp/FE.QKL
```

**Why it matters:** if `DB_TEAMS.DAT` is duplicated inside a `.QKL`, a roster write to
`/DATA/DB_TEAMS.DAT` alone will appear to succeed and change nothing in-game. **This
is the single most important unrun check in the study.**

**Pass:** `DB_TEAMS.DAT` is *not* mirrored in either QKL → roster writes need one write.
**Fail:** it is mirrored → every roster write needs two, and both must stay same-size.

## P7 — `TUNI.UFID` → MMAP member mapping  **NOT DONE**

Decides whether the Uniforms page is real (§4.2 of the scoping doc).

```bash
# UFIDs observed on member 1 (Bears): 2, 3, 199, 224 with TUCO 1,0,2,3
# UIS_PLYR.DAT holds 2,124 stored MMAP members, 2,123 of them 96x96
```

Test the hypothesis that `UFID` indexes into `UIS_PLYR.DAT` (or `PLADATA.DAT`) by
pulling the four Bears `UFID`s and four from a visually distinctive team, decoding the
MMAP surface tables, and checking the palettes differ in the expected team colours.

**Pass:** a stable `UFID → member` relation → Uniforms page reaches `read-only-mapped`
immediately and `offline-writer-proved` for *assignment* soon after.
**Fail:** uniform art is indexed some other way → keep Uniforms as an empty page and
say so in `page_notes`.

## P8 — MMAP header sanity  ✅ done

```bash
# parse_mmap_header over every member of the art containers
```

**Expected:** 5,776 headers parsed, **0 failures**; `version` 2 in 4,280 and 1 in 1,496
(all of `UIS_MCFL`); dimensions 96×96 (2,123), 128×128 (1,616), 480×320 (748),
112×80 (748), 64×32 (289), 64×64 (244), 1024×256 (4).

**Do not go further than the header.** **[S]** `EA_TERF_FORMAT.md:293`: *"Pixel format,
palette presence and mip count are not determined, and are deliberately not guessed."*
Before attempting pixels, check whether `rc87-madden09/mod_editor/games/madden09_ps2/mmap_art.py`
has landed — it reframes MMAP as a table-of-tables and would supersede this.

## P9 — Writer preconditions  ✅ done

```bash
$PY tools/ps2_iso9660_writer.py --inspect "$ISO"
```

**Expected:** `writable_geometry: true`, `slack_bytes: 0`, `sector_size: 2048`.
Plus, from P1's entry list: **0 aliased extents** (no two directory records share an
`lba`) — the writer refuses aliased extents, and Madden 04 has none.

**Note** the duplicated `.IRX` modules between `/SYSTEM` and `/NETGUI/MODULES` are
*separate extents with identical content*, not aliases. Confirmed.

## P10 — Playbook census  ✅ done

```bash
# walk GAMEDATA.DAT's 64 TDB members, tally tables and rows
```

**Expected:** 64 TDB members, 19 tables each. Row totals: `PLYS` 110,660, `PSAL`
62,033, `PBAI` 36,531, `SETG` 24,677, `ARTL` 14,615, `SETP` 13,695, `PBPL` 10,066,
`PLYL` 10,060, then `SGF` 6,793, `PLCM` 5,977, `SPKG` 5,846, `PLPD` 5,419, `SPKF`
3,223, `PLRD` 2,870, `PBST` 1,291, `SETL` 1,245, `PBAU` 902, `FORM` 624, `PBFM` 579.

**[S]** Cross-check: `nfl-online-revival/docs/xbox-data-layer.md:271-288` gives `PBAI`
36,531 and `PLYL` 10,060 for the same file. Exact match.

---

# §H — human-required

These cannot be delegated to an agent under any circumstances. They need a person, a
controller, and in three cases the rig.

## H1 — GS texture dump for PCSX2 replacement identity  **blocking the art lanes**

**Why a human:** PCSX2 names replacement PNGs by a hash it computes at *draw time*.
Those hashes exist only while the game is running. No static analysis of the disc
produces them.

**What to do:** boot `SLUS-20752` in PCSX2, enable texture dumping
(`textures/SLUS-20752/dumps`), and walk the screens that matter — team select, the
uniform screen, a kickoff, a coach portrait, the roster list. Then hand back the dump
directory listing (filenames only; the PNGs stay local).

**What it unlocks:** the mapping MMAP member → PCSX2 hash, which is what turns the
Textures/Uniforms pages from an inventory into an export pipeline. **[S]** This is
exactly the route the community uses (`antdroidx/Madden05NEXT` for the adjacent year),
*because* on-disc MMAP writing is unsolved.

**Rig safety:** the rig shares one VR headset across three emulators. Before any
emulator action, run the live-session check as its own command and read the result;
any hit means stop and ask. Never chain a launch behind the check.

## H2 — In-game witness for any writer  **blocking `runtime-proved`**

**Why a human:** **[S]** the registry requires `runtime.status == "visible-proved"`
with evidence files that exist on disk, and `EA_TERF_FORMAT.md` states the boot test
*"needs the rig."* An agent can produce a byte-exact modified ISO and a verifier
report; it cannot produce the observation.

**Minimum witness for the roster lane:** change one player's name in `DB_TEAMS.DAT`
member 1, rebuild the ISO through the fixed-allocation writer, boot, open the Bears
roster, photograph the changed name.

**Until then** every writer lane caps at `offline-writer-proved`, which is a legitimate
rung and the right thing to ship.

## H3 — Confirm the roster checksum applies to disc rosters

**Why a human:** **[S]** `nfl-online-revival/docs/roster-checksum.md` documents the
algorithm (zlib CRC-32 over the 1,743 `PLAY` rows where `TGID` 1..32 ordered by
`PGID`, seeded with the row count, value `0x8108963c`) for rosters delivered over the
network. Whether the game *also* verifies a roster it loaded off its own disc can only
be settled by editing one and booting.

**Cheap version of H2:** if the edited-name disc from H2 boots and shows the change,
the disc path is unchecked or the checksum was recomputed correctly — either way the
lane is viable.

## H4 — One question to the modding community  **not blocking, but high value**

Ask antdroid / the NCAA-Madden NEXT Discord: **was Madden NFL 2004 PS2 skipped, or
just never attempted?** He authored this repo's upstream and ships `Madden05NEXT`
(SLUS-21000) and `madden08next` — 2004 is the conspicuous gap in his lineup. Five
minutes of his time replaces days of speculation about the art lane.

---

## Summary

| Check | Status | Blocks |
|---|---|---|
| P1 image + boot identity | ✅ done | — |
| P2 ELF CRC = `14F8B841` | ✅ done | — |
| P3 container inventory, 0 violations | ✅ done | — |
| P4 TDB v8 substrate proof | ✅ done | — |
| P5 roster/coach/uniform census | ✅ done | — |
| **P6 `QL01` duplication** | ❌ **not done** | **every disc writer** |
| **P7 `TUNI.UFID` → MMAP** | ❌ not done | the Uniforms page |
| P8 MMAP headers | ✅ done | — |
| P9 writer preconditions | ✅ done | — |
| P10 playbook census | ✅ done | — |
| H1 GS dump | 👤 human | art export lanes |
| H2 in-game witness | 👤 human | `runtime-proved` |
| H3 checksum applies? | 👤 human | roster writer confidence |
| H4 community question | 👤 human | nothing; de-risks the art lane |
