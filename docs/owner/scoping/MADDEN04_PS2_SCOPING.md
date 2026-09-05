# Madden 04 Studio (PS2, SLUS-20752) — scoping study

**Question.** What does it take to add **Madden NFL 2004, PlayStation 2** as a game
module in SOFTDRINKTV's 2K5 Mod Studio fork, on the core Game Studio shell, reusing
as much as possible of what the owner has already decoded elsewhere?

**Answer, in one line.** Less than any other candidate title, because three
independent bodies of the owner's prior work converge on exactly this disc: the
fork's generic `TERF`/`MMAP` reader parses **100 %** of it with zero new format
code, the NCAA-Draft-Class-Editor's EA-TDB substrate reads its roster database
**unmodified**, and `nfl-online-revival` has been reverse-engineering *this exact
ELF* (`14F8B841`) as its primary title for months. Madden 04 is not a new port —
it is a **wiring job over three finished substrates**.

Every claim below is marked **[M]** measured by me in this session (read-only,
commands in `PRECHECKS-madden04.md`), **[S]** sourced from a named file in one of
the owner's repos, or **[A]** assumed / inferred and not yet verified.

> **Scope discipline.** Nothing in this study was written, committed or modified in
> any git worktree. No emulator was launched and the rig was never contacted. The
> only bytes read were the retail disc image, and every payload extracted during
> measurement was deleted afterwards (§10.3).

---

## 0. Headline findings

1. **[M] The whole disc is one container format the fork already reads.** All 51
   probed `/DATA` containers are EA `TERF`, version word `02020005` — byte-identical
   to Madden 09's. 14,981 members parsed, **0 layout violations**. Nothing needed
   changing in `ea_terf.py`.
2. **[M] There is no unknown codec on this disc.** Every one of the 14,981 members
   is either stored (11,700) or **LZH1** (3,281), and the fork decodes both. This is
   *better* than the Madden 09 position, where the compressed members were recorded
   as an open question (§2.4).
3. **[M] The roster database is EA TDB v8 — the format this project already owns two
   implementations of.** `NCAA-Draft-Class-Editor/tools/parse_madden_tdb.py`, run
   **unmodified**, reads Madden 2004's on-disc TDBs and returns real 2003 rosters,
   real coaching staffs, and a `DCHT`/`INJY` schema that is *bit-for-bit identical*
   to the Madden 08 roster save (§3).
4. **[M] The ELF CRC is `14F8B841`** — the exact CRC on all ~34 gameplay `.pnach`
   files in `/mnt/c/GitHub/nfl-online-revival/patches/`. The owner's entire Madden
   gameplay-patch library already targets the disc sitting on this machine (§5).
5. **[M] Coaches are on the disc, per team, in a table the toolchain reads.** 128
   `COCH` records = 32 teams × {HC, OC, DC, ST}, with real 2003 names. This is the
   open "Workstream B" from the owner's project memory, already solved as a *read*
   (§3.4).
6. **[M] Uniform art is not where Madden 09 keeps it.** Madden 04 has **no
   `UNIFORMS.DAT`**; `UIS_UNI.DAT` is a 1-member empty stub. Uniform *assignment*
   lives in a 3-field `TUNI` TDB table; the *art* is MMAP spread across
   `UIS_PLYR.DAT` (2,124 members at 96×96). This is the one genuine format
   divergence from Madden 09, and it is a small one (§6).
7. **[M] 5,776 MMAP texture headers parsed with zero failures**, giving sane
   dimensions (96×96 kits, 128×128 faces and logos, 480×320 card art). The texture
   lane reaches `read-only-mapped` on day one without a line of new code (§6).

---

## 1. Identity facts (deliverable a)

All measured this session against `/mnt/c/Roms/PS2/Madden NFL 2004 (USA).iso`.

| Fact | Value | How |
|---|---|---|
| Serial | `SLUS-20752` | **[M]** `ps2_iso9660.py --inspect` |
| Boot file | `SLUS_207.52` | **[M]** `SYSTEM.CNF` → `BOOT2 = cdrom0:\SLUS_207.52;1` |
| Volume id | `MADDEN04` | **[M]** ISO9660 PVD |
| **PCSX2 ELF CRC** | **`14F8B841`** | **[M]** `code_patches.py --crc` |
| Boot ELF sha256 | `5cb956b62a32a9aeed804c94efdc9a5da6f24ef9eb5b57d7bd8d6116170bd36c` | **[M]** |
| Boot ELF size | 5,354,036 B | **[M]** |
| **Image sha256** | **`b6488caf903920cddd25a9c74e1d2963b505ae302bc2faed9dfa1a0bffadccc5`** | **[M]** `sha256sum`, full 3 GB read |
| Image size | 3,207,397,376 B (2.99 GiB) | **[M]** |
| Sector layout | 2048-byte logical, `data_offset` 0 | **[M]** |
| Volume blocks | 1,566,112 | **[M]** |
| **Trailing slack** | **0 bytes** | **[M]** — a clean retail rip |
| Files / dirs | 124 files, 6 dirs (`/SYSTEM /ONLINE /NETGUI /NETGUI/MODULES /CNF /DATA`) | **[M]** |
| Declared file bytes | 3,206,411,063 | **[M]** |
| **Aliased extents** | **0** | **[M]** — no two directory records share an extent, so the bounded ISO writer will not refuse this image |
| `writable_geometry` | `true` | **[M]** `ps2_iso9660_writer.py --inspect` |

### 1.1 Two CRCs, and the trap

**[S]** `nfl-online-revival/docs/binary-identity.md:91` records *both* CRCs for this
ELF: zlib `crc32` = `CFABB64D`, PCSX2 game-CRC (word-XOR) = `14F8B841`, and warns at
`:116-127` that *"a tool comparing 'the CRC' could be right for one title and
silently wrong for the other."* **[M]** My independent measurement with the fork's
own `--crc` returns `14F8B841`, agreeing with the PCSX2 column. The module's identity
record must state which convention it means. The fork's `code_patches.py --crc`
already emits the PCSX2 one and labels it `pcsx2_crc`, so this is a non-issue as long
as the module reuses that helper rather than hand-rolling a CRC.

**[M]** Control measurements on the same machine, same tool, for calibration:

| Title | Boot | PCSX2 CRC | ELF sha256 (first 16) |
|---|---|---|---|
| Madden NFL 2004 (USA) | `SLUS_207.52` | `14F8B841` | `5cb956b62a32a9ae…` |
| ESPN NFL 2K5 (USA) | `SLUS_209.19` | `42F9D5AF` | `e8c3ba9a3224d567…` |
| Madden NFL 09 (USA) | `SLUS_217.70` | `38014255` | `adb400ba49702114…` |

Those are the *only two* CRCs appearing in the owner's `patches/` directory:
`14F8B841` on 34 files and `42F9D5AF` on one. **[M]** So the patch library is
"Madden 2004 PS2, plus one 2K5 patch" — and both discs are here.

### 1.2 A note on `"retail": false`

**[M]** The fork's `--crc` reports `"retail": false` for both Madden 2004 and Madden
09, and `true` for 2K5. **[A]** This is almost certainly because the current
`nfl2k5_ps2` module carries a hash allow-list that only knows 2K5's own retail ELF,
not because the Madden images are non-retail. A Madden 04 module supplies its own
identity record and the flag becomes meaningful for it. **Do not read this field as
evidence about the disc** until the module defines it.

---

## 2. The disc's container inventory (deliverable b)

### 2.1 Everything is TERF

**[M]** Every file under `/DATA` — all 66 of them, from the 44-byte `UIS_DUMY.DAT` to
the 1.76 GB `MOVIEDAT.DAT` — begins with `TERF` and carries the version word
`02020005`. Header chunk size varies (16, 64 or 2048 bytes) and member alignment
varies (4, 64 or 2048), but both are read from the file, not assumed.

**[M]** Fully parsed 51 of them (the ones under the reader's 96 MiB guard):

```
containers fully parsed : 51
members                 : 14,981
layout violations       : 0
codecs                  : stored 11,700 | LZH1 3,281       ← no unknown codec
formats                 : MMAP 8,255 | unclassified 4,634 | SMF 1,190 | empty 319
                          TDB 308 | DMF 221 | TERF 28 | SKL1 10 | FNTS 9
                          TEXT 3 | SEVT 2 | MPCh 1 | ELF 1
```

**[M]** The four containers above the guard were header-probed only, and are also
TERF `02020005`: `MOVIEDAT.DAT` (116 members, 1.76 GB), `SPCHDATA.DAT` (7,659
members, 660 MB), `SOUNDDAT.DAT` (447 members, 244 MB), `UIS_FMV.DAT` (128 members,
215 MB).

### 2.2 The container table

**[M]** Ordered by member count. "Rung d1" is the registry classification the lane
could honestly claim on **day one**, given only code that exists today.

| Container | Size | Chain | Members | Codecs | Formats | Shell page | Rung d1 |
|---|---|---|---|---|---|---|---|
| `SPCHDATA.DAT` | 660 MB | TERF→DIR1→? | 7,659 | — | speech | Audio | unknown |
| `SPCHHDRS.DAT` | 141 KB | →DATA | 4,021 | stored | unclassified | Audio | read-only-mapped |
| `UIS_PLYR.DAT` | 11.4 MB | →DATA | 2,124 | stored | **MMAP 2,124** | Uniforms / Art | read-only-mapped |
| `UIS_MCFL.DAT` | 42.8 MB | →DATA | 1,496 | stored | **MMAP 1,496** | Art (cards) | read-only-mapped |
| `STADIUMS.DAT` | 55.2 MB | →COMP→DATA | 1,052 | LZH1 437 / stored 615 | SMF 421, MMAP 4 | Stadiums | read-only-mapped |
| `PLADATA.DAT` | 61.8 MB | →COMP→DATA | 1,038 | LZH1 774 / stored 264 | MMAP 756, DMF 74 | Players (models) | read-only-mapped |
| `COACHES.DAT` | 9.7 MB | →COMP→DATA | 756 | LZH1 543 / stored 213 | MMAP 611, DMF 144 | Coaches | read-only-mapped |
| `FIELDART.DAT` | 7.9 MB | →COMP→DATA | 716 | **LZH1 716** | SMF 644, MMAP 72 | Field art | read-only-mapped |
| `COACFACE.DAT` | 7.0 MB | →COMP→DATA | 501 | **LZH1 501** | MMAP 501 | Coaches | read-only-mapped |
| `SOUNDDAT.DAT` | 244 MB | TERF | 447 | — | audio | Audio | unknown |
| `PLYRFACE.DAT` | 8.8 MB | →DATA | 392 | stored | MMAP 392 | Players (faces) | read-only-mapped |
| `ANIMDATA.DAT` | 24.5 MB | →DATA | 365 | stored | SKL1 10, uncl. 354 | — | read-only-mapped |
| `UIS_TMLO` / `UIS_SLIV` | 5.1 / 0.9 MB | →DATA | 290 each | stored | MMAP | Team art | read-only-mapped |
| `UIS_CTLO.DAT` | 6.2 MB | →DATA | 241 | stored | MMAP 241 | Team art | read-only-mapped |
| **`DB_TEAMS.DAT`** | **8.4 MB** | **→DATA** | **232** | **stored 232** | **TDB 232** | **Rosters / Coaches / Uniforms** | **extract-only → offline-writer** |
| `STADATA.DAT` | 3.1 MB | →COMP→DATA | 201 | LZH1 60 / stored 141 | SMF 119, MMAP 80 | Stadiums | read-only-mapped |
| `UIS_COAC.DAT` | 1.0 MB | →DATA | 188 | stored | MMAP 188 | Coaches | read-only-mapped |
| `UIS_FMV.DAT` | 215 MB | TERF | 128 | — | video | — | unknown |
| `MOVIEDAT.DAT` | 1.76 GB | TERF | 116 | — | video | — | unknown |
| `GAMEDATA.DAT` | 2.2 MB | →COMP→DATA | 76 | LZH1 67 / stored 9 | **TDB 64**, SEVT 2, TEXT 1 | **Playbooks** | extract-only |
| `LOADDATA.DAT` | 3.7 MB | →COMP→DATA | 45 | LZH1 43 | MMAP 44, TEXT 1 | Art (load screens) | read-only-mapped |
| `UIS_ALL.DAT` | 6.0 MB | →DATA | 28 | stored | **TERF 28** (nested) | — | read-only-mapped |
| **`TEMPLATE.DAT`** | **2.7 MB** | **→DATA** | **12** | **stored 12** | **TDB 12** | **Rosters (fresh template)** | **extract-only → offline-writer** |
| `UIS_FONT.DAT` | 194 KB | →**HSH1**→DIR1→DATA | 9 | stored | FNTS 9 | Text | read-only-mapped |
| `ONLINE.DAT` | 1.2 MB | →DATA | 4 | stored | ELF 1, TEXT 1 | — | read-only-mapped |
| *~25 further `UIS_*`* | small | mixed | 1–86 | mixed | MMAP / uncl. | UI art | read-only-mapped |

Non-TERF files:

| File | Size | What | **[M]** |
|---|---|---|---|
| `STRMDATA.DB` | 863 KB | **Bare EA TDB v8**, magic `DB\x00\x08`, **70 tables** (`EACD`, `ERWD`, `AGCM`, …) | commentary / streamed-audio database |
| `FE.QKL` | 9.7 MB | `QL01` bundle, `FILS` chunk with a filename table (`animdata.dat`, …) | front-end quick-load manifest |
| `GAME.QKL` | 6.9 MB | `QL01`, same shape | in-game quick-load manifest |
| `NETGUI/NTGUI.ELF` | 4.2 MB | second MIPS ELF (online GUI) | ELF32-LE `ET_EXEC` |
| `SLUS_207.52` | 5.4 MB | boot ELF | — |
| 40 × `.IRX` | small | stock Sony IOP modules, duplicated `/SYSTEM` ↔ `/NETGUI/MODULES` | not module content |

### 2.3 The two new chunk kinds

**[M]** Two things appear here that the Madden 09 notes do not record:

- **`HSH1`** — `UIS_FONT.DAT`'s chain is `TERF → HSH1 → DIR1 → DATA`. The fork's
  reader already has `HSH1_MAGIC` in its public API and walked it without complaint,
  so this is *supported*, merely undocumented for this title.
- **`QL01`** — `FE.QKL` / `GAME.QKL`. Not TERF, not TDB. **[A]** From the visible
  `FILS` chunk and embedded filenames these look like load-order manifests rather
  than asset payloads, so they are probably informational, not editable content.
  Cheap to confirm, low value either way.

### 2.4 Why this disc is *easier* than Madden 09

**[S]** The Madden 09 pre-check note
(`scratchpad/madden09-precheck/NOTES.md`) records the compressed members as an open
problem: *"UNIFORMS.DAT (725 members), FIELDART.DAT (715), STADIUMS.DAT (1,355) =
COMP with high-entropy member bytes (not RefPack 10FB/11FB, not zlib) — the
per-member compression is the open question."*

**[M]** On Madden 2004 that question does not arise: all 3,281 compressed members are
LZH1 and all 3,281 decompressed cleanly, yielding members that then classify as
MMAP / SMF / DMF. **[S]** The reason is historical — `nfl-online-revival/tools/lzh1.py`
reversed LZH1 *from the Madden 2004 ELF itself*. The codec was derived from this
binary; of course it fits this disc.

---

## 3. The roster database — the deepest reuse in the study (deliverable f)

### 3.1 It is EA TDB v8, and our own parser reads it unmodified

**[M]** I extracted member 0 of `/DATA/TEMPLATE.DAT` (253,044 B) and ran
`/mnt/c/GitHub/NCAA-Draft-Class-Editor/tools/parse_madden_tdb.py` on it **with no
changes to the tool**. It parsed cleanly:

```
Header: magic 'DB', version 2048 (0x0800), dbSize 253044, tableCount 4, preambleBytes 0
Table DCHT @ 56     : 1887/2912 records,   8-byte (63-bit) stride,   4 fields
Table INJY @ 23456  :    1/320  records,   8-byte (63-bit) stride,   5 fields
Table PLAY @ 26136  : 1990/2048 records, 108-byte (863-bit) stride, 112 fields
Table TEAM @ 249152 :   33/33   records,  88-byte (703-bit) stride,  59 fields
```

`DCHT / INJY / PLAY / TEAM` is **exactly** the four-table roster schema this project
documents for the Madden 08 memory-card roster save. Madden 2004 keeps it on the
disc instead of on a memcard, wrapped in a TERF member — but the bytes inside are
the same substrate.

**[M]** Control: the same parser on this project's own
`tests/fixtures/madden08-roster-sample.bin` reports the identical header shape
(`version 2048`, `preambleBytes 0`) and the identical `DCHT` (8-byte / 63-bit /
4 fields) and `INJY` (8-byte / 63-bit / 5 fields) layouts. **[M]** Field-by-field,
`DCHT` and `INJY` are **100 % identical between Madden 2004 and Madden 08** — same
names, same types, same bit offsets, same widths. Not "similar": identical.

### 3.2 How much the schema drifted, measured

**[M]** Diffing Madden 2004 (from the disc) against Madden 08 (from this project's
fixture), per table:

| Table | M04 fields | M08 fields | shared | shared with identical (type, width) | M04-only | M08-only |
|---|---|---|---|---|---|---|
| `DCHT` | 4 | 4 | 4 | **4 (100 %)** | 0 | 0 |
| `INJY` | 5 | 5 | 5 | **5 (100 %)** | 0 | 0 |
| `PLAY` | 112 | 110 | 104 | **96 (92 %)** | 8 | 6 |
| `TEAM` | 58 | 66 | 57 | **56 (98 %)** | 1 | 9 |

**[M]** The 8 shared `PLAY` fields whose *widths* differ are all cosmetic/appearance:
`PBRE` 1↔2, `PCPH` 2↔3, `PHLM` 2↔3, `PLSH` 4↔3, `PRSH` 4↔3, `PSKI` 3↔2, `PTAL` 5↔6,
`PTAR` 5↔6. **Every rating field is shared and identically sized.**

**[M]** `PLAY` M04-only: `PCEL PFGE PMGS PQGS PQTS PTPS PTSS PWSS`.
`PLAY` M08-only: `PEGO PICN PMOR POPS PRL2 PROL` — i.e. the franchise-era additions
(ego, morale, role) that 2004 predates.
**[M]** `TEAM`: only `TLNA`'s string width differs (120 vs 144 bits); M08 adds
`FRID TAUO TFLO TMNC TREP TRV1 TRV2 TRV3 TSID`.

**[S]** A separate line of evidence agrees. Parsing MaddenAmp's *PC* Madden 2004
fixtures (`github.com/keylimesoda/MaddenAmp`, `04files/2004_Roster.ros`) yields
`PLAY` at **108-byte stride with 112 fields** — the same stride and the same field
count I measured on the PS2 disc. **[S]** That analysis also found that while ~96 of
104 shared field *widths* match, only ~6 sit at the same *bit offset*. **[M]** My own
measurement is consistent: I compared widths (96/104 match); offsets shift freely.

**This is precisely the Madden 08 → Madden 12 situation the project already solved.**
Per `NCAA-Draft-Class-Editor/CLAUDE.md`, M12 shifted ~74 of 110 `PLAY` fields and the
metadata-driven compiler *"handles transparently"* because it reads each field's
offset from the file's own field directory. Bit-offset drift is a non-event for this
codebase; only names and widths matter, and those are ~92–100 % stable.

### 3.3 What `DB_TEAMS.DAT` actually contains — full census

**[M]** All 232 members are TDB v8, all **stored** (no compression). Census of every
member (table presence, and the first `TEAM` record's `TDNA`/`TLNA`/`TSNA`):

```
members                        : 232        layout violations : 0
members carrying a named TEAM  : 232        (none anonymous)
total PLAY records             : 11,527
total COCH records             : 128
tables present in all 232      : PLAY, TUNI, TEAM      (DCHT in 231)
tables present in 33           : INJY PCDE PCKI PCKP PCNG PCOF PCOL
                                 PSDE PSKI PSKP PSNG PSOF PSOL
tables present in 32           : CPSE COCH OCIS OTGO OTRS
```

The structure is unambiguous:

| Member index | What | Players |
|---|---|---|
| `0` | **Free Agents** (`FA`) | 247 |
| `1 … 32` | **The 32 NFL teams**, `TGID` 1–32, alphabetical by mascot — Bears(1), Bengals(2), Bills(3) … Vikings(32) | 53–55 each |
| `33 … 231` | **199 classic / historical teams** — `02 Bucs`, `02 Raiders`, `01 Rams`, `01 Patriots`, `00 Ravens`, `99 Rams`, `99 Titans`, … | 47–49 each |

**[M]** `TGID` runs 1–32 **alphabetically by mascot**: Bears(1), Bengals(2), Bills(3)
… Texans(30), Titans(31), Vikings(32). That is the same *scheme* as the Madden 08
roster save, which `NCAA-Draft-Class-Editor/CLAUDE.md` also records as "TGID 1-32"
— though that note says "Texans last (slot 32)", which does **not** describe what I
measured here. **Do not index teams by ordinal.** This is exactly the off-by-one class
of bug the project already hit and fixed in Tier 16/17 by resolving teams through each
`TEAM` record's `TDNA` mascot string instead of its slot number; a Madden 04 module
must do the same from day one.

**[M]** Sample of real data read straight off the disc (member 1, Chicago Bears):

```
TEAM : TDNA='Bears'  TLNA='Chicago'  TSNA='CHI'  TGID=1
PLAY : Brad Maynard   P  #4   OVR 95  SPD 18  AGE 29
       Alex Brown    DE  #96  OVR 77  SPD 77  AGE 24
       Phillip Daniels DE #93  OVR 79  SPD 62  AGE 30
```

Those are the real 2003 Chicago Bears. The roster lane is not a research problem; it
is a UI problem.

**[S]** Independent corroboration: `nfl-online-revival/docs/xbox-data-layer.md:128-136`
records `DB_TEAMS.DAT` as sha256 `1bd9b82b…`, 8,439,360 B, **232 TERF members all
TDBs, 1,743 players across teams 1–32**. **[M]** My census gives 8,439,360 B, 232
members, and 1,743 players when summed over members 1–32. Three independent
measurements agree.

### 3.4 Coaches are on the disc — the open Workstream B, already readable

**[M]** 32 members carry a `COCH` table with **4 records each = 128 coaches**, 66
fields wide, keyed by `TGID`. Read from member 1:

```
COCH: CLNA='D.Jauron'    TGID=1  CAGE=52  COFF=70  CDEF=75  CHTY=1   ← head coach
COCH: CLNA='J.Shoop'     TGID=1  CAGE=34  COFF=69  CDEF=40  CHTY=0   ← OC
COCH: CLNA='G.Blache'    TGID=1  CAGE=54  COFF=41  CDEF=73  CHTY=0   ← DC
COCH: CLNA='M.Sweatman'  TGID=1  CAGE=55  COFF=36  CDEF=35  CHTY=0   ← ST
```

That is the real 2003 Bears staff (Dick Jauron HC, John Shoop OC, Greg Blache DC,
Mike Sweatman ST), with `CHTY` distinguishing the head coach.

The owner's project memory lists *"Workstream B TODO: real HC/OC/DC/ST coaches per
year via franchise `COCH` table"* as not started. **On Madden 2004 the `COCH` table
is on the retail disc, in a stored TDB member, readable today with existing code.**
That makes Madden 04 Studio a *coaches* studio essentially for free — which no other
title in the fleet currently offers.

### 3.5 Uniform assignment lives in a 3-field table

**[M]** All 232 members carry `TUNI`, 4-byte records, 3 fields:

```
TUNI: UFID (UINT,  9 bits)   uniform id
      TGID (UINT, 10 bits)   team
      TUCO (UINT,  4 bits)   slot / colourway
member 1 (Bears): (UFID 2, TUCO 1) (UFID 3, TUCO 0) (UFID 199, TUCO 2) (UFID 224, TUCO 3)
```

Four uniform slots per team, pointing by `UFID` at art that lives elsewhere (§6).
Editing *which* uniform a team wears is a 9-bit write into a stored TDB member —
trivially in reach. Editing *what the uniform looks like* is the hard part.

### 3.6 What this means for the writer rung

**[M]** `DB_TEAMS.DAT` and `TEMPLATE.DAT` are **100 % stored** — 244 of 244 members
at codec 0. That matters, because the fork's `rewrite_member` documents that in a
`COMP` container a replacement *"is written stored (codec 0), because no LZH1 encoder
exists"*, which grows the file. **Neither roster container is COMP, so roster writes
have no compression problem at all**: a same-size TDB member drops straight back into
its aligned slot and nothing after it moves.

**[M]** And the ISO writer's preconditions are met: `slack_bytes = 0`,
`writable_geometry = true`, **0 aliased extents**, no Joliet SVD encountered,
2048-byte sectors. The bounded fixed-allocation writer will accept this image.

**[A]** The remaining unknown for a *runtime-proved* roster rung is the on-disc
checksum. **[S]** `nfl-online-revival/docs/roster-checksum.md` + `roster-delivery.md`
document that Madden 2004 computes a roster CRC over *"`select * from PLAY where
TGID between 1 and 32 order by PGID`… 1,743 rows… an otherwise-ordinary zlib CRC-32,
seeded not with 0 but with the row count"*, value `0x8108963c`, and that
`tools/roster_checksum.py` implements it. So the check exists, is understood, and has
a reference implementation — but a Madden 04 module must re-express it, and must
confirm whether disc-loaded rosters are checked at all (memcard/online-delivered ones
demonstrably are).

---

## 4. Textures and uniforms (deliverable e)

### 4.1 Yes, Madden 2004's art is MMAP — measured

**[M]** I ran the fork's `parse_mmap_header` over every member of eight art
containers. **5,776 MMAP headers parsed, zero failures**, with dimensions that look
exactly like textures and nothing else:

| Container | MMAP members | Failures | Dimensions |
|---|---|---|---|
| `UIS_PLYR.DAT` | 2,124 | 0 | 96×96 (2,123), 8×8 (1) |
| `UIS_MCFL.DAT` | 1,496 | 0 | 480×320 (748), 112×80 (748) |
| `COACFACE.DAT` | 501 | 0 | 128×128 (501) |
| `PLYRFACE.DAT` | 392 | 0 | 128×128 (392) |
| `UIS_TMLO.DAT` | 290 | 0 | 128×128 (289), 8×8 (1) |
| `UIS_SLIV.DAT` | 290 | 0 | 64×32 (289), 8×8 (1) |
| `COACHES.DAT` | 611 | 0 | 128×128 (366), 64×64 (244) |
| `FIELDART.DAT` | 72 | 0 | 128×128 (68), 1024×256 (4) |

**[M]** Header `version` splits 2 (4,280 members) / 1 (1,496 — all of `UIS_MCFL`).
That is the *same* version split the fork's `MmapHeader` docstring records for Madden
09's `UIS_MCFL`, so the wrapper is stable across the five-year gap.

**[M]** Disc-wide, 8,255 members classify as MMAP.

### 4.2 The one real divergence from Madden 09: there is no `UNIFORMS.DAT`

**[M]** Madden 09 keeps uniform art in `/DATA/UNIFORMS.DAT` (725 COMP members).
**Madden 2004 has no such file.** `UIS_UNI.DAT` exists but is a 256-byte TERF with a
single **empty** member — a stub.

**[A]** The uniform art is therefore distributed: `UIS_PLYR.DAT`'s 2,124 96×96 MMAPs
are the obvious candidate for kit/jersey texture pages, indexed by the `TUNI.UFID`
values (which reach 224, comfortably inside 2,124). `PLADATA.DAT` (756 MMAP + 74 DMF
models) is the other candidate. **This mapping — `UFID` → member index → texture — is
the single measurement that decides whether the Uniforms page is real on this title,
and it is not yet made.** It is the top item in `PRECHECKS-madden04.md`.

**[S]** The community hit the same wall from the other side: on footballidiot,
MMAP is named as the blocker for on-disc uniform edits, and **no public PNG→MMAP
converter exists**. The fork's own parser is explicit that *"Pixel format, palette
presence and mip count are not determined"* and hands those bytes back verbatim.
So: MMAP **inventory** is free; MMAP **pixel decode** is unsolved everywhere, by
everyone, and a Madden 04 module must not promise it.

### 4.3 PCSX2 texture packs for Madden 2004: none exist

**[S]** Searched thoroughly and the absence is real, not a search failure:
`PCSX2/pcsx2_patches` has zero files for SLUS-20752; ModDB's Madden NFL 2004 page
reports no mods and no files; the PCSX2 HD Textures Project index lists no Madden
entry; GitHub-wide, `SLUS-20752` appears in ~10 code paths, all metadata, savestates,
or one DNAS-bypass repo.

**[S]** But the technique is proven one year away, by the author of this repo's own
upstream. **antdroid (`antdroidx`)** ships:
- `github.com/antdroidx/Madden05NEXT` — **Madden NFL 2005 PS2, SLUS-21000**, updated
  rosters + "Updated Uniforms and Graphics" via PCSX2 texture replacement.
- `github.com/antdroidx/madden08next`, `madden06next`, and NCAA 06 NEXT (11,000+
  textures).

**[A]** Madden 2004 is the conspicuous hole in that lineup. Whether it was skipped
for a technical reason or for lack of demand is worth one question to that community
before committing to the uniform lane — it is the cheapest possible de-risking.

**Practical consequence.** PCSX2 texture replacement (dump to
`textures/SLUS-20752/dumps`, replace from `.../replacements`, hash-named PNGs) is the
route the community uses *precisely because* on-disc MMAP writing is unsolved. A
Madden 04 Studio should present the texture lane as **identify-and-organise** (map
MMAP members to the PCSX2 hashes a GS dump produces), not as on-disc pixel editing.
That requires a human with a controller — see `PRECHECKS-madden04.md` §H.

### 4.4 Community tooling that already claims Madden 2004 — use it as an oracle

**[S]** Two Windows editors advertise Madden 2004 support, both distributed as forum
binaries rather than source:

- **Madden Xtreme DB Editor (MXDBE)** — advertises *"Edit possible emulator console
  files. (2004 - 2020)"*; a developer post says *"Madden 04 - Madden 07 are supported
  so far"*. Handles the PS2 save wrapper automatically.
- **MaddenAmp** (`github.com/keylimesoda/MaddenAmp`, C#, still updated) — README:
  *"Supports to most extent, Madden 2004, 2005 & 2006"*. Ships per-year fixture
  directories including `04files/2004_Roster.ros` and `2004_Franchise.fra`.
- **NCAA-DB-Editor** (`github.com/antdroidx/NCAA-DB-Editor`) — the best-maintained
  *open-source* console TDB editor, built from MXDBE + MaddenAmp + Artem Khassanov's
  `tdbaccess`. NCAA-focused, but the clearest code reference.
- **DAT File Replacer (DFR)** — the community's actual TERF read/write tool; extracts,
  replaces **and appends** members, and exposes the `COMP` codec flag + decompressed
  size manually.
- **QuickBMS `madden_terf.bms`** (aluigi) — dispatches codec 0 stored / 1
  `TDCB_silence` / 5 `ea_madden`. **[S]** aluigi reversed codec 5 *from the Madden 2004
  demo* in 2018. That is the same codec the fork calls `LZH1` — reversed independently
  a second time, from the same game.

**Why this matters for the module:** MaddenAmp's `04files/` fixtures are a *free
cross-check oracle*. **[S]** Parsing them with this project's TDB spec yields `PLAY` at
**108-byte stride, 112 fields** — **[M]** the same stride and field count I measured on
the PS2 disc. A Madden 04 module's tests can assert those numbers without shipping any
copyrighted bytes.

**Two cautions.** (1) MaddenAmp and MXDBE work on **PC** `.ros`/`.fra` files; PS2 disc
TDBs are the same substrate but different packaging (§7.5). (2) **[S]** community
analysis of the PC 2004 franchise found `SLRI` with only **5 fields** (`SCAD SMAD SAMU
SAIP SIIP`) — **no `RFA1..RFA4`** tender tiers, unlike Madden 08's 9. Any
franchise-economy code carried over from `NCAA-Draft-Class-Editor` must not assume
those fields exist. The same source reports `SEAI.SEYR` at **bit offset 51, 6-bit
SINT — identical to Madden 08**.

---

## 5. The gameplay-patch story (deliverable d)

This is Madden 04's unfair advantage, and it exists for no other title in the fleet.

### 5.1 The patch library already exists, in MIPS, for this exact CRC

**[M]** `/mnt/c/GitHub/nfl-online-revival/patches/` holds 36 `.pnach` files. 34 are
named `14F8B841.*` — **the Madden 2004 PS2 CRC I measured in §1**. One is
`42F9D5AF.pnach` (2K5) and one is an unversioned candidate list.

**[M]** By subject, the `14F8B841` set covers: double-team blocking (`dt-hold-90`,
`dt-duration-10x`, `dt3-helper-assign`, `dt-market-guard-p1`, `c1-plus-doubleteam`
v1/v2), the playbook expansion family (`playbook-expansion` v1/v2/v3 ± full/nohook,
`playbook-save-limit`, `playbook-ui`, `playbook-ui-3digit`), the Wildcat family
(`wildcat-inject` ± nohook, `wildcat-menu`), formation sets (`setlist-enlarge`,
`sets-a1-fix`, `sets-caps`), AI (`pbai-purge-fix`, `n1-fold`, `dispatch`,
`motion-block-p8`, `t3-live`), and a set of diagnostics (`skates-diag-256x`,
`velocity-diag-p7`, `shedlock-p11`, `drive-p9/p10`).

**[S]** `nfl-online-revival` ships a consolidated `dist/14F8B841.pnach` described as
*"597 patch lines"*.

### 5.2 The translation problem does not exist here

The Xbox work in that repo needed x86 cave authoring because the Xbox build is the
same game compiled for a different ISA. **[S]** `docs/pnach-to-xbe-pipeline.md:920-922`
is blunt that the automated transcoder was never built — *"Specification only;
nothing built"* — and `:16-17`: *"A byte-level transcoder is impossible."*

**None of that applies to a PS2 module.** The patches are already MIPS R5900, already
addressed for `SLUS_207.52`, already in PCSX2's own `patch=1,EE,ADDR,word,VALUE`
syntax. **[S]** The fork's `_formats/ps2_elf` already parses and emits exactly that
syntax (`emit_pnach`, `parse_pnach`) and computes the CRC that names the file.
There is no porting step at all: the content is in the target format for the target
machine.

### 5.3 How it becomes `CodePatchLane` content

**[S]** The fork's `CodePatchLane` protocol requires `patches()`,
`translation(patch_id, parameters)`, `emit_pnach(patches, crc)` and
`verify_pnach(...)`. The 2K5 lane carries a 21-patch catalogue and pins
`RETAIL_PCSX2_CRC = "42F9D5AF"`. A Madden 04 lane is the same shape with
`RETAIL_PCSX2_CRC = "14F8B841"` and a catalogue re-expressed from the pnach files.

**[S]** The shipped `dist/14F8B841.pnach` is **597 patch lines / 597 distinct
addresses / 556 words landing in cave bands / 41 in-place hooks**, and the file itself
partitions its contents into `FIELD-PROVEN` (double-team blocking; 250 plays, the
freeze fix and memory-card saving; Wildcat injection into shipped team books) and
`REVIEWED BUT NOT YET LIVE-TESTED` (60 sets and the Create-Formation list; the 3-digit
counter fix; the Wildcat custom-book gate fix). **That partition should be carried
into the studio verbatim as per-patch provenance** — it is exactly the honesty the
fork's badge model wants, and it arrives for free.

**[S]** There is also a `pnach → ISO` path: `nfl-online-revival/docs/pnach-to-iso-pipeline.md`
plus `tools/bake_pnach.py` and `tools/patch_iso_elf.py` bake EE word-writes into the
boot ELF inside the image — turning a *pnach* (emulator-only) into a *patched disc*
(portable). Same shape as the fork's own `PS2_CODE_PATCH_PIPELINE.md`.

**Two hard constraints on that path, both measured by the owner and both good news for
a fixed-allocation studio:**

- **[S]** `pnach-to-iso-pipeline.md:152-153`: *"The tools are ready; **`patch_iso_elf.py`
  has never run against a real PS2 ISO**."* So the bake step is **specified and coded
  but unexercised** — budget for first-run friction (§9.3 already allows 1.5 d).
- **[S]** A *hand*-modified retail Madden 2004 ISO **has** booted under PCSX2
  (`docs/field-log.md:150-155`, `madden2004-pt2test.iso`, *"Game booted (PINE:
  SLUS-20752)"*). The same test settled a negative: PCSX2's `Elfheader.cpp`
  `LoadProgramHeaders()` is *"a pure logging routine"*, so **a second `PT_LOAD` segment
  is never mapped — the ELF cannot be grown**. Patches must be **same-size, in-place,
  inside the existing image**. That is precisely what `ps2_iso9660_writer.py` enforces
  anyway, so the constraint costs nothing and removes a whole class of design error.

### 5.4 What the studio would show

**[A]** A Gameplay page listing each patch as a `Target` with a short description and
a `bool`/`choice` field per tunable, and two outputs: (1) **Export `.pnach`** — write
`14F8B841.pnach` into PCSX2's `patches/` folder, the zero-risk path; (2) **Bake into
disc** — the `patch_iso_elf` route, which is a bounded fixed-allocation ELF write and
so can reach `offline-writer-proved`.

### 5.5 The honest caveat about the rung

**[S]** These patches are *witnessed*, but the witness is **unblinded operator
observation plus a PINE canary read**, in `nfl-online-revival`'s own harness — not a
controlled measurement, and not through this module. (That repo's own history shows a
blinded A/B retracting an unblinded "CONFIRMED", so treat `FIELD-PROVEN` as strong
evidence, not proof.) The fork's registry requires, for
`runtime-proved`, `runtime.status == "visible-proved"` with evidence files that exist
on disk, and `EA_TERF_FORMAT.md` records that promoting any on-disc writer above
`offline-writer-proved` *"needs the rig"*. So:

- Day one, honestly: **`extract-only`** (the studio composes and exports a pnach; it
  does not write the game).
- After a bounded ELF bake + verifier: **`offline-writer-proved`**.
- `runtime-proved` needs a rig boot, which is out of scope for an agent (§9).

**[A]** One caution I cannot resolve from here: the patches were authored against
*a* `14F8B841` image. My disc hashes `b6488caf…`; whether the patch author's image is
byte-identical is unverified. The CRC matching is strong evidence the *ELF* matches
(the CRC is computed over the whole ELF), so patch addresses should be valid — but
the module should pin `executable_sha256` and refuse anything else, which the contract
already makes it do.

---

## 6. The reuse table (deliverable c)

### 6.1 Provenance rule

None of the owner's source repos (`nfl-online-revival`, `ps2_madden_recomp`,
`NCAA-Draft-Class-Editor`) carries a `LICENSE` file. The fork does
(`ps2-lane/LICENSE`). So **nothing is copied**: each reuse below is a *fresh
expression* inside the fork, written from the measured format, with the origin
credited in the module docstring. **[S]** This is the precedent already set — the
fork's `ea_terf.py` says exactly that of its own LZH1 work, and
`EA_TERF_FORMAT.md` §10 credits `nfl-online-revival` as *"read-only reference on this
box; no licence file, so nothing was copied."* Follow that pattern verbatim.

### 6.2 What decodes what, and how it re-enters the fork

| Prior art | What it decodes for Madden 2004 | Status in the fork | Work to re-express |
|---|---|---|---|
| `nfl-online-revival/tools/lzh1.py` | LZH1 (codec 5) + RLE1 (codec 1) — **reversed from `SLUS_207.52` itself** | **Already done.** `_formats/ea_terf.py` carries both; cross-validated 3,309 members *"identical, 0 differing"* against `lzh1.py` **[S]** | **none** |
| `nfl-online-revival/tools/container_census.py` | the TERF walk + first-level format classifier | **Already done.** `ea_terf.parse_terf` / `identify_member` | **none** |
| `nfl-online-revival/tools/madden_tdb.py` | Madden 2004's `DB_TEAMS.DAT`, 232 members | **Partly.** `_formats/ea_tdb.py` exists but only in the Madden 09 worktree, and is LE-only (fine — PS2 is LE) | **0.5 d** to promote into the shared `_formats/` |
| `NCAA-Draft-Class-Editor` `MaddenTdb.cs` + `parse_madden_tdb.py` | the same TDB, independently. **[M]** Reads Madden 2004 unmodified | Not in the fork | Redundant with `ea_tdb.py` — use as the **cross-check oracle**, not a second port |
| `nfl-online-revival/tools/roster_checksum.py` + `docs/roster-checksum.md` | the 1,743-row zlib-CRC-32-seeded-with-row-count over `PLAY` where `TGID` 1..32; value `0x8108963c` **[S]** | Not in the fork | **1 d** — small, well-specified, and needed before any roster write is trustworthy |
| `nfl-online-revival` `patches/14F8B841.*` (34 files) | gameplay behaviour, in MIPS, for this CRC | Not in the fork | **2 d** to re-express as a `CodePatchLane` catalogue |
| `nfl-online-revival/tools/patch_iso_elf.py`, `bake_pnach.py` | pnach → patched boot ELF in the image | Fork has `_formats/ps2_elf` (`emit_pnach`/`parse_pnach`/`pcsx2_crc`) + `ps2_iso9660_writer.py` | **1 d** to wire the bake step |
| `nfl-online-revival` ELF function/cave maps | ~25 named PS2 function addresses, data globals, code caves **[S]** | Not in the fork, and **not needed** for a studio | skip — that is a gameplay-research asset, not an editor asset |
| `nfl-online-revival/docs/xbox-*.md` | the Xbox twin of the same game | irrelevant to a PS2 module | skip |
| **`ps2_madden_recomp`** | — | **[S]** targets Madden **08**, not 2004; 30,355 functions with **zero** game-specific names; its `tdb_tool.py` was measured **wrong** (assumes a 0x30-byte table header where the truth is 0x28); nothing runs; dormant since Jul 2026 | **skip entirely.** ~0 reusable input |

### 6.3 Madden 09 module: shared verbatim vs parameterised

**[S]** Read at 2026-09-05 11:56; that worktree is live and moving.

| Piece | Verdict for Madden 04 |
|---|---|
| `__main__.py` (8 lines) | **verbatim** |
| the `_registered()` fragment gate | **verbatim idiom** |
| `containers.py` `/DATA` walk, `classify`, `describe_container`, `load_container` | **near-verbatim**; only the named container constants change (Madden 04 has 51 containers vs 09's 107) |
| `containers.py` synthetic-disc builder | **verbatim** — built from `ea_terf`'s rules, copies nothing from a disc, so conformance runs with no ISO |
| `InventoryLane` (340 ln) | **near-verbatim** — it walks whatever `data_files()` returns |
| `TextLane` (285 ln) | **near-verbatim** |
| `TeamDataLane` (391 ln) | **near-verbatim, and now de-risked** — it needs EA TDB v8, which §3 proves Madden 2004 has |
| `disc_identity.py` `EDITIONS` map | **parameterise**, ~40 lines. Madden 04 has no Deluxe, so one entry |
| identity constants | **parameterise**: `SLUS-20752`, `SLUS_207.52`, `14F8B841`, the two digests I measured |
| `code_patches.py` shape | **share**; catalogue content is 100 % new — but for Madden 04 the content *already exists* (§5), which is not true for Madden 09 (**[S]** its lane ships `classification = "unknown"` with **zero** translations) |
| `mmap_art.py` (new, untracked, 21,915 B) | **watch, don't depend.** **[S]** It reframes MMAP as a table-of-tables (image / surface / palette / name tables) with `decode_rgba`, `encode_indexed`, `deinterleave_csm1` and an `lzm1_decompress`. If it lands and generalises, Madden 04's Uniforms page becomes real; if not, §4.2 stands |
| `registry.fragment.json`, `pins.json` | **do not copy.** **[S]** Madden 09's are still the scaffold placeholders, which is why **zero** of its four written lanes currently load |

### 6.4 The free substrate, itemised

**[S]** Available to a Madden 04 module with no new format work at all:

| Component | Covers |
|---|---|
| `mod_editor/games/contract.py` | the whole module/lane/target/plan/receipt/verdict vocabulary; frozen |
| `studio_qt.py` | **all 14 pages**, generic lane page, `Target.fields` → controls, honesty badges; frozen since RC86 |
| `chooser*.py`, `studio_service.py`, `lane_cli.py`, `conformance.py`, `scaffold.py`, `pins.py`, `fragments.py` | discovery, build+share, the 4-step lane CLI, ~55 generic conformance checks |
| `_formats/ps2_disc` | `Ps2DiscIdentifier` — parameterised by identity, **zero code** |
| `_formats/ps2_elf` | program headers, `pcsx2_crc`, `emit_pnach`/`parse_pnach`, `build_synthetic_elf` |
| **`_formats/ea_terf.py`** | the container, **its codecs reversed from this very disc's ELF** |
| `tools/ps2_iso9660.py` + `_writer.py` + `_verify.py` | reader, bounded fixed-allocation writer, independent verifier |

---

## 7. The remaining lanes (rest of deliverable f)

### 7.1 Playbooks — fully present, and large

**[M]** `/DATA/GAMEDATA.DAT` holds **64 TDB members** (67 of its 76 members are LZH1;
the TDBs decompress cleanly) carrying **19 playbook tables**:

| Table | In members | Total rows | **[A]** likely meaning |
|---|---:|---:|---|
| `PLYS` | 64 | 110,660 | play steps / segments |
| `PSAL` | 64 | 62,033 | player assignment language |
| `PBAI` | 64 | 36,531 | playbook AI weights |
| `SETG` | 64 | 24,677 | set groups |
| `ARTL` | 64 | 14,615 | route art |
| `SETP` | 64 | 13,695 | set personnel |
| `PBPL` | 64 | 10,066 | playbook → play links |
| `PLYL` | 64 | 10,060 | play list |
| `SGF`, `SPKG`, `PLCM`, `PLPD`, `SPKF`, `PLRD`, `PBST`, `SETL`, `PBAU`, `PBFM`, `FORM` | 64 | 624–6,793 | formations, speech keys, play descriptors |

**[S]** Cross-check: `nfl-online-revival/docs/xbox-data-layer.md:271-288` records the
same file as *"64 LZH1 TDB members, `FORM/SETL/PLYL/PLYS/PSAL/ARTL/PBPL/PBAI/PBST`;
totals **`PBAI` 36,531 rows, `PLYL` 10,060 rows**"*. **[M]** My independent counts:
`PBAI` 36,531, `PLYL` 10,060. Exact match — third independent confirmation of this
substrate.

**[S]** `nfl-online-revival` also has a deep playbook-semantics body of work
(`docs/psal-assignment-language.md`, `playbook-capacity.md`, `madden09-playbook-map.md`)
and the fork has `PLAY_*` docs from the 2K5 side. So a Playbooks page could go beyond
listing — but that is a research lane, not a wiring lane.

**Day-one rung: `extract-only`** (enumerate playbooks and plays, export the TDB rows).
Writing is gated on `GAMEDATA.DAT` being a `COMP` container: **[M]** 67 of 76 members
are LZH1, and **[S]** there is no LZH1 encoder anywhere public, so a rewritten member
is stored and the file grows — which the fixed-allocation ISO writer will then refuse.
That is the single biggest structural obstacle in the whole study (§9.1).

### 7.2 Text and menus — strings exist, schema does not

**[M]** Madden 04 is *unlike* Madden 09 here. Madden 09's module found 14,748 members
with `TEXT` magic; **Madden 2004 has 3 disc-wide**, and two of those are noise. The
one real hit is `/DATA/ONLINE.DAT` member 3 — 23,284 bytes of *"Madden NFL 2003 Online
Agreement"* legalese (a leftover from the previous year's build).

**[M]** But UI strings are definitely present, inside members the classifier calls
`unclassified`:

```
UIS_SETT.DAT :  'create player'  'view roster'  'breakdown'  'free agents'
UIS_MDRC.DAT :  'create player'  'view roster'
UIS_BANR.DAT :  'pro bowl'  'Completions:'  'Q.Carter'
UIS_POPS.DAT :  49 of 50 members carry printable runs
```

**[A]** These are EA's "UIS" = UI Screen containers; the per-member layout is a screen
description with embedded labels. The format is not identified by the fork's
`identify_member` and is not documented in any repo I read.

**Day-one rung: `read-only-mapped`** (a string census: which member of which container
holds which label). A writer needs either the UIS schema reversed or a
same-length-in-place string overwrite — the latter is how the 2K5 `TextLane` works and
is a plausible **1–2 d** follow-up, but it is genuinely new work.

### 7.3 Audio — the largest unknown

**[M]** Three containers, all TERF, all above the reader's 96 MB guard:
`SPCHDATA.DAT` (660 MB, **7,659 members**), `SOUNDDAT.DAT` (244 MB, 447 members),
plus `SPCHHDRS.DAT` (141 KB, 4,021 stored members — **[A]** an index into the speech
bank, given the 7,659 ↔ 4,021 relationship) and `STRMDATA.DB` (a bare 70-table EA TDB
— **[A]** the commentary/streaming database, and directly readable).

**[A]** The container is free; the *codec* inside the members is unmeasured. The 2K5
module's audio lane is the fleet's only `runtime-proved` row and it decodes PS2 ADPCM,
so the machinery exists — but nothing establishes that Madden 04's speech members are
the same encoding.

**Day-one rung: `read-only-mapped`** for `STRMDATA.DB` (a TDB we can read today) and
for a member inventory; **`unknown`** for the audio payloads until someone decodes one.
**[S]** The community does document a working soundtrack-swap workflow for NCAA/Madden
PS2 via the DAT File Replacer, so member replacement is at least known to work in
practice.

### 7.4 Stadiums, field art, models

**[M]** `STADIUMS.DAT` (1,052 members: 421 `SMF`, 4 `MMAP`, 106 empty),
`STADATA.DAT` (201: 119 `SMF`, 80 `MMAP`), `FIELDART.DAT` (716, **all LZH1**: 644
`SMF`, 72 `MMAP` including four 1024×256 banners), `PLADATA.DAT` (1,038: 756 `MMAP`,
74 `DMF`), `COACHES.DAT` (756: 611 `MMAP`, 144 `DMF`).

**[S]** `SMF`/`DMF` are static/dynamic mesh geometry and `EA_TERF_FORMAT.md:468` lists
them as *"not decoded anywhere here"*. **[S]** `nfl-online-revival` reached the same
wall: `PLADATA.DAT`'s payload *"remains unreversed on either platform."*

**Day-one rung: `read-only-mapped`** (member inventory + the MMAP textures inside).
Geometry editing is out of scope; texture-level stadium/field work rides the §4.3
PCSX2 route.

### 7.5 Memory-card saves — deliberately out of scope

The owner has stated that memcard save tooling is out of scope for these studios and
that **disc-based parity is the goal**. That is the right call here and the disc
supports it: **[M]** Madden 2004 ships its rosters, coaches, uniforms assignments and
playbooks *on the disc* (`DB_TEAMS.DAT`, `TEMPLATE.DAT`, `GAMEDATA.DAT`), so a
disc-only studio is not a reduced product — it is the whole product.

For the record on what does *not* carry across: `NCAA-Draft-Class-Editor` deals in
Madden 08/09/12 **memory-card** artifacts (`.max`/`.psu` containers, the 4-byte
`02 00 00 00` franchise preamble, the four franchise CRCs). **[M]** None of that
appears here — the on-disc TDB members have `preambleBytes = 0` and sit inside TERF,
not inside a PS2 save container. The *TDB substrate* carries over completely; the
*save-file packaging* carries over not at all. **[S]** The fork's `_formats/ps2_memcard`
is planned but not built.

---

## 8. What each shell page would edit, and its day-one rung

**[S]** All 14 pages always exist; a page with no lane shows *"No &lt;title&gt; lane in PS2
Madden 04 Studio yet."* plus the module's `page_notes` sentence. **[S]** Only lanes
classified `runtime-proved` / `offline-writer-proved` / `extract-only` /
`read-only-mapped` are drawn at all.

| # | Page | Madden 04 source | Day-one rung | Reachable next |
|---|---|---|---|---|
| 1 | **Uniforms & Equipment** | `TUNI` (assignment) + `UIS_PLYR` 96×96 MMAP (art) | `read-only-mapped` | `offline-writer-proved` for *assignment* (a 9-bit write in a stored TDB); art gated on MMAP pixels (§4.2) |
| 2 | **Names, Numbers & Faces** | `DB_TEAMS.DAT` 232 stored TDBs, 11,527 `PLAY`; `PLYRFACE` 392 faces | **`extract-only`** | **`offline-writer-proved`** — no compression in the way (§3.6); needs the roster checksum (§6.2) |
| 3 | **Text & Team Identity** | `TEAM` (`TDNA`/`TLNA`/`TSNA`) in every member; `UIS_TMLO`/`UIS_CTLO` logos | **`extract-only`** | `offline-writer-proved` — team names are byte-aligned strings in stored TDBs |
| 4 | **Field Art** | `FIELDART.DAT` 72 MMAP incl. 4×1024×256 | `read-only-mapped` | blocked: 100 % LZH1 container (§9.1) |
| 5 | **Stadiums** | `STADIUMS` + `STADATA` (`SMF` + MMAP) | `read-only-mapped` | geometry not decoded anywhere |
| 6 | **Presentation** | `UIS_SBLD`, `UIS_BANR`, `UIS_OMG` | `read-only-mapped` | with UIS schema |
| 7 | **Menus & UI** | ~25 `UIS_*` containers; strings present, schema unmapped (§7.2) | `read-only-mapped` | `offline-writer-proved` via same-length string overwrite, 1–2 d |
| 8 | **The Crib** | — (no Crib in Madden 04) | *empty page* | n/a |
| 9 | **Audio** | `SPCHDATA` 7,659 / `SOUNDDAT` 447 / `STRMDATA.DB` (TDB) | `read-only-mapped` (inventory + the TDB) | `unknown` for payloads |
| 10 | **Gameplay** | **34 existing `14F8B841` pnach patches** (§5) | **`extract-only`** (compose + export a pnach) | **`offline-writer-proved`** via ELF bake |
| 11 | **Playbooks & Plays** | `GAMEDATA.DAT` 64 TDBs, 19 tables, 110k `PLYS` rows | **`extract-only`** | blocked on LZH1 re-encode (§9.1) |
| 12 | **All Textures** | 8,255 MMAP members disc-wide, 5,776 header-parsed | **`read-only-mapped`** | `extract-only` once MMAP pixels decode |
| 13 | **Saves** | — (out of scope by decision, §7.5) | *empty page* | n/a |
| 14 | **Build & Share** | core-owned | free | — |

**Day one that means:** 4 pages carrying real `extract-only` lanes (Rosters, Identity,
Gameplay, Playbooks), 7 more at `read-only-mapped`, 2 honestly empty, 1 core-owned.
Compare Madden 09, whose four written lanes are all `read-only-mapped` plus one
`unknown` — **and which currently load none of them** (§6.3).

---

## 9. Risks, unknowns and effort (deliverable g)

### 9.1 The one structural obstacle: no LZH1 encoder

**[M]** 3,281 of Madden 04's 14,981 members are LZH1. **[S]** `ea_terf.py` decodes
LZH1 but `CODECS_ENCODED = (STORED, RLE1)` — there is no encoder in the fork, in
`nfl-online-revival` (`docs/lzh1-encoder-design.md`: *"No encoder was written"*), or
anywhere public (QuickBMS ships the decompressor only).

**[S]** `rewrite_member` therefore writes replacements **stored**, which is a shape
the game already loads — but costs ~3:1 in space. Chained with the ISO writer's
*"`len(new) <= entry.length` or the call fails"*, that means: **any container whose
members are mostly LZH1 is effectively read-only on disc.**

Which containers this kills, measured:

| Container | LZH1 share | Verdict |
|---|---|---|
| `FIELDART.DAT` | **716/716 (100 %)** | writes blocked |
| `COACFACE.DAT` | **501/501 (100 %)** | writes blocked |
| `GAMEDATA.DAT` (playbooks) | 67/76 (88 %) | writes blocked |
| `COACHES.DAT` | 543/756 (72 %) | writes mostly blocked |
| `PLADATA.DAT` | 774/1038 (75 %) | writes mostly blocked |
| `STADIUMS.DAT` | 437/1052 (42 %) | partially blocked |
| **`DB_TEAMS.DAT`** | **0/232 (0 %)** | **✅ free** |
| **`TEMPLATE.DAT`** | **0/12 (0 %)** | **✅ free** |
| **`UIS_PLYR` / `PLYRFACE` / `UIS_MCFL`** | **0 %** | **✅ free** |

**This is the finding that shapes the whole roadmap**: the highest-value lane
(rosters/coaches/uniform-assignment) sits entirely in the uncompressed containers,
and every blocked lane is a lower-value one. Madden 04 is lucky in exactly the right
place. **[A]** Writing an LZH1 encoder is a real project (deflate-adjacent, ~3–5 d
plus validation against 3,281 real members) and should be scoped separately — it
would unblock playbooks and field art here *and* the equivalent lanes on Madden 06/08/09/12
simultaneously, so it is a fleet-level investment, not a Madden-04 one.

### 9.2 Unknowns, ranked

| # | Unknown | Impact | Cost to resolve |
|---|---|---|---|
| 1 | **`TUNI.UFID` → which MMAP member** | decides whether the Uniforms page is real | **0.5 d**, read-only (`PRECHECKS` P7) |
| 2 | **MMAP pixel layout** | gates every art export/import | **[S]** possibly *already solved* — a 21.9 KB `mmap_art.py` appeared in the Madden 09 worktree on 2026-09-05 reframing MMAP as a table-of-tables with `decode_rgba`/`encode_indexed`. Unproven. **Watch it; don't fund it twice** |
| 3 | **Is the on-disc roster checksummed on load?** | gates roster writes | **[S]** the algorithm is documented and implemented in `nfl-online-revival`; whether a *disc* roster is verified needs a rig boot (human) |
| 4 | **UIS screen/string schema** | gates the Menus writer | 1–2 d |
| 5 | **Audio codec in `SPCHDATA`/`SOUNDDAT`** | gates Audio beyond inventory | 2 d, uncertain |
| 6 | **`QL01` preload duplication** | **[S]** `EA_TERF_FORMAT.md` warns `GAME.QKL`/`FE.QKL` *"carry byte-identical **packed** copies of members and directories, so an edit must be applied in both places."* **[M]** Madden 04 has both files, 9.7 MB and 6.9 MB | **1 d** — must be checked before *any* disc write ships, or edits will silently not take |
| 7 | Do the 34 pnach patches match *this* image? | gates the Gameplay lane's usefulness | 0.5 d (compare CRC + pin `executable_sha256`) |
| 7b | **[S]** `patch_iso_elf.py` has never been run against a real PS2 ISO | first-run friction on the bake step | covered in the 1.5 d estimate; the *hand*-equivalent is known to boot |
| 8 | `SMF`/`DMF` geometry | stadium/model editing | out of scope; unsolved everywhere |

**Risk #6 deserves emphasis.** It is the kind of thing that makes a writer look like
it worked and then does nothing in-game. It must be a pre-check, not a discovery.

### 9.3 Effort per lane, in agent-days

Assumes the module scaffold exists and the shared substrate is used as-is. Excludes
the human items in §9.4.

| Lane / task | Days | Confidence |
|---|---:|---|
| Scaffold + identity + `disc_identity` + `containers.py` for 51 containers | **1.5** | high — `games new` emits nine files; identity is measured in §1 |
| `InventoryLane` (textures page, 14,981 members) | **1** | high — near-verbatim from Madden 09 |
| Promote `ea_tdb.py` into shared `_formats/` | **0.5** | high |
| **`TeamDataLane`** — 232 members, 11,527 players, 128 coaches, 232 `TUNI` | **2** | high — §3 proves the format |
| **`CodePatchLane`** — 34 pnach → catalogue, export | **2** | high — content already exists in MIPS |
| `PlaybookLane` (read/export, 64 TDBs × 19 tables) | **1.5** | high |
| Text/menus string census lane | **1** | medium — schema unmapped |
| Stadium/field-art inventory lane | **1** | high |
| Audio inventory lane (+ `STRMDATA.DB`) | **1** | medium |
| Registry rows, `pins.json`, fragments, conformance, tests | **2** | high |
| Docs (`MADDEN04_PS2_MODULE.md`) + validators | **1** | high |
| **Subtotal — a complete read-only/extract studio** | **~14.5 d** | |
| *then:* roster **writer** + checksum + verifier | **+3** | medium — needs #3 and #6 resolved |
| *then:* uniform-assignment writer (`TUNI`) | **+1** | medium — needs #1 |
| *then:* menus string writer | **+2** | medium |
| *then:* pnach → ISO ELF bake + verifier | **+1.5** | high |
| **Subtotal — writers to `offline-writer-proved`** | **+7.5 d** | |
| *separately, fleet-level:* LZH1 encoder | **+3–5** | low-medium — unblocks 5 titles at once |

**Headline: ~14–15 agent-days to a complete read/extract Madden 04 Studio; ~22 to one
with proved offline writers on the lanes that matter.** For comparison the shared
substrate this rides on — contract, shell, `ea_terf`, `ps2_elf`, `ps2_disc`, the ISO
reader/writer/verifier — represents *months* of work already done.

### 9.4 Where a human is unavoidable

Agents cannot do these; they are listed separately in `PRECHECKS-madden04.md` §H.

1. **A GS dump for PCSX2 texture identity.** Mapping MMAP members to the XXH3 hashes
   PCSX2 names replacement PNGs by requires *running the game* and dumping textures.
   No amount of static analysis produces those hashes.
2. **An in-game witness for any writer.** **[S]** The registry will not grant
   `runtime-proved` without `runtime.status == "visible-proved"` and evidence files on
   disk; `EA_TERF_FORMAT.md` states the boot test *"needs the rig."*
3. **The `QL01` question, in practice.** Static analysis can show the duplication;
   only a boot proves whether an edit took.
4. **[A] One question to the NCAA/Madden NEXT community** (antdroid — author of this
   repo's own upstream, and shipper of `Madden05NEXT` for the adjacent year): *was
   Madden 2004 skipped for a technical reason, or for lack of demand?* Cheapest
   possible de-risking of the whole art lane.

### 9.5 Things that are NOT risks, contrary to expectation

- **"A 2003-era disc might use an older container."** **[M]** It does not: same
  `TERF`, same version word `02020005`, same three chunk chains, 0 layout violations
  across 14,981 members.
- **"The TDB might predate v8."** **[M]** It does not: `DB` v8, and `DCHT`/`INJY` are
  bit-for-bit identical to Madden 08's. **[S]** This closes an open question in the
  fork's own roadmap (`MULTI_GAME_INTERFACES_PLAN.md:190`, *"Madden 04 PS2 | S ? (TDB
  era unconfirmed — measure)"*, and step 11 at `:537`, *"TDB probe … then parameterise
  or stop"*). **The probe is done; the answer is parameterise.**
- **"An unknown codec might appear."** **[M]** None does — 0 unknown codecs, 0 refusals.
- **"Madden 04 might be a 2352-byte raw-CD rip."** **[M]** It is a 2048-byte DVD image
  with 0 slack, 0 aliased extents, `writable_geometry: true`.

---

## 10. Recommended order (deliverable h)

### 10.1 Should Madden 04 precede or follow Madden 09?

**Recommendation: start Madden 04 now, in parallel, but land it *after* Madden 09
lands — and use Madden 04 to fix the thing Madden 09 got stuck on.**

The case for parallel-not-serial:

1. **They share the substrate, and Madden 04 exercises it harder.** **[M]** Madden 04
   is 51 containers to Madden 09's 107, but has a *richer* data layer for a studio:
   coaches on disc, 199 classic teams, playbooks in 64 readable TDBs.
2. **[S] Madden 09 is currently blocked on presentation, not on format.** Its four
   lanes are written and complete in code, but **none load**, because
   `registry.fragment.json` and `pins.json` are still the scaffold placeholders. That
   is a one-day fix, and it is the *same* fix Madden 04 will need — solving it once on
   Madden 09 makes Madden 04's version free.
3. **Madden 04 has content Madden 09 does not.** **[S]** Madden 09's `CodePatchLane`
   ships `classification = "unknown"` with **zero** translations because no catalogue
   exists. **[M]** Madden 04 has 34 authored, MIPS-native, correctly-CRC'd patches
   sitting on this machine. Madden 04 is the title that makes the Gameplay page *real*
   for the first time on any Madden.
4. **The MMAP verdict is a shared dependency.** Whatever `mmap_art.py` concludes
   applies to both. Do not duplicate that work in a Madden 04 module.

**But do not start Madden 04's module code until Madden 09's fragment/pins pattern is
settled**, or you will copy a half-finished idiom into a second module.

### 10.2 The order

| Step | What | Days | Gate to clear |
|---|---|---:|---|
| **0** | Run `PRECHECKS-madden04.md` P1–P8 (all read-only, all agent-doable) | **0.5** | none — do this first |
| **1** | Let Madden 09 finish its registry fragment + pins and prove the idiom | — | not Madden-04 work |
| **2** | `games new madden04_ps2` + identity + `containers.py` + `InventoryLane` | 2.5 | step 1 |
| **3** | Promote `ea_tdb.py` to shared `_formats/`; **`TeamDataLane`** (rosters + **coaches** + `TUNI`) | 2.5 | step 2 |
| **4** | **`CodePatchLane`** from the 34 pnach files, export-only | 2 | step 2 |
| **5** | `PlaybookLane`, stadium/field-art, audio, text census lanes | 4.5 | step 3 |
| **6** | Registry rows, pins, fragments, conformance, tests, module doc | 3 | steps 2–5 |
| **7** | **Ship the read/extract studio** | — | ~14.5 d cumulative |
| **8** | Roster writer + checksum + verifier (needs P6 `QL01` + a rig boot) | +3 | human witness |
| **9** | `TUNI` writer, menus writer, pnach→ISO bake | +4.5 | — |
| **—** | *(separate, fleet-level)* LZH1 encoder → unblocks playbooks + field art on 5 titles | +3–5 | own scoping |

### 10.3 Why Madden 04 is the right second Madden

If the fleet can only afford one more Madden after 09, it should be **04, not 08 or 12**:

- **[M]** It is the only Madden whose ELF the owner has already reverse-engineered in
  depth, with a shipping patch library keyed to its exact CRC.
- **[M]** It is the only Madden with **coaches on the disc in a readable table** —
  answering an open workstream in the owner's own project memory.
- **[M]** Its roster containers are 100 % uncompressed, so it is the Madden where an
  *offline-writer-proved* roster lane is cheapest.
- **[S]** Its codecs were reversed from its own executable, so the container layer is
  not merely compatible — it is native.
- **[S]** The community gap is real (no PS2 texture pack, no released tooling for
  SLUS-20752) while the adjacent year (`Madden05NEXT`) proves the audience exists.

---

## 11. Method, scope and cleanup

**[M]** Everything measured here came from five read-only commands documented in
`PRECHECKS-madden04.md`, run against `/mnt/c/Roms/PS2/Madden NFL 2004 (USA).iso` and
against fixtures already in `/mnt/c/GitHub/NCAA-Draft-Class-Editor`.

- **No git worktree was modified.** No file in `ps2-lane`, `rc87-madden09`,
  `nfl-online-revival`, `ps2_madden_recomp` or `NCAA-Draft-Class-Editor` was written,
  staged or committed.
- **The rig was never contacted.** No `ssh`, no emulator, no VR check needed.
- **Payloads were deleted.** Four TDB members (~440 KB) were extracted to
  `scoping/work/ex/` for the §3 measurements and removed afterwards; only the
  ~2.5 MB of JSON *inventory* (`scoping/work/terf/*.json`, no game content) and one
  334 KB parsed table dump remain, both under the scoping directory.
- **Nothing large was extracted.** The four containers over 96 MB were header-probed
  (64 bytes each), never read whole.

### Confidence summary

| Claim class | Confidence |
|---|---|
| Identity facts (§1) | **[M]** measured twice, cross-checked against `nfl-online-revival/docs/binary-identity.md` |
| Container inventory (§2) | **[M]** reproduces the fork's own `EA_TERF_FORMAT.md` §8 Madden 2004 row *exactly* (51 / 14,981 / 11,700 / 3,281 / 0 / 0) |
| TDB substrate (§3) | **[M]** measured on the disc, **[S]** independently corroborated twice (`xbox-data-layer.md`; MaddenAmp PC fixtures) |
| MMAP inventory (§4.1) | **[M]** 5,776 headers, 0 failures |
| MMAP *pixels* (§4.2) | **[A]** unsolved — do not promise |
| Gameplay patches (§5) | **[M]** CRC match measured; **[A]** image-identity match unverified |
| Effort (§9.3) | **[A]** estimates, medium confidence |
