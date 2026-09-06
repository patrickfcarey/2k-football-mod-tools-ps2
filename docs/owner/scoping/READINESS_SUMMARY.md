# How far the Madden 09 module reaches — ten EA PlayStation 2 discs, measured

The owner's thesis is that once Madden NFL 09 is complete, *"the rest of the EA
modules fall like dominos."* This is that thesis measured per title, by running
the **shipped Madden 09 readers themselves** — `ea_terf`, `ea_tdb`, `ea_schl`,
`mmap_art` and the module's own preload-cache parser, imported and not
re-implemented — over every `/DATA` file of every EA disc on this box.

Tool: `tools/owner/ea_module_readiness.py` (`ea_module_readiness/v1`), selftested,
23 unit tests in `tests/owner/test_ea_module_readiness.py`. Per-disc pages:
`docs/owner/scoping/readiness/<SERIAL>.<label>.md`, each rendered from its own
`<SERIAL>.<label>.readiness.json`. **Every number on this page is copied from
one of those JSON files**; where a claim is not, it says so.

**Evidence tags.** **[M]** measured this session by the tool, on the image named.
**[m]** inferred from a committed disc map (`docs/owner/disc_maps/`) for a disc
this box does not hold — the mapper's own readers, not the module's, so it is a
weaker statement and is never mixed into the measured table. **[S]** sourced from
a named document. **[A]** assumed.

**Read-only and retail-free.** Ten images were opened `"rb"`; nothing was written
next to them, nothing was extracted to disk, and nothing under `/mnt/c` was
created or changed. Names, counts, offsets, digests, and schema field names and
widths only: a decoded texture was measured and dropped, a database's records
were never read.

---

## 1. The cross-title table [M]

Percent of each format family that **works unchanged** under the Madden 09
readers. Definitions are on every per-disc page and repeated in §2.

| disc | serial | containers | members | TDB | CRC | MMAP | SCHl | BNKl | cache copies | wall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Madden NFL 2001 (USA) | `SLUS-20093` | 100.0% (26/26) | 99.3% (8,897/8,962) | **0.0% (0/319)** | — | 60.5% (155/256) | **99.3% (4,075/4,105)** | 100.0% (252/252) | — | 60 s |
| NCAA Football 2004 (USA) | `SLUS-20719` | 100.0% (41/41) | 100.0% (25,533/25,533) | 99.2% (521/525) | 100.0% (7,224/7,224) | 91.7% (833/908) | 4.0% (316/7,921) | 100.0% (384/384) | 100.0% (1,356/1,356) | 76 s |
| Madden NFL 2004 (USA) | `SLUS-20752` | 100.0% (55/55) | 100.0% (23,331/23,331) | 100.0% (309/309) | 100.0% (7,024/7,024) | 95.1% (1,074/1,129) | 1.8% (143/7,797) | 100.0% (275/275) | 99.9% (4,712/4,716) | 123 s |
| Madden NFL 06 (USA) | `SLUS-21213` | 100.0% (101/101) | 100.0% (49,612/49,612) | 100.0% (319/319) | 100.0% (7,470/7,470) | 94.1% (1,465/1,557) | 1.0% (156/15,523) | 100.0% (301/301) | 99.8% (5,761/5,773) | 161 s |
| Madden NFL 08 (USA) | `SLUS-21638` | 100.0% (106/106) | 100.0% (51,492/51,492) | 100.0% (355/355) | 100.0% (8,860/8,860) | 95.8% (1,678/1,751) | 1.1% (169/15,659) | 100.0% (301/301) | **100.0% (6,270/6,270)** | 201 s |
| NCAA Football 09 (USA) | `SLUS-21752` | 100.0% (85/85) | 100.0% (30,391/30,391) | 99.7% (580/582) | 100.0% (8,564/8,564) | 95.2% (1,162/1,221) | 5.1% (412/8,021) | 100.0% (728/728) | 100.0% (552/552) | 135 s |
| **Madden NFL 09 (USA) — the control** | `SLUS-21770` | 100.0% (107/107) | 100.0% (47,769/47,769) | 100.0% (355/355) | 100.0% (8,926/8,926) | 95.8% (1,679/1,752) | 1.5% (166/11,389) | 100.0% (301/301) | 99.9% (6,268/6,270) | 126 s |
| Madden NFL 09 Deluxe (USA) | `SLUS-21770` | 100.0% (107/107) | 100.0% (49,019/49,019) | 100.0% (355/355) | 100.0% (8,926/8,926) | 95.8% (1,679/1,752) | 1.5% (174/11,399) | 100.0% (301/301) | — (no cache) | 106 s |
| Madden NFL 12 (USA) | `SLUS-21946` | 100.0% (80/80) | 100.0% (44,326/44,326) | 100.0% (174/174) | 100.0% (7,134/7,134) | 95.7% (1,664/1,738) | 0.5% (58/11,429) | 100.0% (301/301) | — (no cache) | 136 s |
| Madden NFL 12 Deluxe 2026 (USA) | `SLUS-21946` | 100.0% (80/80) | 100.0% (44,360/44,360) | 100.0% (174/174) | 100.0% (7,134/7,134) | 95.7% (1,664/1,738) | 0.8% (91/11,464) | 100.0% (301/301) | — (no cache) | 145 s |
| **fleet total** | | **788/788** | **374,730/374,795** | **3,142/3,467** | **71,262/71,262** | **13,053/13,802** | **5,760/104,707** | **3,445/3,445** | **24,919/24,937** | 1,269 s |

`—` is *not applicable*: Madden 2001 has no database this reader opens, so it has
no checksum site to check, and four images carry no preload cache at all.

---

## 2. What each column means, and what it does not

* **containers** — `ea_terf.parse_terf` returned a container for every `/DATA`
  file whose magic is `TERF`.
* **members** — the member's stored bytes decoded as far as the 32-byte classify
  head, i.e. its codec is one of the three the module implements (stored, RLE1,
  LZH1) and its stream is not truncated.
* **TDB** — `ea_tdb.parse_tdb` returned a database, over every `TDB` member of
  every container **plus** each bare `.DB` file.
* **CRC** — the stored CRC-32/MPEG-2 equals the one recomputed from the file's
  own bytes, per `ea_tdb.crc_sites`, summed over every database that parsed.
* **MMAP** — `mmap_art.decode_rgba` returned pixels for image 0 of a **sampled**
  member. The sample is 48 members per container, spread evenly, and every
  per-disc page states the sample against the population (13,802 of the fleet's
  88,447 texture members were decoded). The pixels are measured and dropped.
* **SCHl** — the header parsed **and** the codec is one the audio lane decodes
  (EA-XA, or no codec tag, which decodes the same way). One header per member;
  a member can hold many streams, and each page says how many were walked.
* **BNKl** — `ea_schl.parse_bank` returned a bank directory.
* **cache copies** — each copy a `QL01` preload cache carries is byte-identical
  to the container bytes it copies, checked with the module's own
  `containers.parse_preload_cache` and `PreloadCopy.length_in`.

A percentage below the total never rounds up to 100.0% — 6,268 of 6,270 prints
as 99.9%, not 100.0%.

---

## 3. What the fleet says, before the per-title detail

**1. The container layer is not a per-title problem at all.** 788 of 788
containers open and 374,730 of 374,795 members decode across ten images spanning
2000–2011 and two Deluxe rebuilds [M]. Every one of the 65 refusals is on a
single disc, Madden NFL 2001, under a single codec — **LZM1 (codec 3)**, which
the module registers and does not implement. No other disc uses it. The chunk
chains are the same three shapes everywhere (`TERF -> DIR1 -> DATA`,
`TERF -> DIR1 -> COMP -> DATA`, and exactly one `TERF -> HSH1 -> DIR1 -> DATA`
per disc) [M].

**2. The checksum layer is perfect across the fleet.** 71,262 of 71,262 CRC
sites hold the value they recompute to, on every database that parsed, on every
disc — zero mismatches [M]. This is the single most load-bearing result here: the
four-CRC pass is what every TDB writer stands on, and it was proved on ten
images before anything was written.

**3. The database layer carries across every Madden year and stops at the NCAA
ones and at 2001.** 355/355 on Madden 08 and 09, 319/319 on Madden 06, 309/309 on
Madden 2004, 174/174 on Madden 12 — but 580/582 on NCAA Football 09, 521/525 on
NCAA Football 2004, and **0 of 319 on Madden 2001** [M]. §5 says exactly why each
one stops.

**4. Texture decoding is a flat ~95% everywhere except the two oldest discs.**
Madden 06 through 12: 94.1–95.8% of sampled `MMAP` images draw, and the refusals
are the same three sentences the Madden 09 module already documents — `IPU1`
pixels, a palette-only entry, no palette [M]. NCAA Football 2004 is 91.7% and
Madden 2001 is 60.5%; 2001 is the only disc where `mmap_art.parse` itself refuses
(48 of 256 sampled members put their surface table at an offset the parser
requires to be `+0x28`) [M].

**5. Audio is the fleet's weakest lane, and 2001 is the exception that proves
it.** On every disc from Madden 2004 onward the speech is EA MicroTalk — 0.5% to
5.1% of members carry a codec the audio lane decodes [M]. Madden NFL 2001 is
**99.3%** (4,075 of 4,105) EA-XA [M]: the oldest disc is the one whose audio the
module could edit today. Sound banks are 3,445 of 3,445 across the fleet [M].

**6. The preload-cache invariant holds everywhere it exists: zero differing
copies on any disc.** 24,919 of 24,937 copies are byte-identical to what they
copy; 18 could not be resolved (§7) and **none differed** [M]. Four images carry
no cache at all — Madden 12, Madden 12 Deluxe, Madden 09 Deluxe, Madden 2001 —
which *removes* the three-place edit rule for those discs rather than adding
work [M]. That is also a live warning: on Madden 09 Deluxe the module's
container-level refusal (which refuses any container a cache names) refuses
nothing, so containers that are read-only on retail are writable on Deluxe.

**7. Retail and Deluxe are the same disc to these readers.** Madden 09 retail vs
Deluxe and Madden 12 retail vs Deluxe agree on every family to within the member
counts the rebuild changed, and all thirteen load-bearing table schemas are
identical between each pair [M].

---

## 4. Do the databases have Madden 09's schema? [M]

Field names and bit widths read from each disc's own field directory, dominant
shape per table name (`dominant_shape` picks the shape most databases carry;
where several tie it takes the widest, and each page's JSON lists every shape).
`identical` means the roster and identity lanes port with **a schema table only**.

| table | M08 | M09 Deluxe | M12 / M12 Deluxe | M06 | M2004 | NCAA 09 | NCAA 2004 | M2001 |
|---|---|---|---|---|---|---|---|---|
| `TEAM` | identical | identical | identical | 65 names, `TLNA` 120 vs 144 | 57 of 58 shared | 29 of 113 shared | 33 of 104 shared | absent |
| `PLAY` | identical | identical | 110 names, 3 widths, 73 offsets | 107 of 111 shared | 104 of 112 shared | 37 of 86 shared | 41 of 65 shared | absent |
| `DCHT` | identical | identical | identical | identical | identical | 3 of 3, 2 widths | 4 names, 3 widths | absent |
| `INJY` | identical | identical | identical | identical | identical | 3 of 5 shared | 3 of 4 shared | absent |
| `COCH` | identical | identical | identical | identical | 66 of 66 shared | 21 of 84 shared | 22 of 79 shared | absent |
| `SEAI` | identical | identical | identical | identical | identical | 15 of 15 shared, 4 M09-only | 15 of 15 shared, 4 M09-only | absent |
| `SLRI` | identical | identical | identical | identical | 5 of 5, 4 M09-only | absent | absent | absent |
| `FORM` `PBFM` `PBST` `SETL` `PBPL` `PLYL` | identical | identical | identical | 2 tables differ by one width | a different generation | a different generation | a different generation | absent |

`absent` for Madden 2001 means no database on that disc opened, so no schema was
read at all — not that the table is missing.

**The single most useful line in this table**: Madden 08's thirteen load-bearing
tables are **byte-for-byte the same shape as Madden 09's** — same names, same
widths, same bit offsets, in `TEAM`, `PLAY`, `DCHT`, `INJY`, `COCH`, `SEAI`,
`SLRI` and all six playbook tables [M].

**And the one that most contradicts an intuition**: NCAA Football 09 shares
Madden 09's *engine year* — same containers, same codecs, same `MMAP` v2, same
`QL01` caches, 100% on every non-database family — and does **not** share its
*schema*. `TEAM` is 113 fields against 65 with 29 shared; `PLAY` is 86 against
110 with 37 shared, and all 37 shared ratings differ in width (`PACC` 5 bits
against 7, and so on) [M]. NCAA's rosters are a different game's records living
in the same container.

---

## 5. Per title: what a module would still need

Each list is the work the measurement says is left, over and above the module
scaffold, the registry rows and the boot witness every module needs.

### Madden NFL 08 (`SLUS-21638`, PCSX2 CRC `2F605581`) — nothing structural
* **Nothing at the format layer.** 106/106 containers, 51,492/51,492 members,
  355/355 databases, 8,860/8,860 CRC sites, and every one of its 6,270 cache
  copies resolved and byte-identical, where the control leaves two of its own
  6,270 unresolved [M].
* Databases are where Madden 09 keeps them: `DB_TEAMS.DAT` 237, `GAMEDATA.DAT`
  102, `TEMPLATE.DAT` 15, plus the bare `STRMDATA.DB` [M].
* Still needed: the per-title ELF patch research (`SLUS_216.38`, its own CRC),
  a PCSX2 texture dump for replacement identities, and a boot witness. Texture,
  roster, identity, text, playbook and audio-bank lanes are a container list and
  a schema table.

### Madden NFL 12 (`SLUS-21946`, CRC `3DD8A7BD`) and Madden NFL 12 Deluxe 2026 (CRC `3D58A73D`) — three bit widths
* 80/80 containers, 44,326/44,326 members, 174/174 databases, 7,134/7,134 CRC
  sites [M].
* `PLAY` carries the same 110 field names with **three different widths**
  (`PCMT` 11 against 10, `PDPI` 9 against 6, `PUCL` 6 against 5) and **73 of 110
  fields at a different bit offset** [M]. The module reads every offset from the
  file's own field directory, so this costs nothing; a hard-coded offset anywhere
  would be wrong on this disc.
* **No preload cache on either image** [M] — the cache-coherence step does not
  apply, and the container-level refusal that protects cached containers on
  Madden 09 protects nothing here.
* Fewer roster targets: `DB_TEAMS.DAT` holds **54** databases against Madden
  09's 235 [M]. Whatever the other 181 held on Madden 09 is not in that container
  on Madden 12.
* Still needed: ELF research, texture dump, boot witness; and a decision about
  what `DB_TEAMS.DAT`'s 54 members cover.

### Madden NFL 06 (`SLUS-21213`, CRC `4D1C4022`) — one width, and twelve cache copies
* 101/101 containers, 49,612/49,612 members, 319/319 databases, 7,470/7,470 CRC
  sites [M].
* `TEAM` is the same 65 names with `TLNA` at 120 bits against 144; `PLAY` shares
  107 of its 111 names, gaining `PCEL PQTS PTSS PWSS` and lacking Madden 09's
  franchise-era `PEGO PRL2 PROL` [M]. `DCHT`, `INJY`, `COCH`, `SEAI`, `SLRI`,
  `FORM`, `PBFM`, `SETL` and `PLYL` are identical [M].
* 5,761 of 5,773 cache copies are byte-identical; **12 are unresolved** because
  `GAME.QKL` names members of `SOUNDDAT.DAT` that container does not have (§7)
  [M].
* Its `MMAP` members are a mix of v2 and v1 and the v1 ones decode: 1,465 of
  1,557 sampled images draw, with the same three refusal sentences as Madden 09
  [M].
* Still needed: ELF research, texture dump, boot witness, and a rule for the
  twelve cache copies before any container they touch is rewritten.

### Madden NFL 2004 (`SLUS-20752`, CRC `14F8B841`) — the playbooks are a different generation
* 55/55 containers, 23,331/23,331 members, 309/309 databases, 7,024/7,024 CRC
  sites, 4,712 of 4,716 cache copies identical [M].
* `TEAM` shares 57 of its 58 names, `PLAY` 104 of 112 with eight widths differing
  — `PBRE` 1/2, `PCPH` 2/3, `PHLM` 2/3, `PLSH` 4/3, `PRSH` 4/3, `PSKI` 3/2,
  `PTAL` 5/6, `PTAR` 5/6, every one of them cosmetic rather than a rating [M].
  **This reproduces the owner's own Madden 04 scoping table field for field** —
  arrived at here against the Madden 09 disc rather than a Madden 08 save fixture
  [S: `MADDEN04_PS2_SCOPING.md` §3.2].
* `COCH` shares 66 of 66 of its names with Madden 09's 68 [M] — the coaches the
  owner's other project has open as a workstream are on this disc in a table the
  reader opens.
* **The playbook tables are not Madden 09's**: `PBST` is 27 fields against 5,
  `SETL` shares all 8 names with all 8 widths different, `PBPL` 4 against 6, and
  `PBFM` 5 against 9 [M]. A playbook lane here is new schema work, not a
  parameterisation.
* Its uniform art is not in a `UNIFORMS.DAT` — the disc has none [S: the same
  scoping study]; the readiness page's Uniforms row lists what the glossary
  matched and the texture counts behind it.
* Four cache copies are unresolved because `FE.QKL` names a container,
  `UIS_LIB_SOLOPLAYERS.DAT`, that is not on the disc [M] — 27 of its 28 named
  files exist, so this is EA's build leftover, not a parse error.
* Still needed: a playbook schema, a uniform-art location, and the boot witness.
  Its ELF patch content already exists [S: 34 pnach files at CRC `14F8B841`, the
  CRC this run measured].

### NCAA Football 09 (`SLUS-21752`, CRC `B0157E6C`) — the container year, not the schema year
* 85/85 containers, 30,391/30,391 members, 8,564/8,564 CRC sites, 552/552 cache
  copies, 728/728 banks [M]. The texture, container, cache and checksum lanes
  port unchanged.
* **580 of 582 databases open.** The two that do not — the bare `/DATA/STRMDATA.DB`
  and `TEMPLATE.DAT` member 3 — carry **TDB field type id 13** (and one field of
  type 14), which is not one of the five the format documents, and whose declared
  width is larger than its table's whole record (`ANIN.ASNA` declares 400 bits in
  an 8-byte record; `RCFN.SPFN` 80 bits in an 8-byte record) [M]. Madden 09's own
  `STRMDATA.DB` carries only types 0–4 and zero such fields [M].
* Its databases live in `LEAGUE.DAT` (433) and `GAMEDATA.DAT` (137), not in a
  `DB_TEAMS.DAT`; there is none [M].
* Still needed: a college roster/identity schema (§4), a reading for TDB field
  type 13, and the usual ELF/dump/witness. **The roster and identity lanes do not
  port with a schema table.**

### NCAA Football 2004 (`SLUS-20719`, CRC `BAE70857`) — NCAA 09's position, one generation older
* 41/41 containers, 25,533/25,533 members, 7,224/7,224 CRC sites, 1,356/1,356
  cache copies [M].
* 521 of 525 databases open; the four refusals are the same field-type-13 family
  (`STRMDATA.DB` plus three `TEMPLATE.DAT` members) [M].
* `TEAM` 33 of 104 shared, `PLAY` 41 of 65 shared, `COCH` 22 of 79 [M] — a
  college schema, and not even NCAA 09's.
* 833 of 908 sampled textures draw (91.7%), the lowest of the eight modern discs,
  71 of the refusals being palette-only entries rather than failures [M].

### Madden NFL 2001 (`SLUS-20093`, CRC `4E7B2C18`) — a different database generation
* It is **not** refused wholesale, which was the expectation worth testing: 26 of
  26 containers open and 8,897 of 8,962 members decode [M]. The raw-CD image
  (2352-byte sectors) is read sector-gathered by the mapper's extent reader with
  no special case.
* **0 of 319 databases open.** The refusal is `ea_tdb.parse_tdb`: "table PLAY
  declares N record(s) of M byte(s), which would end at X in a Y-byte file; the
  file is truncated" — 248 instances on `LEAGUE.DAT` alone [M]. The table header
  is a pre-v8 layout, so record counts and strides are read from the wrong words.
* 65 members refuse under **LZM1**, the only unimplemented codec anywhere on the
  fleet [M].
* 48 of 256 sampled `MMAP` members refuse at `mmap_art.parse` — they declare a
  surface table at an offset other than `+0x28`, which the parser requires [M].
  This is the `MMAP` v1 header, and it is the one texture-format divergence on
  the fleet.
* **Its audio is the fleet's best**: 4,075 of 4,105 members are EA-XA, against
  1.5% on Madden 09 [M]. 252 of 252 banks open, 669 sounds [M].
* Still needed: a pre-v8 TDB reader, an LZM1 decoder, an `MMAP` v1 header path.
  Three format jobs, not a parameterisation.

---

## 6. The two titles this box does not hold — scored from their maps only [m]

Neither was measured. The mapper's TDB reader is **more permissive than
`ea_tdb`** (it does not enforce the field-inside-the-record bound that refused
four NCAA databases above), so a map that reports "0 not the v8 layout" is not a
promise that `parse_tdb` opens them. These rows are a prediction to be replaced
by a measurement the day the disc is on a machine this tool can reach.

| title | serial | what the map says [m] | predicted readiness |
|---|---|---|---|
| **NCAA Football 06** | `SLUS-21214` | 75 TERF containers, 0 refused; 31,829 members under stored / LZH1 / RLE1 only; 575 TDB members + 1 bare, "0 not the v8 layout"; 6,435 `MMAP` all v2; 9,723 `SCHl` of which 361 are codec `0x0a`; 3 `QL01` caches; **plus 65 EA BIG archives holding 5,424 entries and 4,060 `SHPS` images, which no reader in this module opens** | container / member / cache lanes near NCAA 09's; database lane subject to the same field-type-13 risk; a whole art population (`SHPS` inside `BIG`) outside the module's readers entirely |
| **MVP Baseball 2005** | `SLUS-21135` | **0 TERF containers, 0 TDB databases**; 211 BIG archives, 43,773 entries, 16,355 `SHPS` images, 31 bare `SCHl` files | the module's `ea_terf`, `ea_tdb` and `mmap_art` apply to **none** of it. Only `ea_schl` would find anything, and only after a BIG walker exists. Not a domino. |

---

## 7. What the readers refused that looks like a defect, not a format difference

Three, and the first was found on the module's own control disc.

**1. A preload copy whose member index does not exist — and the bytes are real.**
`containers.PreloadCopy.length_in` refuses with *"FE.QKL carries a copy of
UIS_FONT.DAT member 10, which that container does not have."* `UIS_FONT.DAT` has
ten members, 0–9 [M]. The 512 bytes at that offset are **byte-identical to
`UIS_PERS.DAT`'s own container header** — the next file in that cache's name list
[M]. So the copy is real, correct and useful, and the module files it under the
wrong container and then refuses it. Counts: 2 on Madden 09 retail, 12 on Madden
06 (`GAME.QKL` naming members of `SOUNDDAT.DAT`, whose bytes are 9 `TERF` heads
and 3 `BNKl` heads) [M]. **Why it matters:** a writer that rebuilt `UIS_PERS.DAT`
would leave those two cached directory copies stale, and the module's own
coherence rule would not notice, because it thinks they belong to `UIS_FONT.DAT`.
Madden 08 and NCAA Football 2004/09 have zero of these, so it is not universal.

**2. A refusal sentence that names the wrong cause.** The four NCAA database
refusals say *"the field directory is being read at the wrong offset or the file
is damaged."* Neither is true: the directory is being read correctly and the file
is fine. What is there is a **field type id 13** whose `bits` word is not a
per-record bit width [M]. The rule that every refusal is one sentence naming the
fix is not met here — the sentence sends the reader to look for a bug that is not
there. The check itself is right to fire; only its explanation is wrong.

**3. `mmap_art.parse` requires the surface table at `+0x28`.** Madden 2001 puts
it elsewhere in 48 of 256 sampled members [M]. The module's own comment says the
`+0x28` rule was already found "too strong" once (six palette banks). This is a
format difference rather than a defect, but the refusal is a hard `_require`
rather than a per-member skip, so one member's header shape refuses the member
outright.

Everything else the readers refused is a format difference and says so plainly:
LZM1 (65 members), `IPU1` pixels (48 per Madden disc), palette-only entries, a
4-bit/8-bit stride that does not hold, MicroTalk speech, and Madden 2001's pre-v8
table headers.

---

## 8. Ranked recommendation for the next modules

Weighing the share of readers that work unchanged, the size of the remaining
work, and the owner's stated interests.

| # | title | one reason |
|---|---|---|
| **1** | **Madden NFL 08** (`SLUS-21638`) | The only disc that is 100% on every family with a writer today *and* whose thirteen load-bearing table schemas are byte-identical to Madden 09's — so the roster, identity, text and playbook lanes are a container list, and its 6,270 cache copies all resolve where the control's do not. It is also the vehicle game of the owner's other project, and the community pack that covers it is a joint NCAA 06 + Madden 08 release [S]. |
| **2** | **Madden NFL 12 + Deluxe** (`SLUS-21946`) | The same 100% readings with the *least* remaining work of any non-08 disc: three `PLAY` widths the metadata-driven reader already absorbs, and **no preload cache at all**, which deletes the three-place edit rule the Madden 09 art writers spend most of their care on. |
| **3** | **Madden NFL 06** (`SLUS-21213`) | 100% on containers, members, databases and checksums with nine of thirteen tables identical; the remaining work is one `TEAM` string width, four `PLAY` fields, and a rule for the twelve cache copies the module cannot resolve. |
| **4** | **Madden NFL 2004** (`SLUS-20752`) | The deepest owner research on the fleet — this run measured its ELF CRC as `14F8B841`, the CRC the owner's 34 existing pnach patches target — and `COCH` shares 66 of 66 names, answering an open workstream as a read. Ranked below 06 only because its playbook tables are a different generation (`PBST` 27 fields against 5) and its uniform art is not where Madden 09 keeps it. |
| **5** | **NCAA Football 09** (`SLUS-21752`) | Sharing Madden 09's engine year buys the container, texture, cache and checksum lanes outright (100% on all four), and buys **nothing** for rosters and identity: 37 of 86 `PLAY` names shared, 29 of 113 `TEAM`. Worth doing as the first non-Madden module precisely because it separates "same engine" from "same data". |
| **6** | **NCAA Football 06** (`SLUS-21214`) — acquire first | The year the modding community actually works in [S], and its map predicts NCAA 09's position [m]. Not ranked higher because it is not on a machine this tool can reach, and because 65 BIG archives with 4,060 `SHPS` images sit outside every reader the module has. |
| **7** | **NCAA Football 2004** (`SLUS-20719`) | NCAA 09's schema problem plus four database refusals and the lowest texture yield of the modern discs; nothing here that NCAA 09 does not teach more cheaply. |
| **8** | **Madden NFL 2001** (`SLUS-20093`) | Three format jobs before a single lane exists — a pre-v8 TDB reader, an LZM1 decoder and an `MMAP` v1 header path — bought for one prize the others do not offer: 99.3% of its audio is a codec the audio lane already decodes. Do it when audio is the goal, not when a module is. |
| **—** | **MVP Baseball 2005** (`SLUS-21135`) | Do not schedule. Zero TERF containers and zero TDB databases: this module's readers apply to none of it [m]. |

**Two claims in the owner's thesis that the measurement supports, and one it does
not.** The dominos do fall for the *container, texture, checksum and cache*
layers — 788 of 788, 71,262 of 71,262, zero differing cache copies, across eleven
years of discs. They fall for the *database* layer across the Madden line and
stop dead at the NCAA line and at 2001. And "shares Madden 09's engine year"
turns out to predict the container lanes and not the data lanes: NCAA Football 09
is the clearest case on the fleet of a disc that is 100% ready in every way
except the one a roster editor cares about.

---

## 9. Reproducing this

```
python3 tools/owner/ea_module_readiness.py --selftest
PYTHONPATH=. python3 tools/owner/ea_module_readiness.py --iso "<image>" --out <dir> --label "<Title> (USA)"
PYTHONPATH=. python3 tools/owner/ea_module_readiness.py --page <dir>/<SERIAL>.<label>.readiness.json \
    --baseline <dir>/SLUS-21770.Madden-NFL-09-USA.readiness.json --out docs/owner/scoping/readiness
PYTHONPATH=. python3 tools/owner/ea_module_readiness.py --summary <dir>
```

Ten images, 1,269 s of wall time in total, single-threaded, and never more than
a few hundred megabytes resident — a 415 MB speech container is read through a
memory map, never loaded.
`--shallow` skips every deep pass and answers the container and member rows in
about 30 s per disc. Nothing was written outside the output directory.
