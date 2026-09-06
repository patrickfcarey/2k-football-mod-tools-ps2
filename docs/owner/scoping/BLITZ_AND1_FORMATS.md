# The Midway Blitz discs and AND 1 Streetball — what their containers are made of

> Written 2026-09-06 against the five discs on the NAS, with
> `tools/owner/ea_disc_map.py` (`ea_disc_map/v3`) extended to read them. **Read-only:
> no image was written, copied, renamed or moved; nothing was extracted to disk.**
> Sources: `<SERIAL>.<label>.map.json` / `.map.md` under `/turret/builds/2k5/maps/`
> and `docs/owner/disc_maps/`. Every count below is copied from those maps.
>
> **Evidence tags, used on every load-bearing claim:**
> **[M]** measured — the mapper read it this session and the identity it predicts holds.
> **[S]** sourced — a published format the citation names.
> **[A]** assumed — inference from a name. Treat as a question, not a fact.

---

## 1. Why this study exists

The disc census could open every EA and Visual Concepts disc in the fleet and left five
discs as lists of unknown magics: two `504b0304` + a nameless `.ZIH`, a `4d576f33`, a
` KAP`, an `11111111`, two headerless sound banks, 2,119 files beginning `EFS ` and 59
`VAGp`. A census that reports `other:45465320 × 2119` has not measured a disc; it has
measured its own blind spot.

This study says, per family: **what the container is** (the fields, and the identity that
proves each one), **what it holds** (asset kinds with counts), **what stays unknown**, and
**what a game module for it would need**. The rung column is today's, never a future one.

## 2. The five discs [M]

| disc | serial | image bytes | files | boot ELF sha256 (first 16) | PCSX2 CRC |
|---|---|---:|---:|---|---|
| NFL Blitz 2002 (USA) | SLUS-20051 | 1,464,205,312 | 36 | `d165b3c8bdd90548` | `3A32FD60` |
| NFL Blitz 2003 (USA) | SLUS-20474 | 1,029,144,576 | 22 | `57cba3a86145a8c3` | `49A00204` |
| NFL Blitz Pro (USA) | SLUS-20631 | 3,608,838,144 | 72 | `60ef9c5977224575` | `52922787` |
| Blitz: The League (USA) | SLUS-21128 | 2,328,985,600 | 112 | `e4fad3801f64311c` | `5AD4E46F` |
| AND 1 Streetball (USA) (v1.03) | SLUS-21237 | 4,588,797,952 | 2,365 | `5d83679ed331e92a` | `A542271D` |

None of the five holds a `TERF` container, an EA `BIG` archive or an EA `TDB` database [M].
Nothing in this toolchain's EA stack carries over. Everything below is a new reader.

## 3. Headline findings

1. **NFL Blitz 2002 and 2003 keep the whole game in one ZIP, stored, with a pre-built
   index beside it.** 2,426 and 2,695 entries, compression method **stored for every single
   one** [M]. The `.ZIH` next to it is that ZIP's central directory rewritten for fast
   seeking; its offset column points at each member's **data**, one local file header past
   the signature. All 64 sampled offsets on each disc land on a `PK\x03\x04` header whose
   stored name equals the index's name, and on Blitz 2002 all 8 sampled CRC-32 fields
   recompute over the stored bytes [M]. Nothing about this index is inferred.
2. **The Blitz asset naming is RenderWare.** 761 (2002) and 840 (2003) `.rtd` members carry
   RenderWare section id **0x16, texture dictionary**, and their own section-length word plus
   12 accounts for the whole member — so the label is earned, not read off a constant [M].
   The 1,272 / 1,436 `.dff` members begin with id 0x10 (clump) but do **not** satisfy that
   length rule, so the map leaves them as their raw magic [M].
3. **Blitz Pro and Blitz: The League moved to a Midway `PAK ` pack whose object locator we
   do not have.** The pack's own arithmetic is exact — body bytes plus metadata offset is the
   file, on both discs [M] — and its metadata names every top-level object by category and by
   a 32-bit hash that reproduces the object's hexadecimal filename [M]. What is missing is the
   step from a named object to its bytes: **no header word of either disc is an offset into
   the pack body** [M]. That, and nothing else, is what blocks a module for these two.
4. **AND 1 Streetball is the most completely read of the five.** Its 2,119 `EFS ` archives
   are a plain directory of (name offset, data offset, size, size, flags); the last member's
   end is exactly the file's length in **2,119 of 2,119** [M]. 7,197 of its 7,200 `.HDR`
   member sub-directories satisfy `entry-table offset + entries × 16 == first member offset`
   (the other 3 declare no entries) [M].
5. **The audio on all five is Sony PS-ADPCM, and on AND 1 it is loose and documented.** The
   Blitz sound banks end on the canonical `00 07` + fourteen `0x77` PS-ADPCM terminator frame
   [M][S]; AND 1's 59 `.VAG` files satisfy `declared data bytes + 48 == the file` every time,
   52 at 44,100 Hz and 7 at 22,050 [M].

## 4. Family by family

### 4.1 The ZIP + `.ZIH` pair — NFL Blitz 2002 and 2003

| field | where | measured how |
|---|---|---|
| `u32 entries`, `u32 body bytes` | `.ZIH` +0, +4 | `body + 8 == the file`, both discs [M] |
| record, *inline* shape (2002) | nine `u32` then a NUL-terminated name | the walk consumes the file to its last byte [M] |
| record, *table* shape (2003) | `u32 name offset` (from +8), `u32 size`, `u32 data offset`, then one string table | the first name offset equals `entries × 12`, i.e. the directory's own length [M] |
| CRC-32 (inline shape only) | word 5 | recomputed over the stored bytes of the 8 smallest entries: 8 of 8 agree [M] |
| MS-DOS time / date | words 3, 4 | word 4 decodes as 2002-01-12 on Blitz 2002 [M] |
| data offset | word 8 (inline) / word 2 (table) | `offset − 30 − len(name)` is a `PK\x03\x04` local header carrying the same name: 64 of 64 sampled, both discs [M] |

**What it holds** [M], Blitz 2002 / Blitz 2003:

| extension | 2002 | 2003 | what it is |
|---|---:|---:|---|
| `.dff` | 1,272 | 1,436 | RenderWare clump / model, section id 0x10 [S], length rule does not hold [M] |
| `.rtd` | 761 | 840 | RenderWare texture dictionary, id 0x16, length rule holds [M] |
| `.wip` / `.wom` / `.wmp` | 190 | 209 | members beginning `WIFF` [M]; a Midway container, unread [A] |
| `.cap` | 85 | 88 | members beginning `HTPC` [M]; unread |
| `.trv` / `.ini` / `.tab` | 72 | 74 | plain ASCII text members [M] |
| `.rsc` | 36 | 37 | members beginning `RYWM` [M]; unread |
| `.ban`, `.asd`, `.ico`, `.ms2`, `.rst` | 10 | 11 | a handful each; `blitz2.ico` and `midway.ico` read as PS2 save icons [M] |

**Where a modder's data is.** `roster.rst` is a single named entry inside the ZIP on both
discs [M] — the only entry whose name says roster. `field.tab` and the 31–32 `.ini` members
are plain text [M]. Uniforms and kit art are in the `.rtd` texture dictionaries [A: from the
extension and the verified RenderWare id, not from pixels]. Audio is `mslasset.ms2`, one
entry [M]. **Nothing in the ZIP has been decoded past its first sixteen bytes.**

**Rung today: `read-only-mapped`.** Every entry is named, sized, located and checked; none
is decoded. Lifted by decoders for the members' own formats.

**What a module would need.** A ZIP reader (stdlib), then a `.rst` reader before any roster
page exists, and a RenderWare texture-dictionary decoder before any texture page does. A
writer is unusually cheap here *because every member is stored*: a same-length member can be
replaced at its own byte range, and a different length rewrites the ZIP central directory and
**the `.ZIH` index, which carries the same numbers** — that is a three-place edit exactly like
the EA `QL01` rule, and forgetting the third place is the way to break the disc quietly [M].

### 4.2 `MWo3` overlays — Blitz Pro, Blitz: The League

64-byte header, then two segments. `64 + segment1 + segment2` is exactly the file's length on
**all four** overlays across the two discs [M]. The `load` word is a PlayStation 2 main-memory
address (`0x00493c00` on Pro, `0x0079e600` on The League) and the payload after the header is
R5900 code [M]. Two trailing addresses lie in the same range; on three of the four they are
equal to each other and to `load + file bytes`, and on `OVERLAY1.BIN` they are not — so the map
prints them as `address1` / `address2` and names them nothing [M].

**Rung today: `unknown (code-patch scaffold)`.** Raw code at a fixed address. A change here is
a code patch, not a data edit.

### 4.3 The Midway `PAK ` pack and its `0x11111111` metadata — Blitz Pro, The League

The tag is `'PAK '` written as a little-endian `u32`, so it reads ` KAP` in the bytes [M] —
the same CPU-native-word convention this toolchain already documents for PS3 big-endian TDB
table names, in the other direction.

| field | Blitz Pro | The League | measured how |
|---|---:|---:|---|
| body bytes | 417,093,632 | 505,677,824 | `body + metadata offset == the file` [M] |
| metadata offset | 2,048 | 2,048 | the bytes there begin `0x11111111` [M] |
| header words 1 / 3 / 4 | 512 / 272 / 192 | 512 / 960 / 708 | unexplained; **neither is an offset into the body** [M] |

The metadata is `u32 0x11111111`, `u32 records`, then one 2,048-byte slot per record. On The
League the same block also exists as a loose file, `RESMETA.LF`, whose length is exactly
`8 + 55 × 2048` [M]. Each slot begins `0x22222233`, carries a 32-bit name hash at +4 and the
constant 2,048 at +8, and ends with three `u32` string lengths followed by that many
NUL-terminated strings: a category word and an `objects\<hex>.of` path. **The hash equals the
path's hexadecimal stem in 14 of 14 records on Pro and 55 of 55 on The League** [M].

**What it holds** — the category words, verbatim from the map [M]:

* **Blitz Pro (14):** `Anim`, `CaP`, `Character`, `Databases`, `EnvLightMap`, `Formations`,
  `Misc`, `Playbooks`, `Plays`, `Scripts`, `Shell`, `Stadium`, `playsprites`, `screensets`.
* **Blitz: The League (55):** `anim`, `cheer`, `coach`, `databases`, `images`, `misc`, `nis`,
  `playbooks`, `player`, `prop`, `screens`, `screensets`, `shell`, and 42 `stadium_*` words.

**Where a modder's data is.** By its own category words: rosters and team data under
`Databases` / `databases` and `player` / `coach`; plays under `Playbooks`, `Plays`,
`Formations`; art under `images`, `screens`, `Shell`, `EnvLightMap` and the `stadium_*` set
— the words are [M], what each category holds is [A]. This is the strongest name-level
evidence on any of the five discs, and it is still only names.

**Rung today: `unknown`.** Not `read-only-mapped`: the reader can name every top-level object
and cannot locate one. Lifted by whatever turns a named object into a byte range — the
`.of` object header, a table the boot ELF builds at load time, or a second index this pass did
not find. **Until then no page for these two discs can be filled and no writer can exist.**

### 4.4 The Midway sound banks — `BLITZ04.MS2` / `.MS4`

24-byte header whose fifth word is the file's own length — that is what identifies the format,
and the map refuses anything where it does not hold [M]. Then 12-byte `(id, offset, size)`
records, then a name table of `.mst` names inside the declared directory bytes [M].

| disc | declared records | read | empty slots | last member ends at EOF | name table |
|---|---:|---:|---:|---|---|
| Blitz Pro | 11,407 | 11,406 | 0 | yes | 15,238 B, 1,706 `.mst` names [M] |
| The League | 9,366 | 9,365 | 144 | yes | 70,674 B, 2,469 `.mst` names [M] |

On both discs the declared count over-runs the table by exactly one record into the name
table, and the last record that *is* a record ends on the file's last byte [M]. The file ends
with `00 07` and fourteen `0x77` bytes — the Sony PS-ADPCM end frame [M][S].

The League's `BLITZ04.MS4` (286,195,712 bytes) does **not** satisfy the header rule and is
left unclassified [M]. It is a second bank in some other shape [A].

**Rung today: `read-only-mapped`.** Lifted by a PS-ADPCM decoder. Never a writer without one.

### 4.5 `BLITZOPT.OBF` — the Midway tuning tree

Two-byte header, then tagged records: `0x0F` opens a section (two length-prefixed strings,
parent path and name); `0x0E` is one setting (section path, name) followed by a `u32` type and
four 4-byte values — value, minimum, maximum, step. Type 1 reads as an integer and type 2 as
a float [M]. **The walk consumes both files to their last byte**: 8,201 of 8,201 on Pro and
7,800 of 7,800 on The League [M].

| disc | sections | settings | types |
|---|---:|---:|---|
| Blitz Pro | 33 | 103 | int 83, float 20 [M] |
| The League | 34 | 99 | int 79, float 20 [M] |

This is the one non-EA format on these discs that is **completely read**. Every section, every
setting, every value, minimum, maximum and step.

**Rung today: `read-only-mapped (schema + rows)`.** Lifted by a writer with an independent
verifier — and a writer is genuinely small here, because the record is fixed-shape and the
file has no checksum, no index and no length prefix to keep consistent.

### 4.6 `EFS ` — AND 1 Streetball

16-byte header (`"EFS "`, first data offset, entries, `0xFFFFFFFF` on every one of the 2,119
files [M]), then 20-byte entries — name offset, data offset, size, the same size again, flags
— then the name table, then the members.

| identity | result |
|---|---|
| `16 + entries × 20` fits before the first data offset | 2,119 of 2,119 [M] |
| every member's `offset + size` inside the file | 2,119 of 2,119 [M] |
| the two size words agree | every entry, all 9,966 [M] |
| the last member's end equals the file's length | 2,119 of 2,119 [M] |
| entry flags | `0` on all 9,966 [M] |

Ten members are themselves `EFS ` archives (the `ANIM_*.EFS` inside `/AND1/EFS/ANIMS/CHARS/`),
walked one level down [M]. 7,200 members begin `.HDR` and are a second directory of their own:
`u32 entries`, `u32` where the table starts, `u32 0x80000000`, then `char[8]` space-padded
names with a `u32` offset each. `entry-table offset + entries × 16 == the first member's
offset` holds for **7,197**; the other 3 declare no entries [M]. The table offset is 32 for
most members and 20 inside every `.BOB` — read it from the header, never assume it [M].

**What it holds** — member extensions across all 2,119 archives [M]:

| extension | count | first four bytes [M] |
|---|---:|---|
| `.DIM` | 5,389 | `.HDR` — a directory of named sub-blobs |
| `.PPD` | 1,239 | `.HDR` |
| `.FAD` | 785 | `28000000` / `21000000` / `03000000` |
| `.EAF` | 658 | `BALL` (565) and `.HDR` (93) |
| `.QBO` | 521 | a family of `xx8x5786`-shaped heads |
| `.FPR` / `.FNR` / `.BIM` / `.BOB` / `.BNK` | 489 | `.HDR` |
| `.SPF` | 117 | plain ASCII text (65 of them) |
| `.NIS` | 116 | `NIS0` |
| `.UIO` | 84 | `SCR\x00` |
| `.CNT` | 46 | `CONT` |
| `.HD` | 45 | `VB__` (30) and Sony `IECS` sound headers (15) |

Archives are grouped by directory: `CHARS/GLOBAL` 724, `TT` 400, `FRONTEND` 107, `NIS` 65,
`TITLE` 65, `TITLE_F` 64, `TITLE_S` 64, `OBJECTS` 39, `BACKEND` 23, and 17–20 per court under
`COURTS/LEVEL*` [M].

**Where a modder's data is.** Player and team art under `CHARS/`, `OBJECTS/` and the `.DIM`
directories; UI under `FRONTEND/` and `BACKEND/`; courts under `COURTS/LEVEL*`; cut-scenes
under `NIS/`; audio in the `.HD` + `.BIN` pairs under `EFS/SFX/<city>/` (a Sony SCEI sound
header and its body) and in the 59 loose `.VAG` files under `EFS/VB/` — the paths and magics are [M], what each
*is* is [A]. There is no file on this disc whose name says roster, and the
only loose text file is a 130-byte `/MESSAGE.TXT` [M].

**Rung today: `read-only-mapped`.** Every archive and every member is named, located, sized
and checked. Not one member is decoded. Lifted by decoders for `.HDR`-shaped members and for
`BALL` / `NIS0` / `SCR` blobs.

**What a writer would need.** Almost nothing structural: the directory is a flat table and the
last member ends at EOF, so a same-length member can be replaced without moving anything, and
a different length rewrites every later data offset in the same table. There is no checksum,
no index file and no preload copy to keep in step [M]. The work is entirely in the member
formats.

### 4.7 Sony `VAGp` — AND 1 Streetball

59 loose streams under `/AND1/EFS/VB/` [M]. Sony's documented 48-byte header: big-endian
version, data bytes, sample rate, then a 16-character name [S]. `data bytes + 48 == the file`
for **59 of 59** [M]. Version `0x00000020` on all 59; 52 at 44,100 Hz and 7 at 22,050 [M];
byte `0x1E` — the channel count in the variants that carry one — reads 0 on all 59, the
single-channel default [M][S: as vgmstream reads it].

**Rung today: `read-only-mapped`.** Lifted by a VAG decoder; never a writer.

## 5. What a module for each family would need

| family | discs | smallest honest module | blocked on |
|---|---|---|---|
| ZIP + `.ZIH` | Blitz 2002, 2003 | a Text page from the `.ini` / `.trv` / `.tab` members, and All Textures once a RenderWare texture-dictionary decoder exists | a `.rst` reader before any roster page; a `.dff` / `.rtd` decoder before any art page |
| `PAK ` + metadata | Blitz Pro, The League | **none today** | the object locator (§4.3): a named object cannot be turned into a byte range |
| Midway sound bank | Blitz Pro, The League | an Audio page listing records | a PS-ADPCM decoder to play or replace one |
| `.OBF` | Blitz Pro, The League | a Gameplay-tuning page, schema + rows, today | a writer + verifier to make it editable |
| `EFS ` | AND 1 | All Textures / Menus pages once `.HDR` members are decoded | the member formats, not the archive |
| `VAGp` | AND 1 | an Audio page listing streams | a VAG decoder |

## 6. What stays unknown

1. **Where a `PAK ` object's bytes are.** The one finding that blocks two whole discs (§4.3).
2. **What a `.dff` is on the Blitz discs.** The first word is RenderWare's clump id but the
   section-length rule fails on all 2,708 of them across the two discs [M]. Either Midway
   wrote a variant or the id is a coincidence; the map does not choose.
3. **`WIFF`, `HTPC`, `RYWM`, `BAKE`** — 315 and 339 ZIP members whose four-byte heads are the
   only thing read [M].
4. **`BALL`, `NIS0`, `SCR\x00`, `CONT`, `VB__`** and the numeric heads on `.FAD` / `.QBO` /
   `.VIS` / `.CYC` — AND 1's member formats. Of AND 1's 9,966 members the mapper names the
   container shape of 7,200 (`.HDR`) and 10 (nested `EFS `) and reads the first four bytes of
   the rest [M].
5. **`BLITZ04.MS4`**, 286,195,712 bytes, which fails the sound-bank header rule [M].
6. **The `MWo3` trailing addresses**, and the `PAK ` header's second and third counts [M].

## 7. How to reproduce this

    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --iso "<image>" --out <dir> --label "<Title> (USA)"
    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --page <dir>/<SERIAL>.<label>.map.json
    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --selftest        # 89 checks, synthetic bytes only

All five discs map in **under five seconds together** on the NAS [M]. The readers are in
`tools/owner/ea_disc_map.py`; their tests are `MidwayAndAnd1Tests` in
`tests/owner/test_ea_disc_map.py`.
