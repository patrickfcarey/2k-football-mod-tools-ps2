# Disc mapping audit — `ea_disc_map.py` v4 → v5, the runbook, the template and twelve maps

Audit of the read-only disc mapper, its procedure and its outputs, 2026-09-05, on branch
`mapper-audit` (base `1053844`, mapper v4). Everything below is either **measured** on a disc
the owner holds ([M]), **sourced** from a named document or an independent implementation ([S]),
or an **inference** marked as such ([A]). No member payload, decoded pixel or game string
appears in this document, in the maps, or in any committed file.

Paths below name the tool as `tools/ea_disc_map.py` (its place on `mapper-audit`); on the
`owner-tooling` branch the same file is `tools/owner/ea_disc_map.py`, its tests
`tests/owner/test_ea_disc_map.py`, and the runbook and template live under `docs/owner/`.

Retail images were read from `/mnt/c/Roms/PS2/` on the dev box and, for NCAA Football 06 and
MVP Baseball 2005, from `~/Games/ps2/` on the rig over SSH (the mapper piped through
`python3 -`, writing only under `~/ps2-maps/out`). No image was copied or modified; no emulator
was launched.

## 1. What was checked

| area | how |
|---|---|
| Correctness vs the owner's Madden 09 census | per-container join of the v4 and v5 maps against `nfl-online-revival/experiments/madden09/containers/inventory.json` (47,769 member rows): member counts, chunk chains, codec split, decompressed-format histogram; totals against `docs/madden09-container-census.md` §1, §3, §5, §6, §7, §8 |
| Correctness vs the Madden 04 scoping | container count, member total, codec split, per-container rows against `scoping/MADDEN04_PS2_SCOPING.md` §2 |
| Retail vs Deluxe | `--compare` over the two Madden 09 maps and the two Madden 12 maps |
| TDB schema reader | 355 real databases (Madden 09 `GAMEDATA` 104, `DB_TEAMS` 235, `TEMPLATE` 15, `STRMDATA.DB`) compared field-by-field against `nfl-online-revival/tools/madden_tdb.py` and `NCAA-Draft-Class-Editor/tools/parse_madden_tdb.py`; franchise preamble and big-endian refusal on synthetic bytes |
| BIG walker | Madden 09 `/EACN/*.BIG` (index counts vs the census §5), MVP's 211 archives (entry counts vs each index, size-field byte order), NCAA 06's 65 archives (why 0 SHPS) |
| Coverage gaps | the unclassified-magic histogram on every disc, each cluster traced to a container family and, where a source or a measurement justifies it, given a name |
| Robustness | raw-CD image (Madden NFL 2001, 2352-byte sectors), truncated ISO9660 records (Madden 09 Deluxe), damaged containers, a short image, zero-length and 2-byte files, `--render` on a v1 map, 64 KiB allocation granularity, determinism |
| The five pages | every number ≥ 100 in each page traced to its map; container rows, texture sentences, text/audio sentences and rung cells checked one by one |

## 2. Findings, with the evidence

### 2.1 Correctness verdicts

**Madden 09 vs the census: agreement, and one census-side correction.** [M] Files 187, TERF
containers 107, members 47,769, stored 43,500 / LZH1 4,269, chunk chains 60 / 46 / 1, MMAP
11,338, SCHl 11,389, SMF 1,447, empty 650, nested TERF 507, TDB 354, DMF 324, BNKl 301, FNTS
14, MPCh 9, SKL1 8, SEVT 3, ELF 1 — identical to `docs/madden09-container-census.md` §1. The
per-container join finds **102 of 107 containers identical** in every count. The five that
differ are `STORYMSG`, `STRYCPTN`, `STRYEMAL`, `STRYHDLN`, `STRYTEXT`: the mapper counts
**699 more `TEXT` members** (14,748 vs 14,049) and the census 699 more unclassified. All 699 are
members of 17–31 bytes whose decompressed magic in `inventory.json` is a `<` followed by
letters. The census reads 32 bytes for every stored member and so read past the end of a short
member into the next member's alignment padding, which is zero and not printable; the mapper
reads exactly the member. **The mapper is right; the census's `TEXT` total is 699 short**, and
the sentence in `ea_terf.py` claiming the 32-byte rule "agrees with the owner's census exactly"
is true only after this correction. Correction owed to the census: `TEXT` = 14,748,
unclassified = 6,676 at the v4 magic table (6,664 at v5's).

**Madden 09 QL01, BIG and executables vs the census** [M]: `GAME.QKL` 29 files / 6,084 entries
(23 header copies, 6,061 member copies) / 6,082 distinct offsets; `FE.QKL` 28 / 186 (34 / 152) /
184 — census §3 exactly. `BUNDLE.BIG` 74 entries, 70 nested `BIGF` + 4 directory entries;
`LOC_PS2.BIG` 20; `MODULES3.BIG` 23 ELF — census §5 exactly. 47 IRX + 3 EXEC — census §7
exactly. The size field of all 70 nested archives is little-endian and equals the entry size.

**Madden 2004 vs the scoping study** [M]: 55 containers (the study's 51 fully parsed + 4
header-probed), 23,331 members (14,981 + 116 + 7,659 + 447 + 128), stored 20,050 / LZH1 3,281,
TDB 308, DMF 221, SKL1 10, FNTS 9, nested TERF 32 (28 + 4 inside the four large containers),
`STRMDATA.DB` 70 tables, `SPCHHDRS` 4,021, `GAMEDATA` 76 (LZH1 67 / stored 9; TDB 64, SEVT 2,
TEXT 1), `ONLINE` 4 (ELF 1, TEXT 1) — all agree. One scoping-side typo: its `STADIUMS.DAT` row
says "SMF 421, MMAP 4"; the container holds MMAP 461, SMF 421, empty 106, unclassified 64
(1,052 members), so "MMAP 4" is a truncated 461.

**Madden 09 retail vs Deluxe** [M] (`--compare`, `audit/compare-m09-retail-deluxe.md`): **13
files differ** — 2 removed (`/DATA/FE.QKL`, `/DATA/GAME.QKL`: the Deluxe drops the preload
copies, which is what the census's three-place edit rule predicts a rebuild must do) and 11
resized (`BGM`, `DB_TEAMS`, `FIELDART`, `GAMEDATA`, `MOVIEDAT`, `STADIUMS`, `STRMDATA.DB`,
`TEMPLATE`, `UIS_PLYR`, `UIS_STAD`, `UNIFORMS`). Eight containers change in mapped counts (for
instance `STADIUMS` 1,355 → 2,120 members and COMP → DATA; `UNIFORMS` MMAP 455 → 591; `MOVIEDAT`
9 MPCh → 10 empty; `DB_TEAMS` 235 → 644 members, 409 of them empty), 99 are identical in every
count, and the boot ELF differs (CRC `38014255` → `084562FF`). Six containers are recorded short
in ISO9660 by 4 to 26,168 bytes, as `EA_TERF_FORMAT.md` §7 says; v4 refused four of them, v5
reads all six to their declared length.

**Madden 12 retail vs Deluxe 2026** [M] (`--compare`): 97 files on both, **9 resized**
(`BGM`, `DB_TEAMS`, `FIELDART`, `MOVIEDAT`, `STADIUMS`, `STRMDATA.DB`, `TEMPLATE`, `UIS_PLYR`,
`UNIFORMS`), 7 containers changed in mapped counts (`MOVIEDAT` again stubbed to 200 bytes with
10 empty members; `UNIFORMS` MMAP 455 → 591; `BGM` 22 → 57 streams), 73 identical, boot ELF
CRC `3DD8A7BD` → `3D58A73D`, and the same ISO9660-short signature on six containers (v4 refused
two of them, v5 none). The retail Madden 12 disc has no `.QKL` files to drop.

**TDB schema reader** [M]: on 355 real databases the mapper's table names, record counts, field
names, bit widths and bit offsets are **identical to both independent readers (355 / 355 and
355 / 355)**. The franchise preamble (`02 00 00 00` before `DB`) and the big-endian refusal
are covered by synthetic tests. One defect found and fixed: the version word sits on the disc as
`00 08`, so v4 recorded every schema as "v2048"; v5 records `version_bytes` and reads 8 from
either byte order. A second: Madden NFL 2001's databases carry version word `01 03` (a v3
layout — 12-byte directory entries), which v4 would have "parsed" into garbage table names; v5
refuses them with the version word (Madden 2001 `LEAGUE.DAT`: 313 TDB members, all refused as
"version word 0103").

**BIG walker** [M]: MVP's 211 archives — every index read to its declared entry count (43,773
entries), every size field little-endian and equal to the file size. NCAA 06's 65 archives —
5,424 entries; three `.VIV` archives store the total big-endian and 31 to 2,919 bytes short of
the file (`XDB.VIV` declares 1,759,345 for 1,762,264 bytes), now reported as "BE (declares X,
file Y)". **The "0 SHPS" on NCAA 06 was a coverage gap, not a fact**: its `.VIV` archives nest
2,880 archives whose 4,060 SHPS banks sit one level down, and 2,169 members are RefPack-packed
(`10 FB`) so their stored bytes carried no magic. Two defects were found while closing it:
the nested banks store their directory big-endian (read little-endian, one bank declared
16,777,216 images and 942 banks summed to 15.8 billion); and v4 never looked inside a nested
archive at all.

### 2.2 Coverage gaps closed

| gap | v4 | v5, and the justification |
|---|---|---|
| RefPack-packed archive members (MVP 23,855; NCAA 06 2,169) | `other:10fb…` | decompressed only to their magic (32–128 bytes) with a RefPack head decoder (EA's public LZ77 variant; the `10 FB` family); MVP: SHPS 16,355, SCHl 9,123, Apt 1,282, TEXT 2,047; NCAA 06: SHPS 4,060 |
| nested BIG archives | not opened | one level walked: entries, kinds, extensions, SHPS banks merged into the parent's counts |
| SHPS/FSH headers | none | image count, directory id, first image's record id / width / height, byte order (fshtool / niotso FSH layout [S]) |
| SCHl headers | none | platform id (`PT` + u16, or `GSTR` generic), version, channels, codec ids (0x83 and 0xA0), sample rate, from the patch list as vgmstream's `ea_schl.c` reads it [S]; Madden 09: platform `PS2` 3,751 / `GSTR` 7,638; codec2 `0x04` on 10,988 members, `0x0a` on 14, absent on 387 |
| QL01 preload files | kind only | files named, entry count, header vs member copies, distinct offsets, copies per container (census §3 layout [S]) |
| ELF / IRX inventory | boot ELF only | every ELF: class, type (`EXEC` / `IRX (SCE IOP relocatable)` = e_type 0xFF80), machine, entry, sha256; 47 IRX + 3 EXEC on Madden 09 |
| nested TERF | one level | three levels, formats and TDB schemas aggregated, depth recorded |
| unclassified-magic histogram | top 8 per container, level 1, containers lost for nested members | full histogram across every depth, top 48 with the containers that hold each |
| member-size statistics | none | min / median / max / distinct sizes, stored and decompressed totals, largest member; small fixed-size record families are named in the notes (`SPCHHDRS`: 5,740 members of 20–56 bytes, 9 sizes) |
| file kinds | 11 magics | 30 magics incl. PS2 system files (`RESET` IOP images, `PS2D` icon descriptors, `.ICO` by magic + shape count, `IECS` sound headers), `MPCh`, `ABKC`, `BNKl`, `LOCH`, `FNTS`/`FntS`, `PFR1`, `EVT`, `Apt`, `ASFT`, MPEG video / program streams, `TEXT` (ASCII, UTF-8 BOM, Latin-1), zero-headed, `VC-pack` by path; extension hints for the rest, graded [A] |
| `EVT` | unknown | the head of every loose `.EVT` audio event table on MVP 2005 (8, `03 12 3c 07`) and NCAA 06 (4, `03 11 3c 07`), also a member of every EA speech container (Madden 09: 9) — named after the extension the loose files carry [M] |
| MMAP beyond width/height | none | version and format-id histograms; format `0x400` members (Madden 09: 8; NCAA 2004: 799; NCAA 06: 228) declare 1×3 and are kept out of the dimension table |
| the 2K5 VC packs | `other:e2100000` | `VC-pack` with a pointer to the `nfl2k5ps2.textures.disc_inventory` lane; the mapper's whole-image sha256 for the 2K5 disc equals that lane's pinned digest `f1300699ab44…` |

**Measured and recorded as negatives (not closed):**

- **`ANIMDATA` blobs are not length-prefixed.** Census §10 item 8 hypothesised the `f8010000`
  family is a leading u32 length. Measured on all 631 unclassified `ANIMDATA` members of Madden
  09: the u32 at +0 equals the member length − 4 in **0 of 631**. The heads split into a family
  with a u16 at +0 in 0x100–0x9ff and zeros at +2..+7 (403 members) and a family with u16 1 at
  +0 and small counts at +2 / +4 (the rest). Left unclassified.
- **`SPCHHDRS` records have no invariant.** 5,740 members, 9 distinct sizes (28 ×2,947, 24
  ×2,418, 44, 20, 40, 32, …); the u16 at +0 takes five values (16683 ×2,260, 10 ×2,228, 678,
  496, 8230); the u16 at +2 equals the member index only in the "10" family (2,228). Madden 12's
  3,859 records are 28 bytes in 3,748 cases. Reported through the size statistics, not named.
- **MMAP internals are not a clean rule.** Census §6's "pixel block + palette" reading of the
  two sizes was tested on all 10,140 version-2 members with format id 0/1/4 on Madden 09: the
  u32 at +0x30 equals width × height × (4, 8, 32) / 8 for format ids (0, 1, 4) in **5,117**
  members — every face, kit, coach, fan and stadium container satisfies it — and fails in 5,023,
  all in `UIS_*` containers (`UIS_PLYR` 3,218, `UIS_PDBI` 353, `UIS_COAC` 238). `size_a` equals
  that pixel count + 64 in 4,860. Version-1 members (1,190, `UIS_MCFL`) show a different u32 at
  +0x30 for identical dimensions. So the format id is recorded; bits per pixel is not derived.
- **Madden NFL 2001 is an older revision of everything.** [M] Raw CD (2352-byte sectors,
  payload at +24), 41 files, 26 TERF containers, 8,962 members. Three containers carry version
  word `02 01 00 05` (every later disc: `02 02 00 05`); two of them have zero members.
  `UIS_POPS.DAT` holds **65 members in codec 3 (`LZM1`)** — the codec `EA_TERF_FORMAT.md` §6
  records as "reported in NASCAR Thunder 2004 and implemented by nobody, absent from all seven
  discs" is present on this eighth disc and is refused as undecodable (65). Its 319 TDB members
  are the v3 layout (version word `01 03`). The container itself parses: chain, members,
  codecs, MMAP 1,639, SCHl 4,105, BNKl 252, SMF 26.
- **The UI screen format** (`UIS_POPS`, `UIS_BANR`, `UIS_PAUS` … ~200 LZH1 members) and the
  `CAFE*` inner blobs (`01000100` ×1,051 on Madden 09, the largest cluster at every depth) stay
  unclassified: no source names them and nothing here decodes below a magic.

### 2.3 Robustness fixes

| finding | evidence | fix |
|---|---|---|
| **v4 misread every raw-CD container.** `_Extent` assumed a contiguous extent; on a 2352-byte image `read()`/`view()` walked sync and header bytes as data | Madden NFL 2001: v4 "mapped" 26 containers with 5 refusals whose sentences were chunk-chain nonsense (`no DIR1 chunk`) | sector-gathered `read()`; `view()` materialises up to 1 GiB on a raw image; synthetic raw-CD disc maps identically to the 2048 one (test) |
| **ISO9660 records shorter than the DATA chunk lost the tail.** v4 mapped the directory length only | Madden 09 Deluxe: 4 of 107 refused; Madden 12 Deluxe: 2 of 80 | `declared_length(head)` decides the span; the image is checked for the bytes; `iso_short_by` is recorded (test patches a record 64 bytes short) |
| **A trailing empty member past the end still refused** (`DB_TEAMS`, `STADIUMS` on the Deluxe: DATA chunk one alignment unit short of it) | 2 of 107 refused after the fix above | `ea_terf`: an empty member may sit past the end when `allow_size_mismatch=True`; a member with bytes still refuses (3 tests; 60 pass) — product change, separate commit |
| `mmap` past EOF / a corrupt container raised out of `map_disc` (the `view()` call sat outside the `try`) | synthetic short image | every per-file step is inside a `try`; a `_View` closes on every path and retries a `BufferError` after `gc.collect()` (test writes to the image afterwards) |
| zero-length file became `other:` with an empty hex | synthetic | `empty` |
| `--render` on an older JSON raised `KeyError` on v3/v4 keys | v1-shaped map | every key read with a default; test renders a v1 map and its page |
| count dictionaries lost their order in the key-sorted JSON, so the "top" MMAP sizes were alphabetical | every v4 `.map.md` | rendering re-sorts by count |
| cp1252 consoles | Windows CI | `sys.stdout.reconfigure(errors="backslashreplace")` |
| `mmap.ALLOCATIONGRANULARITY` = 65,536 on Windows | test monkeypatches the constant and reads a file at an unaligned offset | the base/offset arithmetic already held; now proven |
| stdin execution on the rig (`__file__ == "<stdin>"`) | first rig run failed with `No module named ps2_iso9660` | the repository root is taken from the cwd when `__file__` is not a file |
| determinism | two maps of one synthetic disc | identical JSON except `generated_utc` / `seconds` (test) |

### 2.4 New modes

- `--page MAP.json`: the disc-map page skeleton with every mechanical cell filled from the map's
  Totals — identity, kinds, the containers that matter (largest 12 + every TDB/TEXT holder) with
  a glossary phrase graded [S] (owner's census) or [A], archives, databases with schema ids,
  textures, text/audio, the page-by-page rung table by the runbook's rules, the writers section
  (DATA chains, LZH1 chains, RLE1-only chains, stored-only COMP chains, BIG, QL01) and the top
  unclassified magics as open questions. The agent adds only `<what it is for>` phrases and
  further open questions.
- `--compare A B`: files added / removed / resized; containers changed with member, chain,
  codec, format, MMAP-size, TDB and ISO9660-short deltas; archives; schemas; totals.
- `--summary DIR`: one table over every map (disc, serial, files, containers, refused, members,
  archives, entries, schemas, MMAP, SCHl, TEXT, TDB members, nested TERF, unclassified, seconds,
  image sha256).
- The `.map.md` gained **Totals**, **Databases inside containers**, **Preload copies (QL01)**,
  **Executables**, an archive table with RefPack / SHPS / nested columns, and a full-depth
  unclassified-magic table.

## 3. The five pages: what needs correcting

Every number ≥ 100 in each page was traced to its map; the container rows and the summary
sentences were then checked one by one. The systematic cause is the same in every page: the v4
`.map.md` had no disc-wide totals, so the agents computed or guessed them. `--page` writes each
of these sentences from Totals; the corrections below are what `--page` now produces.

**NCAA Football 2004** (`SLUS-20719`): chains "DATA-only 37 / COMP 4" → **33 / 8**; "other 20"
folds the 3 `QL01` files in → 17 other + 3 QL01; "Dimensions (top): 256x128 ×1170, 528x256
×368, 256x256 ×703, …" are per-container numbers (703 appears nowhere) → disc-wide top:
**128x128 ×2,419, 256x128 ×1,457, 256x64 ×706, 64x64 ×465, 128x64 ×402** (the 799 "1x3"
members are format-0x400 records, not textures); writers "37 DATA-only" → 33, "6 COMP" → 8.
Rung table and database rows are right.

**Madden NFL 2004** (`SLUS-20752`): "DATA chain only" → **39 DATA / 16 COMP**; "other 20" →
18 + 2 QL01; "MMAP across 21 containers" → **27**; the dimensions list mixes per-container
counts → disc-wide top **128x128 ×2,337, 96x96 ×2,310, 112x80 ×748, 480x320 ×748, 64x64 ×374**.
Everything else traces.

**MVP Baseball 2005** (`SLUS-21135`): "other (8 kinds) 59" → 125 unrecognised files under v4
(16 under v5, the rest now `MPCh` 42, `ABKC` 24, `TEXT` 21, `EVT` 8, `LOCH` 3, `BNKl` 2 and
PS2 system kinds); "Archives hold 12,989 `.ssh`" → **15,856** `.ssh` entries (v5 sees them as
16,355 SHPS banks, RefPack-packed); "SCHl: 31 files — all in 8 BIG archives" is two things
merged: 31 loose files with a `.BIG` name whose *content* is a bare SCHl stream, and 9,123 SCHl
members inside archives; "MPC: 42 files … Largest sample: `/CNF/DIAL_SPD.CNF` 812 bytes" is a
`.CNF` text file quoted as a movie — the MPC files are `/DATA/FRONTEND/MOVIES/*.MPC` (largest
150,564,068 bytes); "Stadiums: SHPS (geometry)" — SHPS is an image bank, the stadium members
are RefPack-packed and their format is unknown; "BIG archives rewritable with
`ea_terf.rewrite_member`" — BIG is not TERF; "565 KB / 492 KB" are rounded sizes not in the
map. Under v5 the disc has 43,773 archive entries: SHPS 16,355, SCHl 9,123, ELF 4,061 (`.axt`/
`.ord` objects), TEXT 2,047, Apt 1,282, BIGF 643.

**NCAA Football 06** (`SLUS-21214`): "other 155 (164 distinct kinds)" → 144 unrecognised + 3
QL01 + 8 SCHl under v4 (45 under v5); "Distinct schema shapes: 1" → **13**; the databases table
says GAMEDATA/LEAGUE/TEMPLATE members are "not enumerated" — the JSON enumerates every one
(v5's `.map.md` shows them in *Databases inside containers*); "MMAP across 20 containers" →
**33**; dimensions "128×128 ×2,286, 64×64 ×1,108, 256×256 ×1,188, …" → **128x128 ×3,224, 64x64
×930, 256x256 ×819, 528x256 ×408, 128x64 ×340** (228 format-0x400 records excluded); "TEXT
members: 8 (not in the map file)" — they are in it; "SHPS … 0" → **4,060 banks / 9,254 images**
inside the `.VIV` archives, plus 3 loose `ShpS` files; "Menus & UI … TERF decoder" is not a
thing. Nested TERF 264 and SCHl 9,723 are right.

**NCAA Football 09** (`SLUS-21752`): "stored 31, COMP 54" → **50 DATA / 35 COMP**; "MMAP across
85 containers" → **35**; dimensions "256×256 ×1,200, 128×256 ×818, 128×128 ×1,700, 64×64
×1,161" → **128x128 ×2,968, 64x64 ×891, 256x256 ×799, 128x256 ×771, 528x256 ×409**; "SCHl in
… `/DATA/CMNTDATA.DAT`" — CMNTDATA holds no SCHl (3 containers do); "Nested TERF: 141" →
**411**; "Distinct schema shapes: 2" → **13**; "read-only-mapped → extract-only" is a future
rung; "Playbooks & Plays | `/DATA/PLADATA.DAT` | DMF" — PLADATA is player models; playbooks are
the TDB members of `GAMEDATA`.

The Madden 09 page (not one of the five) is reproduced by `--page` in
`audit/pages-new/`; the integrator can regenerate all five the same way.

## 4. Runbook and template changes

- The runbook now makes `--page` the page step; the agent fills only the `<what it is for>`
  cells and the open questions; rule 6 forbids arrows and future rungs; a table names every
  error seen in the five pages and the rule that prevents it; `--compare` / `--summary` are the
  Deluxe and fleet steps; the rung rules gain SHPS, MPCh, RLE1 (an encoder exists), BIG (no
  writer) and QL01 (three-place edit) rows; the timing line is updated (Madden 09 ≈ 45 s plus
  hashing).
- The template mirrors the `--page` output and marks every cell `[--page]` or `[agent]`, adds
  the archive-shaped variant for BIG discs, restricts the rung column to five values, and ends
  with a "do not" list.

## 5. What remains unknown

- The `CAFE*` inner blob families (`01000100`, `02000000`, `02000100`), the `UIS_*` LZH1 screen
  members, the `ANIMDATA` blobs, `SPCHHDRS` records, `OTGDASH.DAT` (`8a09bbd8`), the Burnout
  Revenge demo assets bundled on the Madden 06 disc (`.HWD`/`.LWD`/`.BGV`/`.RWS`/`.BIN`), the
  `MMNCDEMO` `.EBO` members on NCAA 06 (2,731, head `45424f00`), MVP's `.hdr`/`.ifo`/`.fel`
  members.
- MMAP bits per pixel, palette and mip layout (§2.2); the meaning of MMAP format id `0x400`.
- The SCHl codec ids beyond the tag legend (vgmstream's table reads `0x04` as MicroTalk 10:1 and
  `0x0a` as 16-bit PCM; not verified here, no sample decoded).
- Madden 2001's `LZM1` codec and v3 TDB directory layout.
- Whether any container-level checksum exists (unchanged from `EA_TERF_FORMAT.md` §6).

## 6. Fleet summary (counts only)

Produced by `--summary` over the regenerated maps (12 discs of the brief plus Madden NFL 2001):

| disc | serial | files | containers | refused | members | archives | archive entries | schemas | MMAP | SCHl | TEXT | TDB members | nested TERF | unclassified | seconds | image sha256 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Madden NFL 2001 (USA) | SLUS-20093 | 41 | 26 | 0 | 8,962 | 0 | 0 | 0 | 1,639 | 4,105 | 0 | 319 | 19 | 2,277 | 55.6 | `8c1e967db605f1fb9ce03f5289ecc862cd4fe30fa067ede1d8327da027ed84d0` |
| NCAA Football 2004 (USA) | SLUS-20719 | 110 | 41 | 0 | 25,533 | 0 | 0 | 13 | 6,999 | 7,921 | 1 | 524 | 27 | 7,012 | 61.1 | `aa66d1d95927341f837cc88930d21c7c05a3f247289a024edd71ff04f3d2b157` |
| Madden NFL 2004 (USA) | SLUS-20752 | 124 | 55 | 0 | 23,331 | 0 | 0 | 16 | 8,255 | 7,797 | 3 | 308 | 32 | 4,663 | 84.7 | `b6488caf903920cddd25a9c74e1d2963b505ae302bc2faed9dfa1a0bffadccc5` |
| ESPN NFL 2K5 (USA) | SLUS-20919 | 71 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 68.5 | `f1300699ab445ad04b1e27f6e2df87f7a4d1d080d06c7d73499e1be9618a4ebe` |
| MVP Baseball 2005 (USA) | SLUS-21135 | 434 | 0 | 0 | 0 | 211 | 43,773 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3.1 | `90ed5e7974fc6f4374b43f6de19a984609c75dde94bc632a2f0940f8267b6484` |
| Madden NFL 06 (USA) | SLUS-21213 | 357 | 101 | 0 | 49,612 | 3 | 110 | 22 | 10,405 | 15,523 | 14,017 | 318 | 310 | 6,359 | 117.4 | `b5480cc101aa4e81dcf00cd3547b93823a809d42d45394159127b497ee85690d` |
| NCAA Football 06 (USA) | SLUS-21214 | 364 | 75 | 0 | 31,829 | 65 | 5,424 | 13 | 6,435 | 9,723 | 8 | 575 | 264 | 9,017 | 9.8 | `fe2e30e7ea345f1adc489293453dba6a3b53613a66f0b9fab84acaa41fd98cb0` |
| Madden NFL 08 (USA) | SLUS-21638 | 186 | 106 | 0 | 51,492 | 3 | 117 | 21 | 10,821 | 15,659 | 14,743 | 354 | 507 | 6,662 | 78.7 | `39d9e41832b9aff947d7f1d1421d71d6056fa9d4fb44a839519dd42a655666c7` |
| NCAA Football 09 (USA) | SLUS-21752 | 166 | 85 | 0 | 30,391 | 3 | 117 | 13 | 6,978 | 8,021 | 1,247 | 581 | 411 | 7,051 | 99.0 | `e15ba4d0a3a7139f4e60023c6e045c306d95aca62eb5d483cb8414b4b9fb7de8` |
| Madden NFL 09 (USA) | SLUS-21770 | 187 | 107 | 0 | 47,769 | 3 | 117 | 21 | 11,338 | 11,389 | 14,748 | 354 | 507 | 6,664 | 68.0 | `b34e8a6acb4be6c92c238173e9c269bf42dfd3bb4231685052538f3aa82f6427` |
| Madden NFL 09 Deluxe (USA) | SLUS-21770 | 185 | 107 | 0 | 49,019 | 3 | 117 | 21 | 11,476 | 11,399 | 14,748 | 354 | 507 | 6,664 | 89.0 | `d331c5e40104317768a0ff100476082b2dd499d1758b9a04ba0e0efe4bc1be20` |
| Madden NFL 12 (USA) | SLUS-21946 | 97 | 80 | 0 | 44,326 | 0 | 0 | 21 | 10,200 | 11,429 | 14,743 | 173 | 42 | 4,784 | 54.7 | `b9c3e7b95527a1e81faf629b515e8036f71bbd5e05806959944cd602fc3fcdaf` |
| Madden NFL 12 Deluxe 2026 (USA) | SLUS-21946 | 97 | 80 | 0 | 44,360 | 0 | 0 | 21 | 10,336 | 11,464 | 14,743 | 173 | 42 | 4,784 | 60.8 | `6141e21cff21a57886b74bf3fde7ffc78e870b1816be185d8f1888f67e794d67` |

Totals over the fleet: 863 containers, 406,624 members, 94,882 MMAP, 114,430 SCHl, 89,001 TEXT, 65,937 unclassified, 291 archives.

Madden NFL 2001 is not one of the twelve; it is the raw-CD robustness check and is listed
because its map now exists.

## 7. Verification

`python tools/ea_disc_map.py --selftest` (54 checks); `python -m unittest
tests.mod_editor.test_ea_disc_map tests.mod_editor.test_ea_terf` (23 + 60 tests);
`python tests/mod_editor/test_phase1_packaging.py` (17 tests, the one pre-existing
reviewed-metadata error in a lean worktree); `python tools/ea_terf_inspect.py --selftest`
(13 checks). All synthetic; no fixture, no disc.
