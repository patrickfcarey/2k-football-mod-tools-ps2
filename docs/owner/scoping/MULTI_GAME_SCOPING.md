# Adding further PS2 games as game modules — scoping study

> Written 2026-09-05 against the `ps2-lane` worktree (the PR-27 head) and the two machines.
> **Scoping only. Nothing was built, no repository was touched, no image was written or
> downloaded.** Companion documents: `PRECHECKS.md` (the ordered pre-flight checklist),
> `iso_inventory.json` (the machine-readable inventory).
>
> **Evidence tags, used on every load-bearing claim:**
> **[M]** measured — I ran a read-only command and saw the result this session.
> **[S]** sourced — a URL, named inline or in `research_ea_ps2.md`.
> **[A]** assumed — inference, not verified. Treat as a question, not a fact.

---

## 1. What this study answers

The owner wants more PS2 games hosted on SOFTDRINKTV's 2K5 Mod Studio fork as **game modules**
on the `vc_game_module/v1` contract. The contract, discovery, registry merge, conformance
harness, chooser, scaffold and the shared `_formats/ps2_disc` + `_formats/ps2_elf` packages
already exist and ship; `nfl2k5_ps2` is the only module so far, carrying 10 registry rows
across 10 surfaces [M].

This study says, per candidate game: what its disc is, whether we have it, who mods it and
with what, which of our lanes carry over unchanged, which need new format work, what the
smallest honest module looks like, what has to be measured before a line is written, where a
human is unavoidable, and what it costs.

## 2. Headline findings

1. **We do not own three of the four games in scope.** ESPN NBA 2K5, MVP Baseball 2005 and
   NCAA Football 06/07/08 are **absent from the dev box, the rig and the NAS** [M]. Madden
   (04/06/08/09/12, stock and Deluxe) and NCAA Football 2004/09 are present with **measured**
   serials. Everything basketball- and baseball-shaped in this study is currently unmeasurable.
2. **The EA on-disc container is much less unknown than the interfaces plan assumed.** The plan
   files Madden/NCAA on-disc `/DATA/*.DAT` "TERF" as *"PARTIAL → UNKNOWN, no public spec"*.
   In this survey I opened three of those files read-only and got most of the way through the
   container in minutes, and — the important part — **the payloads are EA TDB, the format this
   ecosystem already reads and writes byte-exactly** (§4.2). One of them,
   `/DATA/TEMPLATE.DAT` on Madden 08 PS2, contains a TDB whose `dbSize` and table set are
   **identical to the memory-card roster save** the sibling repo already compiles [M].
3. **The Madden/NCAA family is one parameterisation, not four ports.** Madden 08, Madden 12 and
   NCAA Football 09 PS2 discs share the same root layout, the same `/DATA` naming convention,
   the same `TERF`/`DIR1` container and the same bare-TDB `STRMDATA.DB` [M].
4. **Every new game needs its own human at the controls, once.** There are **122 GS dumps for
   `SLUS-20919` and zero for any Madden, NCAA, NBA or MVP title** on the rig [M]. No
   emulator-side (texture-pack) claim can reach `runtime-proved` for a new game without a
   human booting it and capturing a dump.
5. **The upstream author of our sibling repo already ships an NCAA Football TDB save editor.**
   `antdroidx/NCAA-DB-Editor` — "DB/Save Editor for NCAA Football series on PS2/Xbox/PSP/GC",
   descended from Madden Xtreme DB Editor + MaddenAMP + `tdbaccess` [S]. The Madden-PS2 and
   NCAA-PS2 community tool lineages share code ancestry [S]. We are not entering an empty room,
   and we are not entering a hostile one either.
6. **MVP's flagship hub went offline permanently around April 2026** [S]. The surviving MVP
   scene (`mvp2kcaribe.com`) is a **PC** conversion community, and its own texture tool cannot
   open console files. This moves MVP from "low priority" to "do not schedule" (§6.2).
7. **I agree with the interfaces plan's recommendation, with one change.** Madden 08 PS2
   (rosters + draft classes) first — the reasons are stronger than the plan states. But I would
   promote **NCAA Football 06 PS2** over NBA 2K5 for second place, and I would run the NBA 2K5
   *measurement* early and cheaply anyway because it is two commands once the disc exists (§10).

---

## 3. The machines — what is actually here

Full listing: `iso_inventory.json` (376 files across both hosts). Method: read-only `find`;
serials read from each image's ISO9660 root `SYSTEM.CNF` `BOOT2` line with
`scoping/probe_serial.py`, which opens the file read-only and reads a handful of 2048-byte
sectors. No image was copied.

### 3.1 Capacity

| host | free | note |
|---|---|---|
| dev box `/mnt/c` | **50 GiB of 953 GiB (95% used)** [M] | C: filling to 32 MB free crashed WSL three times on 2026-09-05. **Never write images here.** |
| rig `/home` | **1.4 TiB of 1.8 TiB (23% used)** [M] | all image work goes here, detached |
| NAS `/mnt/Z_Share/roms` | — | contains one directory, `_loadout_scratch`; **no game images** [M] |

No emulator was running on the rig at survey time (`pgrep -x pcsx2-qt` / `mupen64plus` /
`[q]emu-system-i386` all empty) [M].

### 3.2 PS2 discs we hold, with measured serials

| Title | Serial [M] | dev box | rig | size |
|---|---|---|---|---|
| ESPN NFL 2K5 (USA) | `SLUS-20919` | ✅ | ✅ ×3 | 4.34 GiB |
| Madden NFL 08 (USA) | `SLUS-21638` | ✅ | ✅ | 1.77 GiB |
| Madden NFL 09 (USA) | `SLUS-21770` | ✅ | ✅ | 1.54 GiB |
| Madden NFL 09 Deluxe | `SLUS-21770` | ✅ | — | 1.72 GiB |
| Madden NFL 12 (USA) | `SLUS-21946` | ✅ | ✅ | 1.48 GiB |
| Madden NFL 12 Deluxe 2026 | `SLUS-21946` | ✅ | ✅ | 1.52 GiB |
| Madden NFL 06 (USA) | `SLUS-21213` | ✅ | ✅ | 3.16 GiB |
| Madden NFL 2004 (USA) | `SLUS-20752` | ✅ | ✅ ×3 | 2.99 GiB |
| NCAA Football 09 (USA) | `SLUS-21752` | ✅ | — | 2.03 GiB |
| NCAA Football 2004 (USA) | `SLUS-20719` | ✅ | — | 2.46 GiB |
| Madden NFL 2001 (USA) | not read (CD `.bin/.cue`) | ✅ | ✅ | 0.59 GiB |

**Not present anywhere: ESPN NBA 2K5, ESPN NHL 2K5, ESPN College Hoops 2K5, MVP Baseball 2005,
MVP 06 NCAA Baseball, NCAA Football 06 / 07 / 08** [M].

Note the Deluxe images carry the **stock serials** — `Madden NFL 09 Deluxe` reports
`SLUS-21770`, `Madden NFL 12 Deluxe 2026` reports `SLUS-21946` [M]. Identity by serial alone
cannot tell a Deluxe rebuild from a retail disc; the module must carry a second
`content_sha256` per accepted image, exactly as the PS2 lane already does for its
Deluxe-sourced templates.

### 3.3 Emulator state on the rig

| thing | measured |
|---|---|
| GS dumps by serial | `SLUS-20919` **122**; SCUS-97124/97198/97328/97436, SLES-52323, SLUS-20062/20090/20268/20318/20786/20851/20932 (8–45 each); **Madden / NCAA / NBA / MVP: zero** |
| PCSX2 texture trees | `SCUS-97124` (129,090 entries), SCUS-97198, SLUS-20062, SLUS-20090, SLUS-20786, `SLUS-20919` (92), SLUS-20932 |
| PenguinScreen2 texture trees | `SLUS-20919` only — and it is a **symlink** into `~/2k5-ps2-final/replacement-pack/...` |
| memory cards | PCSX2: `Madden09 2011/2015/2019/2023.ps2`, `Mcd001`, `Mcd002`, `NFL 2K27`, `NFL 2K27 TEST`; PenguinScreen2: `Mcd001`, `Mcd002`, `NFL 2K27` |
| PCSX2 game-list root | `RecursivePaths = /home/pacarey/Games/ps2` |

The four `Madden09 20xx.ps2` cards are the strongest signal in this table: **Madden 09 PS2
save work has already happened on this rig**, so the memory-card half of a Madden module has a
warm start.

---

## 4. What we measured about the EA on-disc formats

This is new material — the interfaces plan lists it as unknown. Everything here was read
read-only out of the ISOs we own, in this session.

### 4.1 The disc shape is one family

`/DATA/` on Madden 08 (110 files, 1.73 GiB) and NCAA Football 09 (90 files, 1.98 GiB) [M]:

```
Madden 08   SPCHMAD1 SPCHFEDT BGM SOUNDDAT SPCHMAD2 MOVIEDAT SPCHDATA STADIUMS
            UNIFORMS UIS_*.DAT FANDATA ANIMDATA PLYRFACE GAME.QKL COACHES
            FIELDART PLADATA STADATA DB_TEAMS TEMPLATE STRMDATA.DB FE.QKL …
NCAA FB 09  SPCHDATA SOUNDDAT MOVIEDAT STADIUMS UNIFORM  UIS_*.DAT FANDATA ANIMDATA
            GAME.QKL FLDDATA STADATA LEAGUE  TEMPLATE STRMDATA.DB FE.QKL PL.QKL …
```

Same convention, same `QKL` script blobs, same `STRMDATA.DB`, same `UIS_*` UI packs. A module
that reads Madden 08's disc reads NCAA Football 09's disc.

### 4.2 `TERF` / `DIR1` — most of the container, from three hexdumps

Every `/DATA/*.DAT` on Madden 08, Madden 12 and NCAA 09 begins `TERF` [M]. From
`Madden 08 /DATA/TEMPLATE.DAT`, `DB_TEAMS.DAT`, `GAMEDATA.DAT`, `PLADATA.DAT`, `STADATA.DAT`,
`COACHES.DAT`, `FIELDART.DAT`, `UNIFORMS.DAT` and `Madden 12 /DATA/DB_TEAMS.DAT`:

```
0x00  "TERF"  u32 0x40 (header size)  02 02 00 05  u16 0x0040  u16 memberCount
0x40  "DIR1"  u32 dirBytes            u32 0x40      u32 0
0x50  memberCount × (u32 offset, u32 size)      offsets 0x80-aligned, relative to 0x100
...   zero padding to dirBytes
0x100 "DATA"  u32 totalFileSize                  ← equals the file's own length
0x180 first member payload
```

Checks that hold across all nine files [M]: `dirBytes / 8` is the member count rounded up
(`TEMPLATE` 18 members / 0xC0 = 24 slots; `DB_TEAMS` 237 / 0x780 = 240; `GAMEDATA` 113 / 0x3C0
= 120; `PLADATA` 370 / 0xBC0 = 376; `STADATA` 263 / 0x840 = 264); `offset[n] + size[n]`
rounded up to 0x80 equals `offset[n+1]`; the `DATA` chunk's u32 equals the file size exactly.

**Still unknown [A]:** whether individual members can be compressed, whether any checksum
covers the container, and what the `02 02 00 05` word means. Those are the remaining hours of
work, not the remaining weeks. This is a **materially smaller risk** than
`MULTI_GAME_INTERFACES_PLAN.md` §3.1 currently records, and the plan's risk table should be
corrected.

### 4.3 The payloads are EA TDB — the format we already own

| file | what it is [M] |
|---|---|
| Madden 08 `/DATA/STRMDATA.DB` | **bare TDB**, `dbSize` 5,169,236 = the file size, **211 tables** (`EACD ERWD AGCM … cMON COCH COLL …`) |
| NCAA 09 `/DATA/STRMDATA.DB` | **bare TDB**, `dbSize` 2,008,284 = file size, **91 tables** (`ANIN ANMM ANPG … CAPT …`) |
| Madden 08 `/DATA/DB_TEAMS.DAT` | TERF holding a **sequence of 21-table TDBs** (`COCH DCHT INJY OCIS OTGO OTRS PCDE PCKI PCKP PCNG PCOF PCOL PLAY PSDE PSKI PSKP PSNG PSOF PSOL TUNI TEAM`), first at 0x800, ~22 KB each, 237 members — i.e. per-team databases including `TUNI` (team uniforms) |
| Madden 12 `/DATA/DB_TEAMS.DAT` | **the same 21 tables, same layout**, 235 members |
| **Madden 08 `/DATA/TEMPLATE.DAT`** | TERF whose member 0 at 0x180 is a TDB with **`dbSize` 245,856 and exactly 4 tables — `DCHT INJY PLAY TEAM`** |
| NCAA 09 `/DATA/TEMPLATE.DAT` | TERF whose member 0 is a **49-table TDB** (`BOWL COCH CONF CTCD CTUN DCHT … TEAM`) |

The `TEMPLATE.DAT` line is the finding that matters. The sibling repo's roster fixture
`tests/fixtures/madden08-roster-sample.bin` — the memory-card roster save — is 246,784 bytes
with `dbSize` **245,856** and exactly **4 tables `DCHT INJY PLAY TEAM`** [M, hexdumped
this session]. **The on-disc default roster and the memory-card roster save are the same TDB
object.** `MaddenRosterCompiler`'s output is, structurally, a drop-in for the disc member —
and because the sizes match exactly, the fixed-allocation discipline the ISO9660 writer
demands is satisfied for free.

---

## 5. What carries over unchanged, and what does not

### 5.1 Free — game-agnostic today

| primitive | why it carries [M] |
|---|---|
| `tools/ps2_iso9660.py` / `_writer.py` / `_verify.py` | pure ISO9660: 2048 and 2352 sector layouts, fixed-allocation in-extent replacement, independent verifier. Its own docstring frames it as the PS2 analogue of the Xbox XISO support, not as a 2K5 tool. |
| `mod_editor/games/_formats/ps2_disc` | `Ps2DiscIdentifier(identity)` is **parameterised by the game's `GameIdentity`**; its docstring already names "an ESPN NBA 2K5 module" as the intended second caller. |
| `mod_editor/games/_formats/ps2_elf` | ELF32-MIPS program headers, EE-address → file-offset, `pcsx2_crc`, pnach emit/parse, `build_synthetic_elf`. "No retail address or byte appears in this file." |
| `tools/xxh3.py` | pure-Python XXH3-64, the hash PCSX2 names replacements by. Validated against 1.2 M emulator-produced hashes. |
| `tools/spu_adpcm.py` | PS2 SPU-ADPCM codec (decode **and** encode), transcribed from SPU2 `Mixer.cpp`. The *codec* is console-wide; only the AUDO/AUSB *containers* around it are VC-specific. |
| `tools/nfl_outer.py` | the VC outer pack parser — **zero `SLUS` literals** [M]. Already portable; what is game-specific is the pack directory name and `PACK_SLOT_COUNT`. |
| contract + conformance + scaffold + chooser | `python -m mod_editor.games new <id>` writes a module that passes conformance on day one. |

### 5.2 Needs new format work

| format | for | state |
|---|---|---|
| **EA TDB** (`DB` v8, table dir, bit-packed records, 4× CRC-32/MPEG-2, LE PS2 / BE PS3, franchise 4-byte preamble) | Madden, NCAA Football, on-disc `STRMDATA.DB` / `DB_TEAMS.DAT` / `TEMPLATE.DAT` | **KNOWN and implemented**, but in the *sibling* repo: Python `parse_madden_tdb.py` (248 lines) + `write_madden_tdb.py` (225), byte-exact roundtrip; C# `MaddenTdb.cs` (629 lines) [M]. Becomes `_formats/ea_tdb`. |
| **PS2 memory-card containers** (`.psu`, `.max`, 8 MB card, ECC) | every save lane | **KNOWN twice over.** The fork has MIT PSU + card code inside `tools/nfl2k5_ps2_save.py`; the sibling repo's `pack_baslus.py` shells out to **GPL `mymcplus`** [M] — do not vendor that. Generalise the fork's own code into `_formats/ps2_memcard`. |
| **NCAA draft-class binary** (`46 00 40 06`, 1600 × 86 = 138,240 B) | Madden draft-class lane | KNOWN (sibling C#). Small; re-express in Python inside the game module. |
| **TERF / DIR1** | any EA on-disc lane | **mostly decoded this session** (§4.2). Remaining: per-member compression, container checksum. |
| **VC PS2 stack** (`/VC_<serial>`, 0x20 chunk headers, `TXTR/TSET/AUDO/AUSB`, VC-LZ, text banks) | a second VC title (NBA 2K5) | KNOWN for NFL 2K5, spelled `nfl2k5_ps2_*` across ~20 tools with ~62 `SLUS-20919` literals [M]. Extraction into `_formats/vc_ps2` is mechanical but real. |
| **EA BIG / VIV / FSH** | MVP Baseball | Open specs, open readers exist [S]. **Write is partial** — the community's own FSH tool (`FshEd`) "only supports graphics files for PC games, not the console versions" [S]. |
| **EA SCxl audio** (`SCHl/SCCl/SCDl`, VAG / EA-XA) | MVP, Madden, NCAA audio | Decode known (vgmstream); **no public SCHl writer or bank rebuilder** [S]. Classify `unknown` until proven. |

### 5.3 The registry rungs a lane can earn

The validator binds classification to `(backend.operation, gui.mode)` exactly [M]:

| classification | operation / gui.mode | extra requirement |
|---|---|---|
| `runtime-proved` | `write` / `edit` | `runtime.status == "visible-proved"` **with evidence paths** — a human saw it |
| `offline-writer-proved` | `write` / `edit` | bytes proved by an independent verifier; no witness needed |
| `extract-only` | `export` / `export` | a validated exporter that writes a local asset |
| `read-only-mapped` | `inspect` / `view` | catalogue only |
| `unknown` / `unsafe/deferred` | `none` / `deferred` | **must stay hidden** (`expose:false`) |

Two consequences that shape every module below. First, **an exporter can never be
`runtime-proved`** — a PCSX2 replacement pack is `extract-only` by rule, whatever a human sees.
Second, **`offline-writer-proved` is the honest ceiling for everything reachable without the
rig**, which is why a module can ship real value before any human is booked.

---

## 6. Per game

### 6.1 ESPN NBA 2K5 (PS2) — Visual Concepts, the owner's addition

| | |
|---|---|
| Serial | **`SLUS-20920`** (NTSC-U) [M — grepped PCSX2's own `GameIndex.yaml` locally: `name: "ESPN - NBA 2K5"`]. A European disc `SLES-53022` also exists; do not conflate. |
| Redump | **present and top-tier**: `redump.org/disc/8378`, v1.02, CRC-32 `e84f812b`, status "2+ dumps" [S] |
| ISO present | **nowhere** [M] |
| PCSX2 compatibility | **unrated** in PCSX2's own DB [M — its `GameIndex.yaml` entry carries no `compat:` line, unlike its three siblings] — unknown, not known-good |
| PC version | **none** — Xbox + PS2 only [S: `research/ps2_basketball_modding.md`] |
| Community | **alive and PS2-specific.** NLSC (`forums.nba-live.com` / `nba-live.com`) is the hub; SodaBig's "Prime Roster" for the **PS2** version was updated **2025-06-26** and re-uploaded 2025-06-07 [S]. Distribution is a **PS2 memory-card save transferred with MyMC** — the same class of artefact and tool our own pipeline uses [S]. |
| What they mod | rosters, essentially only. No texture packs, no ISO patches, no disc tooling found [S]. |
| Existing tools | **none for this generation.** Every NBA 2K IFF tool (RED MC v5.0, 2KVenueLab, Cyberface Editor) explicitly targets **NBA 2K12–2K15 / MLB 2K12, PC files only**; none reaches back to 2K5–2K8 [S]. No GitHub tool for NBA 2K5 exists [S]. |

**The serial neighbourhood is itself evidence.** The four ESPN 2K5 titles were assigned
**consecutive** serials — NFL 2K5 `SLUS-20919`, **NBA 2K5 `SLUS-20920`**, NHL 2K5 `SLUS-20921`,
College Hoops 2K5 `SLUS-20922` — and the previous ESPN wave was consecutive too (`SLUS-20726`
NBA Basketball, `20727` NFL Football, `20728` NHL Hockey, `20729` College Hoops, `20794` MLB)
[M, all grepped out of PCSX2's `GameIndex.yaml` locally]. Our own NFL 2K5 disc reads
`SLUS-20919` [M] and redump lists it at `disc/8379` v1.01 CRC-32 `d16bec78` [S]. One publisher,
one wave, one submission batch, one engine team. That makes shared tooling *likelier* — it does
not make it true, and §7.1 is still the read that settles it.

**Correction for the project's records:** an earlier note in the brief gives NFL 2K5 as
`SLUS-20916`. That serial is **Dance Dance Revolution EXTREME** — I grepped PCSX2's own
`GameIndex.yaml` and read the line [M]. NFL 2K5 is `SLUS-20919` [M, read from our own disc's
`SYSTEM.CNF`].

**Distribution caveat that shapes the roster lane.** NLSC's ESPN NBA 2K5 "Prime Roster" ships
as a **raw PCSX2 memory-card image (`Mcd001.ps2`)**, not a `.max` or `.psu` [S]. Our
`_formats/ps2_memcard` work must therefore cover whole-card read/write, not just the two export
containers — which is exactly what the fork's MIT card code in `tools/nfl2k5_ps2_save.py`
already does [M]. College Hoops 2K5 rosters instead ship as `.psv` (PS3-adaptor exports),
community-converted to `.psu` [S].

**Lanes that carry over.** Every one of them, *if* the container is shared: the disc inventory,
the text-bank lane, the uniform-colour lane, the stadium lane, the AUDO audio lane, the roster
lane and the PCSX2 replacement-pack export are all built on `/VC_<serial>` + `nfl_outer.py` +
`spu_adpcm.py` + `xxh3.py`, none of which is football-specific in code [M]. Plus the free
primitives in §5.1. **If it is not shared, essentially nothing carries over but ISO9660 and
identity**, and NBA 2K5 becomes a from-scratch reverse-engineering project.

**The one measurement that decides it** is in §7.1. It costs one `find` and one 4 KB read.

**Minimum viable module** (assuming shared container):

| row | surface | classification | why that rung |
|---|---|---|---|
| `nba2k5ps2.textures.disc_inventory` | `textures` | `read-only-mapped` | catalogue only; the exact shape of NFL 2K5's first shipped row |
| `nba2k5ps2.saves.roster_name_writer` | `saves` | `offline-writer-proved` | the community already ships roster saves; our PSU/card code + CRC-32 `EXTRA` recompute is the proven route |

That is a **two-row module that needs no human and no GPU**, and it lands the game in the
chooser. Uniform colours, text banks and a replacement-pack export follow one at a time.

**Effort.** Measurement 0.5 d; identity + inventory lane 2 d; `_formats/vc_ps2` extraction from
the NFL tools **5 d** (its 502 tests must stay green); roster save lane 3–5 d. **~11–13
agent-days** to a two-row module plus the shared format package — but **only** on the far side
of the measurement.

**Risks.** (a) The container may not be shared — the plan calls this "plausible, UNCONFIRMED"
and the basketball research found *no source* connecting NFL 2K5 to any NBA 2K format [S].
(b) NBA 2K5's roster save is a different object from NFL 2K5's `ROST`; the memory-card
*container* transfers, the payload does not. (c) **No PCSX2 `textures/<serial>/` replacement
pack exists for NBA 2K5, NHL 2K5 or College Hoops 2K5** — the community's central GBAtemp hub
thread was read in full and mentions none [S] — so a replacement-pack export lane for basketball
would be creating a market, not serving one. (d) Scope/branding: the product is called "2K
Football Mod Tools" — the interfaces plan raises this as open question 7 and it is the owner's
call, not ours.

### 6.2 MVP Baseball 2005 (PS2), and MVP 06 NCAA Baseball

| | MVP Baseball 2005 | MVP 06 NCAA Baseball |
|---|---|---|
| Serial | **`SLUS-21135`** (NTSC-U) [M, PCSX2 `GameIndex.yaml`] | **`SLUS-21367`** (NTSC-U) [M, indexed as "MVP '06 - NCAA Baseball"] |
| Redump | present, `redump.org/disc/11469` [S, search-index only — redump.org refused direct fetch] | present, **Redump ID 8389** [S, two independent mirrors agree]. *Do not confuse with `redump.org/disc/10276`, which is MVP **07**.* |
| ISO present | **nowhere** [M] | **nowhere** [M] |
| PC version | **YES** (Windows, Feb 2005) [S] | **no** — PS2 + Xbox only [S] |
| Community | **was the largest in this study — and its hub just died.** `mvpmods.com` was active to 2025-05-06 and then went **permanently offline around April 2026** (the team's own X post, an Operation Sports "gone offline permanently" thread, and independent DNS failures all agree) [S]. The surviving hub is **MVP Caribe / `mvp2kcaribe.com`** (loaded live; an early-access "MVP Baseball 2026" file; semi-official recognition from two real leagues per Kotaku) [S] — and it is a **PC** conversion scene. | **none found.** Searched specifically; nothing dedicated [S] |
| What they mod | full rosters/database, uniforms, stadiums, logos, total conversions, cameras [S] | — |
| Tools | `MVPedit` (roster/ratings), `bigGUI` (BIG/VIV), `FshEd` (FSH textures), MVP Studio & Uniedit [S] | none [S] |
| PCSX2 texture pack | **none found** [S], and Operation Sports' own list of PS2 sports titles that got serious emulation-era treatment names NFL 2K5, Madden 08, NCAA Football 06 and NCAA Football 14 — **MVP is absent** [S] |

**The disqualifying fact.** The community's own texture tool, `FshEd`, *"only supports graphics
files for PC games, not the console versions"* [S], and porting PC-mod content to PS2 is
discussed on forums as a hypothetical nobody has done [S]. **The MVP scene mods the PC SKU.**
A PS2 MVP module would be building a tool for a platform the community does not use, for a
game we do not own, in formats (BIG/VIV/FSH) whose write path is only partially public — and
its main distribution hub went offline five months ago [S].

**One honest counterweight.** There *is* exactly one PS2-native MVP tool:
`github.com/CollinErickson/MVP2005`, a **memory-card roster tool**, active as recently as
April 2026 [S]. One person, one repo, save-side only. It does not change the recommendation,
but it does mean "nobody touches MVP on PS2" would be an overstatement, and it is the first
thing to read if the owner overrules the deferral.

**Minimum viable module.** One row, `mvp2005ps2.textures.disc_inventory`, `read-only-mapped` —
identity plus an inventory of the `.BIG` members. Nothing more is honest until someone measures
whether `database/*.dat` is a TDB.

**Effort.** Identity + inventory 3 d; `_formats/ea_big` 4 d; `_formats/ea_fsh` (read) 3 d;
any writer, unbounded. **~10 agent-days for a read-only module**, and no evidence anyone wants it.

**Recommendation: defer.** Keep it on the list because the owner asked, but rank it last of the
four. If MVP is pursued at all, the honest first step is the **PC** SKU, which is where the
formats are open and the users are — and that is a different product, not a PS2 game module.
**Note MVP 06 NCAA Baseball only as a footnote:** no community, no tools, and no evidence it
shares MVP 2005's exact format [S].

### 6.3 NCAA Football (PS2) — which years, and why

**Which years the community actually mods: 06 first, then 11; 07 is neglected; 08 has a
little.** Operation Sports' NCAA Football Rosters subforum carries dated 2023-24-season threads
for **NCAA 06 and NCAA 11 PS2**; a thread exists literally titled *"Anybody have NCAA 07 PS2
Rosters?"* — asking, not offering [S]. `ncaanext.com` — actively shipping ("NCAA Next 26 is in
Beta Testing", Aug 2025) — **covers NCAA Football 06 exclusively**, confirmed from their own
About page [S]. Operation Sports' emulation-enhancement list names **NCAA Football 06** and
NCAA Football 14, not 07 or 08 [S].

So the brief's "06, 07, 08" should be read as **06 is the target; 07 and 08 are not**. And
there is a second candidate the brief did not name: **NCAA Football 11 PS2**, which the sibling
repo already treats as a draft-class source (`BASLUS-21932LClass10` → Madden 12) and which the
roster community actively maintains.

Two corrections to the brief's framing. **"College Football Revamped" is not the project to
look at** — searched specifically, nothing by that name is in scope here; the operative project
is **NCAA NEXT**, and it is 06-only [S]. (Revamped is the NCAA 14 PS3/360 scene, a different
generation and a different substrate.) And the **11,000-texture PCSX2/AetherSX2 pack is a
*joint* NCAA 06 + Madden 08 release** [S] — one team, one download, both games. That is a
strong argument for treating NCAA 06 and Madden 08 as one product surface rather than two.

Every NCAA Football PS2 serial, grepped out of PCSX2's `GameIndex.yaml` locally [M]. (Worth
recording *how*: twelve web lookups across psxdatacenter, redump.org, the PCSX2 wiki,
SerialStation, GameTDB and archive.org all failed to produce these — every one of those sites
blocks automated fetching. Pulling PCSX2's index from GitHub raw and grepping it locally
answered in seconds. Use that route first next time; it is `PRECHECKS.md` B.3b.)

| year | serial | PCSX2 compat | we own it? |
|---|---|---|---|
| NCAA Football 2004 | `SLUS-20719` | — | ✅ dev box [M, read from the disc] |
| NCAA Football 2005 | `SLUS-20991` | — | ❌ |
| **NCAA Football 06** | **`SLUS-21214`** | **5 (Perfect)** | ❌ ← the year the community mods |
| NCAA Football 07 | `SLUS-21459` | — | ❌ (and not worth acquiring) |
| **NCAA Football 08** | **`SLUS-21620`** | 5 (Perfect) | ❌ ← *see below* |
| NCAA Football 09 | `SLUS-21752` | 5 (Perfect) | ✅ dev box [M, read from the disc] |
| NCAA Football 10 | `SLUS-21892` | — | ❌ |
| **NCAA Football 11** | **`SLUS-21932`** | — | ❌ |

**Two of those serials are already load-bearing in the sibling repo, and nobody wrote it down.**
Its draft-class fixture is `BASLUS-21620LClass07` and its Madden-12 draft-class preset is
`BASLUS-21932LClass10` [S: sibling `CLAUDE.md`]. `SLUS-21620` is **NCAA Football 08** and
`SLUS-21932` is **NCAA Football 11** [M]. So the NCAA draft-class binary this whole toolchain
compiles is *NCAA Football 08 PS2's* "Send to Madden" export, and the M12 path is NCAA
Football 11's. The NCAA Football family is not a new game for this ecosystem — it is already
its upstream data source.

**One discrepancy worth a check.** `pack_baslus.py`'s M09 draft-class preset uses
`BASLUS-21769LClass08` [S], but `SLUS-21769` is **Yakuza 2** in PCSX2's index, and NCAA
Football 09 is `SLUS-21752` [M]. The sibling repo's own status table already says "PCSX2
verification of BASLUS suffix convention pending" for that tier — this is a concrete reason
to do it.

| | NCAA Football 06 | NCAA Football 09 | NCAA Football 2004 |
|---|---|---|---|
| Serial | **`SLUS-21214`** [M] | **`SLUS-21752`** [M] | **`SLUS-20719`** [M] |
| ISO present | **nowhere** [M] | dev box only | dev box only |
| Community | **the active one** — NCAA Next, OS rosters [S] | some [S] | little |

**What carries over.** Everything the Madden module builds. NCAA Football 09's disc is the same
`/DATA` + `TERF` + bare-TDB `STRMDATA.DB` shape as Madden 08's [M]; its `TEMPLATE.DAT` holds a
49-table TDB [M].

**Prior art from our own upstream author — read this before writing anything.** `antdroidx`
(the upstream of the sibling repo) publishes, all confirmed by listing the profile directly [S]:

| repo | what it is | why it matters here |
|---|---|---|
| `antdroidx/NCAA-Football-PS2-Modding-Resources` | "a collection of lessons learned for modding NCAA Football" | **the single highest-value document to read before this lane starts**, and it costs nothing |
| `antdroidx/NCAA-DB-Editor` | "DB/Save Editor for NCAA Football series on PS2/Xbox/PSP/GC", not year-locked, actively maintained | public proof NCAA Football PS2 roster saves are TDB and editable; descends from Madden Xtreme DB Editor + MaddenAMP + `tdbaccess` |
| `antdroidx/NCAA-Football-PS2-Coach-Editor` | "spreadsheet tool for importing and editing Coach database files" | **directly answers the sibling repo's own open workstream B** (real HC/OC/DC/ST coaches via the franchise `COCH` table, recorded as "not started") — do not rebuild this from scratch |
| `antdroidx/NCAA-Football-PS3-to-PS2-Roster-Porting-Tool` | PS3 → PS2/PSP roster conversion | the BE↔LE TDB problem, already solved once by someone else |
| `antdroidx/NCAA06-Roster-Archive`, `Madden05NEXT`, `madden06next`, `madden08next`, `madden-teams-db-splitter` | year-specific data and tools | corroborates the 06-and-08 focal-year pattern |

The whole `github.com/ncaanext` organisation was listed directly: **every repository targets
NCAA Football 06; zero target 07 or 08** [S]. Confirmed no PC SKU for NCAA Football 06/07/08
[S, Wikipedia direct].

**Minimum viable module** (per year, after the Madden module exists):

| row | surface | classification |
|---|---|---|
| `ncaa06ps2.players.roster_save` | `players_rosters` | `offline-writer-proved` |
| `ncaa06ps2.textures.disc_inventory` | `textures` | `read-only-mapped` |

**Effort.** With `_formats/ea_tdb` already built by the Madden module: **4–6 agent-days per
year** (identity, template signature, roster lane, tests). Without it, add the 3 days for the
format package.

**Risk.** We own NCAA Football 09 and 2004, **not 06** — the year that matters. Acquiring
NCAA Football 06 (PS2, NTSC-U) is a prerequisite, and until it exists the sensible move is to
prove the lane against **NCAA Football 09**, which we do own, and parameterise to 06 later.

### 6.4 Madden NFL (PS2) — 08, then 09 and 12

| | Madden 08 | Madden 09 | Madden 12 |
|---|---|---|---|
| Serial | **`SLUS-21638`** [M] (a `SLUS-21638F` Canada/French variant exists [S]) | **`SLUS-21770`** [M] | **`SLUS-21946`** [M] |
| Redump | **confirmed**, `redump.org/disc/20360`, SHA-1 `650056fcadde3a33fa8444823b207f621b22827b`, MD5 `15b60ad576665739c8bb8ad9dc6c02b1`, CRC32 `54680318`, re-verified 2025 [S] | **unconfirmed** — no `disc/NNNNN` URL surfaced; very likely present, check directly [S] | present, `redump.org/disc/36836` [S, search-index only] |
| ISO present | dev box **and** rig [M] | both (+ Deluxe on dev box) [M] | both, stock **and** Deluxe [M] |
| PC version | **yes** — the last PC Madden until Madden 19 [S] | no [S] | no [S/A] |
| Community | **very active into 2025-26**: FootballIdiot "JINXROSTER", OS "PS2 Roster Update?", and NCAA Next's **"Madden 08 NEXT"** — "a game patch for Madden 08 on PS2 that updates the game database to include the latest rosters, coaches, stadium names, franchise information like salary cap, contracts" [S] | **the flagship**: `github.com/maddendeluxe/madden09deluxe`, v0.5-beta, roster files dated **August 26** (~1 week before this study), 1000+-member Discord [S] | second Deluxe project, same author (`joshuablackstone`) and Discord [S] |
| What they mod | rosters, franchise DB, coaches, stadium names, salary cap, contracts, HD textures | rosters, uniforms, stadiums, fields, upscaled textures, portraits, schedule | rosters, teams, coaches, field/helmet logos, playbooks |
| Delivery | `.psu` roster saves + `mymc` + Delta Patcher ISO patches + PCSX2 texture packs + JSGME [S] | same [S] | same [S] |
| PCSX2 texture pack | **yes** — NCAA Next's combined "NCAA 06 + Madden 08 NEXT HD Remasters", *"over 11,000 new textures … over 1000 team uniforms, every logo upgraded, and stadiums updated"* [S] | **yes**, the mod *is* one — requires PCSX2 ≤ 1.7.2049 with texture replacement, "cannot run on real hardware" [S] | yes [S] |

**Note the community's focal years differ by franchise.** `ncaanext`/`antdroidx` ship "NEXT"
modernisations for Madden **05, 06 and 08** and for NCAA Football **06** [S]; the separate
"Deluxe" scene owns Madden **09 and 12** [S]. Two distinct communities, two distinct sets of
years, both live. Madden 08 sits in the first; Madden 09/12 in the second. Serving both is a
feature of doing Madden 08 first and parameterising outward.

**External prior art for the TDB substrate**, beyond `antdroidx`'s tools in §6.3 [S]:
`tdbaccess.dll` (Artem Khassanov, of NHLView) — the library the whole community tool lineage
sits on; **Madden AMP** on SourceForge and `keylimesoda/MaddenAmp` on GitHub (roster **and**
draft-class editing — the same two artefact types we produce); `ozwolf-software/madden-08-api`,
a Madden-08-specific API, low-maintenance but public. None of these is a dependency; all are
cross-checks for the field semantics the sibling repo derived independently.

**Correction for the project's records.** The sibling repo's `CLAUDE.md` points at
`../madden-db-editor` (`bep713/madden-db-editor`) as *"the existing reader/writer for the EA
TDB format… Reference for Tier 6."* That project covers **Madden 19–22 only** [S] — a later
branch of the TDB family, not the PS2 08/09/12 layout. It is a fine conceptual reference and a
poor byte-level one; the sibling repo's own `parse_madden_tdb.py` / `MaddenTdb.cs` are the
authority for PS2, and the note should say so.

**This is the one where we are not starting from zero.** The sibling repository at
`/mnt/c/GitHub/NCAA-Draft-Class-Editor` already ships, PCSX2-verified for 2018: byte-exact TDB
read/write in Python **and** C#, the four CRC-32/MPEG-2 fields, the franchise 4-byte preamble,
`.max`/`.psu` packing, 18 seasons of rosters, 19 of draft classes, a franchise compiler with a
real salary-cap economy and real OverTheCap contracts, and per-player career stats decoded
against known lines [S: its own `CLAUDE.md`]. And the community's own "Madden 08 NEXT" has
**independently converged on exactly that scope** [S].

**Minimum viable module** — three rows, all reachable **with no human and no GPU**:

| row | surface | classification | source of truth |
|---|---|---|---|
| `madden08ps2.players.roster_save` | `players_rosters` | `offline-writer-proved` | user's own `BASLUS-21638DRost5` save; `MaddenRosterCompiler` logic ported |
| `madden08ps2.saves.draft_class` | `saves` | `offline-writer-proved` | user's own NCAA export; fixed 1600 × 86 = 138,240 B |
| `madden08ps2.franchise.calendar_cap` | `saves` (or a franchise surface) | `offline-writer-proved` | user's own Week-1 `BASLUS-21638BFran1`; `SEAI.SEYR` + `SLRI.SCAD/SMAD/RFA1..4` |

Every one is fixed-allocation (the destination is the same size as the template), every one has
an independent verifier (re-decode the TDB and compare outside the declared ranges), and every
one has a **cheap synthetic source**: a minimal valid TDB is a few hundred bytes, and a 1600-record
draft class is 138,240 bytes of generated data. No retail byte enters the repository.

A fourth row is available and unusually cheap given §4.3: `madden08ps2.players.disc_roster`,
writing the same compiled TDB into `/DATA/TEMPLATE.DAT`'s member 0 through the existing
fixed-allocation ISO9660 writer — **the sizes already match** [M]. File it `unknown` until the
TERF checksum question (§4.2) is settled, then `offline-writer-proved`.

**Effort** (the interfaces plan says ~20 days; I agree, and here is the split):
`_formats/ea_tdb` 3 d · `_formats/ps2_memcard` 2 d · roster lane 4 d · draft-class lane 3 d ·
franchise lane 3 d · chooser-hosted window 3 d · validators, fragments, pins, docs 1 d ·
registry-row plumbing (13 pins in 9 files until the §5.4 hooks land) 0.5 d ·
optional PCSX2 witness 1 d. **≈ 20 agent-days.**

**Madden 09 and Madden 12 after it: 2 days each** — different serial, different template,
different `PLAY` bit layout that the metadata-driven reader absorbs transparently [S: sibling
`CLAUDE.md`]. Both discs are already on both machines [M].

**Risks.** (a) The Deluxe images share stock serials [M] — identity must be digest-based.
(b) Franchise saves enforce **four** CRCs on load and refuse with "error loading franchise" if
any is wrong; the sibling code recomputes all four, a fresh port must too [S]. (c) The
franchise template must be a true **Week-1** export — a later one silently degrades the cap
economy [S]. (d) Licence: the sibling repo has **no LICENSE file** [M] — see `PRECHECKS.md` D.2.

### 6.5 The rest of the VC family — short, as asked

| game | verdict |
|---|---|
| **ESPN College Hoops 2K5 (PS2)** — `SLUS-20922` [M], redump `disc/8377` v1.02 CRC-32 `bf547c9e` [S] | Real but small, and **intermittently alive**: an annual roster updater (TreyzAllDayz) was still going as of **Dec 2023**, and an Operation Sports thread carries a 2022-23-season update with "350+ names", shipped as `.psv` [S]. Mission fit is good (NCAA real-names motivation). **But PCSX2's own compatibility DB rates it `compat: 2` — "Menu", i.e. broken in-game** [M, grepped locally], and that community targets *real PS2 hardware* primarily [S] — so an emulator-side lane has nowhere to land and even a witness is doubtful. **Include only as a parameterisation of an NBA 2K5 module, never on its own, and only for save-side rows.** |
| **ESPN NHL 2K5 (PS2)** — `SLUS-20921` [M], redump `disc/8381` v1.03, "2+ dumps" [S] | **Dormant.** One real PCSX2 mod effort exists (Nov 2023, a single modder, alpha stage, no confirmed release) and nothing since [S]. PCSX2 rates it `compat: 5` — Perfect [M], so the platform is fine; the people are not there. **Exclude.** |
| NBA 2K6 / 2K7 / 2K8, College Hoops 2K6–2K8 | scattered 2K-Share-era rosters, **no tooling** [S]. Exclude. |
| NBA Street (PS2) | the real effort targets **Dolphin/GameCube**, and only one named hobbyist [S]. Exclude. |
| NCAA March Madness (EA, PS2) | real dated PS2 roster activity [S], but EA Vancouver's codebase — unrelated to both our TDB knowledge and the VC stack. Exclude. |

---

## 7. What must be measured first

### 7.1 The single highest-value measurement in this study

**Does ESPN NBA 2K5's PS2 disc carry a `/VC_<digits>` pack directory?**

NFL 2K5's ISO root is exactly `SLUS_209.19, SYSTEM.CNF, VC_20919` [M] — the pack directory is
named from the serial digits. So the check is literal: **does `SLUS-20920`'s root contain
`VC_20920`?** If it does, the whole Visual Concepts stack — outer packs,
0x20 chunk headers, `TXTR/TSET/AUDO/AUSB`, text banks, VC-LZ — is presumptively shared, and
`_formats/vc_ps2` is worth extracting. If it does not, basketball is a new engine.

Cost once the disc exists on the rig: **two read-only commands, under a minute**
(`PRECHECKS.md` A.4). Cost today: **unmeasurable, because no copy exists on any machine** [M].
This is the reason the acquisition list in `PRECHECKS.md` §A.2 is ordered the way it is.

### 7.2 The rest, in order

| # | measurement | on what | why it gates something |
|---|---|---|---|
| 1 | Disc inventory + `VC_*` check | NBA 2K5 | decides §6.1 entirely |
| 2 | `sha256` of image + boot ELF | every staged disc | the contract's `GameIdentity` cannot be written without them |
| 3 | Redump comparison per serial | every staged disc | separates a verified dump from a Deluxe rebuild |
| 4 | TERF member compression + any container checksum | Madden 08 `/DATA/TEMPLATE.DAT` | decides whether the on-disc roster row is `offline-writer-proved` or stays `unknown` |
| 5 | Save-file shape of the user's own `BASLUS-21638DRost5` / `BFran1` / NCAA class | Madden 08 | the module's identity is serial **plus** the template's table signature |
| 6 | Is MVP's `database/*.dat` a TDB? | MVP Baseball 2005 (PC copy is enough) | one run of the existing parser answers a question no public source answers [S] |
| 7 | One GS dump per game at a representative screen | each candidate | the only way any texture claim becomes witnessable (§8) |
| 8 | `ClassicTextureNames` default per serial | each candidate | PenguinScreen2's `s_classic_default_serials` **already contains M09 / NCAA09 / M12** but not SLUS-20919 [S: lane notes] — so the Madden family may need no flag while a VC title will. Verify, never assume. |

---

## 8. Where a human is unavoidable

The PS2 lane's own experience is the guide: it reached M1 (a witnessed texture replacement)
only with a person at the controls, and it documented exactly why.

| need | why an agent cannot do it | frequency |
|---|---|---|
| **H-2 headset check** before any GPU action on the rig | one VR headset is shared by three emulators; a false negative puts someone in a headset that gets yanked. The check must be read by a human as its own command | every session that touches the GPU |
| **GS dump capture** per game | menus are **unreachable headless** — the fork has no press-at-vsync button seam, and `VMManager.cpp` latches one dump per boot. Cold boots are frame-deterministic; save-state boots are **not**, so state-based diffs are meaningless [S: project memory] | once per game, per screen of interest |
| **Reaching gameplay** for uniform/field/roster witnesses | same reason. The 2K5 lane could witness *audio* and *intro-frame* changes headlessly, but colours/roster/text/stadium/playbooks needed a human to reach a menu | once per surface claimed `runtime-proved` |
| **Week-1 franchise export** per Madden/NCAA year | starting a franchise and exporting before Week 2 is a menu journey | once per year in scope |
| **`runtime-proved` sign-off** | the validator demands `runtime.status == "visible-proved"` with evidence paths — by construction, a person saw a screen | once per row that claims it |

**What does *not* need a human:** everything `offline-writer-proved`. All three Madden rows in
§6.4, both NCAA rows in §6.3 and both NBA rows in §6.1 are byte claims proved by an independent
verifier. **A useful module can ship before the human is ever booked** — that is the single
biggest scheduling lever in this study.

Human time to budget: **~30–45 min per game** for boot + two dumps; **~45 min per Madden/NCAA
year** for the Week-1 franchise export.

---

## 9. Effort and risk, consolidated

| work item | agent-days | depends on |
|---|---|---|
| Licence on the sibling repo (`PRECHECKS.md` D.2) | ~0 (owner) | — |
| Dev-box disk cleanup | 0.5 | — |
| `_formats/ea_tdb` (Python port, LE+BE, synthetic builder, tests) | 3 | licence |
| `_formats/ps2_memcard` (generalise the fork's MIT PSU/card code) | 2 | — |
| **Madden 08 PS2 module** (3 rows + window + fragments + pins) | **20** total incl. the two above | — |
| Madden 09 PS2 | 2 | Madden 08 |
| Madden 12 PS2 | 2 | Madden 08 |
| NCAA Football 09 PS2 (we own it — prove the lane here) | 4–6 | Madden 08 |
| NCAA Football 06 PS2 (parameterise) | 2 | NCAA 09 + the disc |
| NBA 2K5 measurement | 0.5 | **the disc** |
| `_formats/vc_ps2` extraction from the NFL tools | 5 | measurement says yes |
| NBA 2K5 module (identity + inventory + roster save) | 5–7 | `vc_ps2` |
| College Hoops 2K5 (parameterise) | 2 | NBA 2K5 |
| MVP Baseball 2005 read-only module | 10 | the disc; **not recommended** |
| Upstream §5.4 hooks PR (kills 13 pins × 9 files, forever) | 1 | owner's acceptance |

**Top risks, honestly ranked.**

1. **We don't own the discs for three of the four asked-for games** [M]. Everything basketball
   and baseball is blocked on acquisition, not on engineering.
2. **NBA 2K5 container sharing is unconfirmed** — "plausible" in the plan, and the basketball
   research found *no source* linking NFL 2K5 to any NBA 2K format [S]. If it is not shared,
   §6.1's estimate is wrong by a factor of several.
3. **Franchise CRCs and the Week-1 template rule** are the two ways a Madden module silently
   produces a file that will not load or that shows 2007-era money [S].
4. **The 13-count-pin tax** per new game persists until the §5.4 hooks land [M].
5. **Licence** — the sibling repo has none [M]; vendoring before that is fixed is not mergeable.
6. **Scope creep into non-football** is an owner/product decision (the plan's open question 7),
   not an engineering one, and it should be answered before basketball work starts.
7. **Disk on the dev box** — 50 GiB free, 95% used, with a documented history of crashing WSL [M].

---

## 10. Recommended order, and the first module

**The interfaces plan recommends Madden 08 PS2 (rosters + draft classes) first, and NBA 2K5
"measured by disc inventory first". I agree with both, and this survey strengthens the first
and re-times the second.**

### The order

| # | do this | why here |
|---|---|---|
| 0 | Licence the sibling repo; clean the dev box; run the existing conformance suite in a scratch copy | free, and each one unblocks or de-risks everything after it |
| 1 | **Madden 08 PS2** — `_formats/ea_tdb` + `_formats/ps2_memcard` + roster + draft-class + franchise rows | every format is already proven end-to-end in the sibling repo; we own the disc **twice**; synthetic sources are trivially generated; no GPU, no human, no ISO writer, no new container. It also *builds the two format packages every later EA title needs.* |
| 2 | **Madden 09 + Madden 12** | 2 days each, pure parameterisation; both discs already on both machines [M]; the Deluxe scene is the most active community in this study and ships exactly `.psu` roster saves [S] |
| 3 | **NCAA Football 09 PS2** | we own it [M]; same disc family, same TDB substrate [M]; proves the "different game, same engine" axis without waiting on an acquisition |
| 4 | **NCAA Football 06 PS2** once the disc exists | this is the year the community actually mods [S] — NCAA Next covers 06 and nothing else |
| 5 | **NBA 2K5 measurement** (§7.1) — run it the day the disc lands, out of band, ahead of its queue position | it is half a day and it changes the size of the remaining work by a factor of several. Do not let it wait behind step 4. |
| 6 | **NBA 2K5 module**, if and only if step 5 says the container is shared | then College Hoops 2K5 as a 2-day parameterisation |
| 7 | On-disc Madden lane (`TEMPLATE.DAT`) once TERF's checksum question is settled | newly plausible because of §4.3 |
| — | **MVP Baseball**, **NHL 2K5**, NCAA Football 07/08, NBA 2K6-2K8, NBA Street, March Madness | do not schedule |

### First module: **Madden NFL 08 (PS2)** — `madden08_ps2`

Reasons, in the order I weight them:

1. **The formats are not just known, they are shipped and PCSX2-verified.** TDB read/write,
   four CRCs, the franchise preamble, `.max`/`.psu` packing, 18 seasons of rosters, 19 of draft
   classes — all in the sibling repo, with a 2018 franchise confirmed in-game [S].
2. **It needs nothing this survey found missing.** We own the disc on both machines [M]; the
   deliverables are saves, so no TERF work, no ISO writer, no GPU, no human witness, no
   acquisition.
3. **It builds the two format packages every later EA title needs** — `ea_tdb` and
   `ps2_memcard`. Madden 09, Madden 12 and both NCAA years then cost 2–6 days each instead of
   20. No other starting point has that leverage.
4. **The demand is documented and current.** Madden 09 Deluxe shipped roster files dated ~1 week
   before this study, to a 1000+-member Discord, in exactly the `.psu` container we produce [S];
   NCAA Next's "Madden 08 NEXT" independently converged on our own franchise-compiler scope [S].
5. **Synthetic sources are cheap and provably retail-free** — a minimal TDB is a few hundred
   generated bytes; a 1600-record draft class is generated data. The conformance harness can
   prove the lane on CI without anyone owning a disc, which is the whole point of the contract.

**The one change I would make to the plan.** Its roadmap puts NBA 2K5 measurement at step 8,
after five other pieces of work. Move the *measurement* (not the module) to whenever the disc
arrives: it is half a day, it needs no code, and it is the difference between a 5-day and a
20-day basketball estimate. Everything else in the plan's order stands.
