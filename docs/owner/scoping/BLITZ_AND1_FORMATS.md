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
>
> **Revised the same day, 2026-09-06:** the `PAK ` object locator was found — the pack's last
> 2,048 bytes are a directory — and the pack's databases and `SEC ` containers are read. §3 item 3,
> §4.3, §5, §6 and §7 carry the revision; every other section is as first written.

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
3. **Blitz Pro and Blitz: The League keep everything in one Midway `PAK ` pack, and it is
   located three formats deep.** The pack's last 2,048 bytes are a directory whose leaves carry
   the byte range of every object — 14 on Pro, 57 on The League, two of which the metadata list
   omits — and those ranges tile the body from the first sector after the metadata to the
   directory itself [M]. The two "unexplained" header words are that directory's node-table and
   name-table lengths [M]. Inside, 5,605 and 7,409 members are each named by their own record
   and checked against the entry that points at them; 48 of 49 and 311 of 311 `.dbd` databases
   walk to the byte against their `.dbs` schemas (the roster is `playerdb.dbd`, 3,628 and 695
   player rows), and all 1,104 `SEC ` play and scene containers on The League list their
   sections [M]. What stays unread is what a RenderWare or `WIFF` member *shows* (§4.3).
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

### 4.3 The Midway `PAK ` pack — Blitz Pro, The League — located, and read three formats deep

The tag is `'PAK '` written as a little-endian `u32`, so it reads ` KAP` in the bytes [M] —
the same CPU-native-word convention this toolchain already documents for PS3 big-endian TDB
table names, in the other direction. The readers are product code:
`mod_editor/games/_formats/midway_pak.py` (the pack), `midway_db.py` (the databases) and
`midway_sec.py` (the section containers), specified in `docs/product/MIDWAY_PAK_FORMAT.md`;
the mapper imports them and quotes their identities.

**What the pack is** [M]. A read-only file-system image in four parts: a 24-byte header padded
to a sector; the `0x11111111` metadata list at 2,048 (one 2,048-byte slot per listed object,
each slot a byte copy of that object's own header record — 14 of 14, 55 of 55); the objects,
each a sector-aligned `objects\<hex>.of` file laid down in the lexicographic order of its
hexadecimal name; and, in the **last 2,048 bytes, a directory** of 16-byte nodes
`(name offset, kind, offset, size-or-count)` rooted at 0 — a directory `objects` whose leaves
are the object files and a file `resmeta.lf` whose range is exactly the metadata region.
This is how the first reading's two unexplained header words resolved: **word 3 is the node
table's length and word 4 the name table's** (padded to 4), on both discs.

| identity | Blitz Pro | The League |
|---|---:|---:|
| body bytes + metadata offset == the file | 417,093,632 + 2,048 | 505,677,824 + 2,048 |
| objects located by the trailer directory | 14 | 57 (55 listed + `3a36d186.of`, `eee81757.of`) |
| first object is the first sector after the metadata; objects tile to the directory | yes; yes | yes; yes |
| node table bytes == header word 3; name table bytes == header word 4 | 272; 192 | 960; 708 |
| `resmeta.lf` leaf == the metadata region; slots that are byte copies of the object record | yes; 14 of 14 | yes; 55 of 55 |
| members; record agrees with its directory entry; sector-aligned; ascending; padded end meets the next record | 5,605 each | 7,409 each |
| directory-entry layout | 64-byte, with a `modules\<object>\<member>.mf` path whose stem equals the hash (5,605 of 5,605) | 32-byte, with a second hash and a 64-bit timestamp |
| record timestamps | 2003-09-13 to 2003-09-27 (Y M D h m s ms words) | 2005-06-28 to 2005-09-14 (.NET ticks) |
| `.dbs` schemas parsed; `.dbd` data files walked to the byte | 16; 48 of 49 (the one refused has no schema of its own on the disc) | 294; 311 of 311 |
| tables; rows; string references landing on a string start | 350; 83,791; 29,178 of 29,178 | 2,240; 168,744; 28,639 of 28,639 |
| `SEC ` containers read; sections; contiguous and ending at the declared total | none on this disc | 1,104 of 1,104 (106 empty); 56,971; all |

**An object** begins with a 2,048-byte `0x22222233` record — hash, member count, a timestamp,
and a category word plus its `objects\<hex>.of` path — then a member directory padded to a
sector, then the members, each a 2,048-byte `0x11111111` record (the member's real file name
is in it) followed by its bytes padded to a sector. Two generations of the record and entry
layouts exist, told apart by the offset of the string-length triple (+60 on Pro's 2003 layout,
+40 on The League's 2005 layout), never by title [M]. `hash2` is not the CRC-32 of the data,
and the name hash is none of CRC-32, FNV-1/1a, djb2, sdbm, one-at-a-time, ELF or
SuperFastHash [M] — it is carried, never recomputed.

**What it holds** — by member extension, the top of each disc [M]:

| Blitz Pro (14 objects, 5,605 members) | The League (57 objects, 7,409 members) |
|---|---|
| `.dff` 2,229 and `.rtd` 1,641 (RenderWare ids 0x10 / 0x16 [S]), `.cap` 345 (`HTPC`), `.ini` 306, `.ppn` 286 (`Part`), `.tga` 238, `.amx` 55, `.dbd` 49, `.dbs` 16, `.ban` 14, `.wad` 13 | `.rtd` 4,442, `.sec` 1,104, `.dbd` 311, `.dbs` 294, `.gcp` 286, `.cap` 282, `.wad` 274, `.ppn` 93, `.wip` 86 (`WIFF`), `.rws` 82, `.sss` / `.str` 40 each |

**Where a modder's data is** [M]:

* **Rosters and teams:** `playerdb.dbd` + `.dbs` in `Databases` / `databases`. Pro: `players`
  3,628 rows, `teams` 61, `positions` 15, `attributes` 10, `depthchart` 60, `coaches` 122,
  `cheerleaders` 366, with first and last names in two string pools. The League: `player_list`
  695 (names inline, 32-byte strings), `teams` 29, `positions` 15, `depthchart` 33, `voices` 28,
  three attribute tables of 695 rows each, `cap_player_list` 40, `coach_list` 196,
  `cheer_list` 252, `injuries` 23, `skin_colors` 77. The schema is a typed field list
  (`b`/`w`/`i` with bit-packing, `f`, fixed-width `s`, pool references `r`/`q`) and the data is
  fixed-width rows with a zero trailer; every table on both discs divides evenly by its
  schema's row width.
* **Playbooks and plays:** `master_pbk.dbd` (`playbook` 33 / 18 rows, `condition` 1,033 / 244)
  and 32 / 17 per-team `.dbd` files that share its schema (matched by the database name in
  their own header); Pro's `formation.dbd` (`plays` 303: a sprite-resource hash and one packed
  word), The League's `master_plays.dbd` (`plays` 364) and 289 `SEC ` play containers holding
  49,161 sections between them.
* **Stadiums:** Pro keeps one `Stadium` object of 2,951 members (`.dff`, `.rtd`, `.ini`, `.ppn`);
  The League keeps 42 `stadium_*` objects of 105–110 members each — 102–103 `.rtd` texture
  dictionaries, one `.sec` scene, two `.wip`, up to four `.ppn` — plus a `stadium_<name>.dbd`
  / `.dbs` pair per stadium in `databases`.
* **Art and UI:** `screensets` / `screens` / `images` / `Shell` / `EnvLightMap` (`.rtd`,
  `.sss`, `.str`, `.swp`, `.sec`, `.tga`), and the `player` / `coach` / `cheer` / `prop` /
  `Character` / `CaP` objects (RenderWare `.rws` / `.dff` models with per-model `.dbd` part
  databases).

**Rung today: `read-only-mapped`.** Every object and member is located, named, sized and
checked; the databases and section containers are read to the byte. Lifted by decoders for
the RenderWare, `WIFF`, `HTPC` and `Part` members, and by a writer with an independent verifier.
A writer is small for a same-length member (its bytes only) and for a database row (fixed
width, in place); a longer member moves every later member offset in the object's directory,
the object's leaf in the trailer, every later object and header word 2 — and on The League
the loose `RESMETA.LF`, a byte copy of the pack's list, if an object record changes. Adding a
member needs the hash function, which is not known.

The generated page routes each category word to a studio page from the word alone (`playbooks`
to Playbooks & Plays, `stadium_*` to Stadiums, and so on) — the object is located [M], the page
it feeds is [A] — and that row reads `read-only-mapped`.

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
| `PAK ` + metadata | Blitz Pro, The League | a Rosters / Teams page from `playerdb` (schema + rows), a Playbooks page listing playbooks, plays and formations, a Stadiums page listing scenes and texture dictionaries by name | writers with verifiers; RenderWare / `WIFF` / `HTPC` decoders before any art page |
| Midway sound bank | Blitz Pro, The League | an Audio page listing records | a PS-ADPCM decoder to play or replace one |
| `.OBF` | Blitz Pro, The League | a Gameplay-tuning page, schema + rows, today | a writer + verifier to make it editable |
| `EFS ` | AND 1 | All Textures / Menus pages once `.HDR` members are decoded | the member formats, not the archive |
| `VAGp` | AND 1 | an Audio page listing streams | a VAG decoder |

## 6. What stays unknown

1. **What a `PAK ` member *shows*.** Every member is located and named and the databases and
   `SEC ` containers are read (§4.3); the RenderWare `.rtd` / `.rws` / `.dff` members, `HTPC`
   (`.cap`), `Part` (`.ppn`), `WIFF` (`.wip`), `.gcp`, `.wad`, `.amx`, `.ban` and `.tga` are read
   to their first four bytes only.
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
6. **The `MWo3` trailing addresses**, the `PAK ` header's constant 512, the member records'
   `hash2` and type words, and the name-hash function — not CRC-32, FNV-1/1a, djb2, sdbm,
   one-at-a-time, ELF or SuperFastHash [M] — the one thing that stops a member being *added*.

## 7. How to reproduce this

    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --iso "<image>" --out <dir> --label "<Title> (USA)"
    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --page <dir>/<SERIAL>.<label>.map.json
    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --selftest        # 109 checks, synthetic bytes only

All five discs map in **under five seconds together** on the NAS [M]; with the pack's objects,
databases and sections read, the two `PAK ` discs map in 0.9 s and 1.1 s on the dev box [M]. The
non-EA readers are in `tools/owner/ea_disc_map.py`, except the pack, database and section
readers, which are product code in `mod_editor/games/_formats/midway_{pak,db,sec}.py` with
their own synthetic tests; the mapper's tests are `MidwayAndAnd1Tests` in
`tests/owner/test_ea_disc_map.py`.
