# How far the Madden 09 module reaches — twenty EA PlayStation 2 discs, measured

The owner's thesis is that once Madden NFL 09 is complete, *"the rest of the EA
modules fall like dominos."* This is that thesis measured per title, by running
the **shipped Madden 09 readers themselves** — `ea_terf`, `ea_tdb`, `ea_schl`,
`mmap_art` and the module's own preload-cache parser, imported and not
re-implemented — over every `/DATA` file of every EA disc on this box.

**§1 is the ten images this box holds.** Ten more have been measured on the NAS
since: NFL Street 1–3 and NCAA Football 06, which are the same `TERF` family, and
the six EA `BIG` discs of **§6**, which are not. `readiness/TABLE.md` carries all
twenty rows.

Tool: `tools/owner/ea_module_readiness.py` (`ea_module_readiness/v2`); its selftest
makes 61 checks on synthetic discs it builds itself, and 45 unit tests sit in
`tests/owner/test_ea_module_readiness.py`. `v2` adds the BIG / RefPack / SHPS
rows §6 is built from, driven by `ea_big` and `ea_shps` — the readers the *other*
EA lane ships, imported the same way. Per-disc pages:
`docs/owner/scoping/readiness/<SERIAL>.<label>.md`, each rendered from its own
`<SERIAL>.<label>.readiness.json`. **Every number on this page is copied from
one of those JSON files**; where a claim is not, it says so.

**Evidence tags.** **[M]** measured this session by the tool, on the image named.
**[m]** inferred from a committed disc map (`docs/owner/disc_maps/`) for a disc
this box does not hold — the mapper's own readers, not the module's, so it is a
weaker statement and is never mixed into the measured table. **[S]** sourced from
a named document. **[A]** assumed.

**Read-only and retail-free.** Twenty images were opened `"rb"`; nothing was written
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
copy; 18 could not be resolved (§8) and **none differed** [M]. Four images carry
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
  `GAME.QKL` names members of `SOUNDDAT.DAT` that container does not have (§8)
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

## 6. The BIG family — the half of the fleet §1 could not see [M]

Six more discs, measured on the NAS over the same read-only path. **Not one of
them carries a single `TERF` container, EA `TDB` or `QL01` cache** [M], so under
§1's rows all six are a line of dashes: the MVP Baseball 2005 page in this
directory said exactly that and nothing else until this pass. `ea_big` and
`ea_shps` are the readers the *other* EA lane ships — documented in
`docs/product/EA_BIG_FORMAT.md` and `EA_SHPS_FORMAT.md`, and already the
substrate of `MVP05_PS2_MODULE_PLAN.md` — and the census now drives them the
same way it drives `ea_terf` and `mmap_art`: imported, not re-implemented.

MVP Baseball 2005 is the **control** for this half of the fleet, the way Madden
NFL 09 is for the other: its archives are the ones `ea_big` was written against,
and every count below agrees with the module plan's independently taken ones
(43,773 level-one entries + 2,423 nested = 46,196; 23,855 RefPack; 16,371 banks
inside the archives, and 21 more sitting loose on the disc, which is where this
census's 16,392 comes from).

### 6.1 The cross-title table [M]

| disc | serial | BIG archives | BIG entries | RefPack | SHPS images | SCHl | BNKl | wall |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| FIFA Street (USA) | `SLUS-21147` | 98.3% (176/179) | 100.0% (1,025/1,025) | 98.9% (181/183) | 66.4% (2,358/3,550) | 100.0% (25/25) | — | 11.7 s |
| FIFA Street 2 (USA) (En,Es) | `SLUS-21369` | 98.9% (716/724) | 100.0% (5,904/5,904) | 100.0% (1,797/1,797) | 94.4% (4,777/5,063) | 100.0% (23/23) | 100.0% (58/58) | 25.5 s |
| FIFA 14 (Latin America) | `SLUS-27093` | 99.9% (16,572/16,575) | 100.0% (144,010/144,010) | 100.0% (39,942/39,942) | 58.4% (27,502/47,093) | 7.7% (1,521/19,674) | — | 99.9 s |
| NBA Street Vol. 2 (USA) | `SLUS-20651` | **100.0% (28/28)** | 100.0% (5,204/5,204) | **0.0% (0/24)** | **100.0% (8,190/8,190)** | **100.0% (194/194)** | 100.0% (38/38) | 7.0 s |
| NBA Street V3 (USA) | `SLUS-21126` | 96.2% (457/475) | 95.9% (5,538/5,777) | 100.0% (996/996) | 54.6% (3,206/5,868) | 100.0% (1/1) | 100.0% (3/3) | 8.6 s |
| **MVP Baseball 2005 (USA) — the control** | `SLUS-21135` | 100.0% (854/854) | 100.0% (46,196/46,196) | 100.0% (23,855/23,855) | 58.7% (34,675/59,060) | 0.3% (29/9,154) | 100.0% (4/4) | 67.2 s |
| **the six together** | | **99.8% (18,803/18,835)** | **99.9% (207,877/208,116)** | **99.9% (66,771/66,797)** | **62.6% (80,708/128,824)** | 6.2% (1,793/29,071) | **100.0% (103/103)** | 220 s |

`—` is *not applicable*: FIFA Street and FIFA 14 carry no `BNKl` bank at all.
Every one of these six also reads `—` on **containers, members, TDB, CRC sites,
MMAP and cache copies** in `readiness/TABLE.md`, and that is a measurement, not
a gap: the file-kind histogram in each record counts zero `TERF`, zero `TDB` and
zero `QL01` files on all six [M].

Column definitions, in the same shape as §2:

* **BIG archives** — `ea_big.parse_big` returned an archive, over every file
  whose magic is `BIGF`/`BIG4` **and** every nested archive found inside one
  (depth 2; nothing was left unopened on any of the six).
* **BIG entries** — the entry's stored bytes decoded as far as the 32-byte
  classify head: it is stored plain, or its RefPack stream started cleanly, and
  its table row addresses bytes the archive really holds.
* **RefPack** — the same over the packed entries only, plus every loose file on
  the disc whose first two bytes are a RefPack header.
* **SHPS images** — `ea_shps.decode_rgba` returned pixels, over **every image of
  every bank**. No sampling was used: 59,311 of 59,311 banks parsed, and every
  image in each was decoded or refused. The pixels are measured and dropped.

### 6.2 What runs unchanged, and it is most of it

**The archive layer is as solid here as the container layer is on the Madden
line.** 18,803 of 18,835 archives open, 207,877 of 208,116 entries classify and
66,771 of 66,797 RefPack streams start cleanly — 1,066,485,148 declared
decompressed bytes on FIFA 14 alone, none of it refused [M]. Every one of the
59,311 image banks parsed; **not one bank was refused on any disc** [M].

The size word is read correctly nearly everywhere: 18,799 opened archives report
a byte order the reader can name and **4** report `neither` (2 on NBA Street
Vol. 2, 2 on NBA Street V3) [M]. NBA Street Vol. 2 is the only disc where
**big-endian is the rule** — 26 of its 28 archives — against 18,771 little-endian
across the other five, which is the mixed byte order `EA_BIG_FORMAT.md`
documents. Big-endian is not unique to it, though: FIFA Street's `/DATA/FONTS.BIG`
and FIFA Street 2's `/DATA/IOP.BIG` are one each [M].

Audio splits the fleet the way it does in §3: NBA Street Vol. 2 and both FIFA
Street titles are **EA-XA end to end** (194/194, 25/25, 23/23), so the audio lane
could edit them today; MVP Baseball 2005 (29 of 9,154) and FIFA 14 (1,521 of
19,674) are MicroTalk speech and it could not [M].

### 6.3 What is refused, grouped by the reader's own sentence [M]

Three sentences account for 48,174 of the 48,413 refusals across the six discs,
and the fourth is one disc's own bookkeeping.

| the reader's sentence, numbers blanked | count | where |
|---|---:|---|
| `ea_shps.undecodable_reason` — *"image N ('tag') starts with block code 0xNN, which this reader does not decode; the block declares WxH in N byte(s), which is N.NNN byte(s) per pixel …"* | **48,116** | every disc but NBA Street Vol. 2 |
| `ea_big.parse_big` — *"… is a BIG4 archive. BIG4 stores its integers little-endian throughout, and no disc this reader has been measured against carries one, so it is refused by name rather than read with BIGF's mixed byte order."* | **32** | 18 on NBA Street V3, 8 on FIFA Street 2, 3 on FIFA Street, 3 on FIFA 14 |
| `ea_big.refpack_decompress` — *"… does not begin with a RefPack header: its first two bytes are c0 fb, and a RefPack stream's second byte is 0xFB with the family marker 0x10 in bits 0x3E of the first."* | **26** | 24 on NBA Street Vol. 2, 2 on FIFA Street |
| `ea_big.stored` — *"entry N ('name') wants N byte(s) at +N, past the N byte(s) the archive occupies."* | **239** | NBA Street V3 only: `/FE/ANIMSBH.VIV`, `/FE/OVLBH.VIV`, `/FE/ONLINE.VIV` |

The 48,116 image refusals, by block code, complete:

| code | images | what it is |
|---|---:|---|
| `0x0E` | 36,272 | the fixed-rate compressed art codec `EA_SHPS_FORMAT.md` measures at exactly 6 bytes per 4×4 block; §6.4 |
| `0x0D` | 8,699 | **a code MVP Baseball 2005 never carried.** 8,684 of them on FIFA 14, 9 on FIFA Street 2, 6 on NBA Street V3 |
| `0x01` | 2,178 | the one-pixel stub the reader refuses rather than guess a row layout for |
| `0x83` | 706 | FIFA 14 only |
| `0x0F` `0x0B` `0x0C` `0x0A` `0x08` `0x04` `0x03` `0x09` | 257 | eight further codes — 82, 49, 43, 33, 30, 8, 7 and 5 images — none of them in `ea_shps.CODE_NAMES` |
| `0x02` | 4 | not a codec refusal: four FIFA Street 2 images are 8-bit indexed with **no palette block after them**, which the reader refuses rather than draw grey |

**The `BIG4` refusal is the expensive one, and it is not expensive everywhere.**
On FIFA 14 the three refused archives are font sets (31 `FNTS` entries between
them) and nothing is lost. On FIFA Street the three include `/DATA/MODELS.BIG`,
which the committed disc map counts at **426 image banks and 276 nested
archives** [m] — the disc's largest art population, entirely behind the refusal;
this census reached 241 banks, the map reached 507. On NBA Street V3 the
eighteen include `/XF/PLAYER.VIV`, `PLAYER2S.VIV`, `PLAYER2X.VIV` and
`DYNBAN.VIV`; the map counts **17,239 banks** on that disc and this census
reached 2,739, so roughly **14,500 image banks sit behind `BIG4`** — more art
than `BIGF` exposes [M][m]. On FIFA Street 2 the eight include `FEART.BIG`
(143 banks, 1,841 images) [m].

`ea_big` refuses `BIG4` deliberately and says why: BIG4 is little-endian
throughout where BIGF is mixed, and no disc the reader had been measured against
carried one. Four of these six do. That is the single highest-value line in this
section: **teaching `ea_big` the `BIG4` byte order is one flag, and it unlocks
the largest art archive on three discs.**

### 6.4 Is `0x0E` the uniform-and-portrait codec on these discs too? [M]

On MVP Baseball 2005 and NBA Street V3, **yes, and completely.** On FIFA Street
it is only the front end. On FIFA Street 2 and NBA Street Vol. 2 it does not
appear at all. The per-archive counts the census now records say it plainly:

| disc | archive | images | drawn | refused | codes |
|---|---|---:|---:|---:|---|
| MVP Baseball 2005 | `/DATA/GHEAD.BIG` (head textures) | 8,400 | **0** | 8,400 | `0x0e` 8,400 |
| MVP Baseball 2005 | `/DATA/FRONTEND/PORTRAIT.BIG` | 2,391 | **0** | 2,391 | `0x0e` 2,391 |
| MVP Baseball 2005 | `/DATA/FRONTEND/UNIFORMS.BIG` | 862 | **0** | 862 | `0x01` 431, `0x0e` 431 |
| MVP Baseball 2005 | `/DATA/MODELS.BIG` | 30,535 | 21,779 | 8,756 | `0x0e` 8,756 |
| NBA Street V3 | `/FE/PLAYERS.VIV` (portraits) | 513 | **0** | 513 | `0x0e` 513 |
| NBA Street V3 | `/FE/LOGOS.VIV` `LOGOSLG` `LOGOSSM` `CHLOG` | 198 | **0** | 198 | `0x0e` 198 |
| NBA Street V3 | `/XF/BACOURT.VIV` (court + player art) | 2,790 | 2,477 | 313 | `0x01` 311, `0x03` 2 |
| FIFA Street | `/DATA/APTANIMS/FEART.BIG` (front end) | 1,305 | 148 | 1,157 | `0x0e` 1,157 |
| FIFA Street 2 | `/DATA/STADIUM/CAPITCH.BIG` | 327 | 213 | 114 | `0x01` 114 |
| FIFA 14 | `/DATA/ZDATA_02.BIG` | 10,128 | 132 | 9,996 | `0x0e` 8,795, `0x0d` 1,201 |
| FIFA 14 | `/DATA/ZDATA_01.BIG` | 11,734 | 3,300 | 8,434 | `0x0d` 7,472, `0x01` 392, `0x83` 353, and six more |

So the answer is per title, not per family. **NBA Street Vol. 2 draws every
image it has** — 7,679 under `0x02` and 511 under `0x05`, 8,190 of 8,190, the
only disc on the whole twenty-image fleet at 100% on its texture family [M].
FIFA Street 2 is next at 94.4%. NBA Street V3 keeps its entire identity art —
every player portrait and every team logo — under `0x0E`, which is the MVP
finding repeated on a different disc and a different year. And FIFA 14 raises a
**second** undecoded codec, `0x0D`, at the same scale as `0x0E`.

### 6.5 Where each title keeps its roster and team data [M]

The census probes every file and entry whose *name* is database-shaped and
records its magic, whether `ea_tdb.parse_tdb` opens it, and — when the bytes are
text — how many comma-separated names its first line declares. 157 probes across
the six discs. **Not one of them is an EA `TDB`.**

| title | where | what it is |
|---|---|---|
| MVP Baseball 2005 | `/DATA/DATABASE/DATABASE.BIG`, 18 RefPack entries | **plain-text CSV**, confirming the module plan field for field: `attrib.dat` 47 columns, `team.dat` 56, `lhattrib.dat` 29, `rhattrib.dat` 30, `manager.dat` 22, `org.dat` 15, `roster.dat` 11 [M] |
| FIFA Street | `/DATA/DATABASE/XDB*.ADF`, 21 loose files | a bespoke `ADF` table with **no magic at all**: the first little-endian word is a small count (`XDBPLAYR.ADF` 50, `XDBTEAMS.ADF` 16, `XDBCTEAM.ADF` 23), the second a second count, the third and fourth an identical pair of byte lengths |
| FIFA Street 2 | `/DATA/DATABASE/DB.BIG`, 29 RefPack `.adf` entries + `DB.BH` (magic `VivF`) | the same `ADF` shape, moved inside an archive: `xdbplayer.adf` `[67, 360, 48284, 48284]`, `xdbteams.adf` `[18, 23, 860, 860]`, `xdbplayerstat.adf` `[18, 362, …]` |
| NBA Street V3 | `/DATABASE/*.ADF`, 31 loose files | the same `ADF` shape: `XDBPLYR.ADF` 77,344 bytes `[109, 237, 51720, 51720]`, `XDBTEAM.ADF` `[23, 42, 1964, 1964]` |
| NBA Street Vol. 2 | `/DATABASE/XDB*.ADF`, 6 loose files (a tenth of V3's) | the same `ADF` shape: `XDBPLYR.ADF` 52,640 bytes `[101, 240, 48532, 48532]`, `XDBTEAM.ADF` `[11, 49, 1108, 1108]` |
| FIFA 14 | `/DATA/CMN/FIFA.DB` (2,931,794 bytes) + `META.DB` + `FE/{ENG,FRE,MEX}.DB` | **not** a TDB despite the extension and **not** text: first four little-endian words `[0, 4, 92, 15880]`, and `[0, 4, 1, 56]` on the three language files |

So the identity and ratings work costs, per family: a CSV parser on MVP, one
`ADF` reader shared by all four Street titles, and a sixth format on FIFA 14.
None of them costs a TDB reader or the four-CRC pass — and none of them gets one
for free either.

### 6.6 What a module for each would still need, over the scaffold

* **NBA Street Vol. 2** — a `C0 FB` decoder (24 loose files hold the whole front
  end: fonts, palettes, layout, `XAFEBG`, `XAPORTS`, `XATEAMS`), an `ADF` reader
  for six database files, and a rule for the two archives whose size word reads
  `neither`. Its art and audio lanes are done: 8,190/8,190 images, 194/194 EA-XA
  streams, 38/38 banks with 790 sounds.
* **FIFA Street 2** — the `BIG4` byte order (8 archives, `FEART.BIG` among them),
  an `ADF` reader, and a reading for `0x01`. 94.4% of its images already draw.
* **MVP Baseball 2005** — a `0x0E` decoder or the acceptance that portraits,
  heads and kits are `read-only-mapped`; a CSV writer that can change a row's
  length inside a RefPack entry, which the module plan already names as the wall;
  no new container work at all.
* **NBA Street V3** — the `BIG4` byte order first (it hides ~14,500 banks), then
  `0x0E` for every portrait and logo, then `ADF`, then a rule for the 239 entries
  in the three `.BH` shadow archives whose rows address bytes outside the file.
* **FIFA Street** — the `BIG4` byte order (`MODELS.BIG` is the disc's art), a
  `0x0E` decoder for the front end, and `ADF`.
* **FIFA 14** — the most work of the six: `0x0E` **and** `0x0D` (8,817 and 8,684
  images), a `FIFA.DB` reader that is neither TDB nor CSV, and a MicroTalk
  decoder for 92% of its audio. Its container layer is flawless — 16,572 of
  16,575 archives, 144,010 of 144,010 entries, 39,942 of 39,942 RefPack streams —
  and every lane above it is new format work.

---

## 7. The two predictions of the last pass, checked [M]

The last pass scored two titles from their committed disc maps alone and marked
the rows `[m]`, to be replaced by a measurement the day the disc was reachable.
Both are now measured, and the two predictions came out differently.

**NCAA Football 06 (`SLUS-21214`) — the pessimistic half was wrong.** Predicted:
container / member / cache lanes near NCAA Football 09's, the database lane
"subject to the same field-type-13 risk", and a whole art population outside the
module's readers. Measured on the NAS: 75/75 containers, 31,829/31,829 members,
**576/576 databases** — the field-type-13 risk did not materialise on this disc —
8,364/8,364 CRC sites, 496/496 cache copies and 1,112 of 1,160 sampled `MMAP`
images [M]. The art prediction stands but is now cheap: its **65 EA `BIG`
archives, 5,424 entries and 4,060 `SHPS` images** [m] are still `n/m` in
`TABLE.md`, because that page was rendered before the `BIG` rows existed. §6 says
what a re-run would find: `ea_big` opens `BIGF` archives on every disc measured,
and `ea_shps` draws every `0x02` image.

**MVP Baseball 2005 (`SLUS-21135`) — "not a domino" was wrong twice over.**
Predicted: "`ea_terf`, `ea_tdb` and `mmap_art` apply to **none** of it. Only
`ea_schl` would find anything, and only after a BIG walker exists. Not a domino."
The first clause is exactly right — 0 containers, 0 databases, 0 `MMAP` [M]. The
rest is not. The BIG walker **is** shipped, and it is the fork's own: `ea_big`
opens 854 of 854 archives, classifies 46,196 of 46,196 entries and unpacks
23,855 of 23,855 RefPack streams, and `ea_shps` parses 16,392 of 16,392 image
banks and draws 34,675 of their 59,060 images [M]. And `ea_schl` finding
"anything" turns out to mean 9,154 streams of which **29** carry a codec it
decodes: the audio lane is the one thing that does *not* carry over. §6 ranks
this disc seventh on the fleet, not last.

The general lesson holds and is worth keeping: the mapper's TDB reader is **more
permissive than `ea_tdb`** (it does not enforce the field-inside-the-record bound
that refused four NCAA databases in §5), so a map that reports "0 not the v8
layout" is still not a promise that `parse_tdb` opens them.

---

## 8. What the readers refused that looks like a defect, not a format difference

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

## 9. Ranked recommendation for the next modules

Weighing the share of readers that work unchanged, the size of the remaining
work, and the owner's stated interests. The six `BIG`-family discs of §6 are now
ranked in the same list rather than beside it; the five new entries are marked
**new**, and the two earlier rows they displaced say by how much.

| # | title | one reason |
|---|---|---|
| **1** | **Madden NFL 08** (`SLUS-21638`) | The only other title whose thirteen load-bearing table schemas are byte-identical to Madden 09's — same names, same widths, same bit offsets — on top of 100% on containers, members, databases and checksums, so the roster, identity, text and playbook lanes are a container list and a boot witness. Its 6,270 cache copies all resolve, where the control leaves two of its own unresolved. It is also the vehicle game of the owner's other project, and the community pack that covers it is a joint NCAA 06 + Madden 08 release [S]. |
| **2** | **Madden NFL 12 + Deluxe** (`SLUS-21946`) | The same 100% readings with the *least* remaining work of any non-08 disc: three `PLAY` widths the metadata-driven reader already absorbs, and **no preload cache at all**, which deletes the three-place edit rule the Madden 09 art writers spend most of their care on. |
| **3** | **Madden NFL 06** (`SLUS-21213`) | 100% on containers, members, databases and checksums with nine of thirteen tables identical; the remaining work is one `TEAM` string width, four `PLAY` fields, and a rule for the twelve cache copies the module cannot resolve. |
| **4** | **Madden NFL 2004** (`SLUS-20752`) | The deepest owner research on the fleet — this run measured its ELF CRC as `14F8B841`, the CRC the owner's 34 existing pnach patches target — and `COCH` shares 66 of 66 names, answering an open workstream as a read. Ranked below 06 only because its playbook tables are a different generation (`PBST` 27 fields against 5) and its uniform art is not where Madden 09 keeps it. |
| **5** | **NCAA Football 09** (`SLUS-21752`) | Sharing Madden 09's engine year buys the container, texture, cache and checksum lanes outright (100% on all four), and buys **nothing** for rosters and identity: 37 of 86 `PLAY` names shared, 29 of 113 `TEAM`. Worth doing as the first non-Madden module precisely because it separates "same engine" from "same data". |
| **6** | **NCAA Football 06** (`SLUS-21214`) — acquire first | The year the modding community actually works in [S], and its map predicts NCAA 09's position [m]. Not ranked higher because it is not on a machine this tool can reach, and because 65 BIG archives with 4,060 `SHPS` images sit outside every reader the module has. |
| **7** | **MVP Baseball 2005** (`SLUS-21135`) — **new**, was *do not schedule* | The `BIG` family's control, and 100% on all three of its own families — 854/854 archives, 46,196/46,196 entries, 23,855/23,855 RefPack streams — with the rosters in **plain CSV** inside one 18-entry archive, so the identity and ratings work that costs a TDB reader and the four-CRC pass on the Madden line costs a CSV parser here [M]. It also has a written plan already. |
| **8** | **NBA Street Vol. 2** (`SLUS-20651`) — **new** | The only disc on the whole twenty-image fleet that draws **every** texture it has (8,190/8,190) and opens every archive, with 194/194 EA-XA audio and 38/38 banks on top — the art and audio lanes are simply finished. Ranked below MVP only because 24 loose `C0 FB` files hold its entire front end and the reader refuses all 24 [M]. |
| **9** | **FIFA Street 2** (`SLUS-21369`) — **new** | 94.4% of its images draw with **no `0x0E` on the disc at all**, 100% of 1,797 RefPack streams unpack, and its rosters are 29 `ADF` tables in one archive; the only structural cost is the `BIG4` byte order for eight archives [M]. |
| **10** | **NCAA Football 2004** (`SLUS-20719`) — *was 7* | NCAA 09's schema problem plus four database refusals and the lowest texture yield of the modern discs; nothing here that NCAA 09 does not teach more cheaply. Displaced by three discs that each open ~100% of their own family and teach a format the fleet does not otherwise have. |
| **11** | **NBA Street V3** (`SLUS-21126`) — **new** | The same `ADF` rosters as Vol. 2 and a far worse art story: every player portrait and every team logo is `0x0E` (513/513 and 198/198 refused), and eighteen `BIG4` archives hide roughly **14,500 further image banks** — more art than `BIGF` exposes on that disc [M][m]. |
| **12** | **FIFA Street** (`SLUS-21147`) — **new** | Smallest of the four Street titles and the one whose largest art archive is behind the `BIG4` refusal (`MODELS.BIG`, 426 banks and 276 nested archives [m]); what remains is 66.4% drawable and one front-end archive of `0x0E`. |
| **13** | **Madden NFL 2001** (`SLUS-20093`) — *was 8* | Three format jobs before a single lane exists — a pre-v8 TDB reader, an LZM1 decoder and an `MMAP` v1 header path — bought for one prize the others do not offer: 99.3% of its audio is a codec the audio lane already decodes. Do it when audio is the goal, not when a module is. |
| **14** | **FIFA 14** (`SLUS-27093`) — **new** | A flawless container layer (16,572/16,575 archives, 144,010/144,010 entries, 39,942/39,942 RefPack) with **nothing above it**: two undecoded art codecs of similar scale (`0x0E` 8,817, `0x0D` 8,684), 92% MicroTalk audio, and a `FIFA.DB` that is neither a TDB nor CSV. The most measured disc on the fleet and the least reachable [M]. |

**Two claims in the owner's thesis that the measurement supports, and one it does
not.** The dominos do fall for the *container, texture, checksum and cache*
layers — 788 of 788, 71,262 of 71,262, zero differing cache copies, across eleven
years of discs. They fall for the *database* layer across the Madden line and
stop dead at the NCAA line and at 2001. And "shares Madden 09's engine year"
turns out to predict the container lanes and not the data lanes: NCAA Football 09
is the clearest case on the fleet of a disc that is 100% ready in every way
except the one a roster editor cares about.

**And a third the `BIG` half adds.** The dominos fall for the *archive* layer
too — 18,803 of 18,835 archives, 207,877 of 208,116 entries, 66,771 of 66,797
RefPack streams — but on that half of the fleet the wall moves from the database
to the **art codec**: 48,116 of 128,824 images are refused, 36,272 of them under
one block code. The Madden line's hard problem is a schema; the BIG line's hard
problem is a decoder, and it is the *same* decoder on five of the six discs.

---

## 10. Reproducing this

```
python3 tools/owner/ea_module_readiness.py --selftest
PYTHONPATH=. python3 tools/owner/ea_module_readiness.py --iso "<image>" --out <dir> --label "<Title> (USA)"
PYTHONPATH=. python3 tools/owner/ea_module_readiness.py --page <dir>/<SERIAL>.<label>.readiness.json \
    --baseline <dir>/SLUS-21770.Madden-NFL-09-USA.readiness.json --out docs/owner/scoping/readiness
PYTHONPATH=. python3 tools/owner/ea_module_readiness.py --summary <dir>
```

The six `BIG`-family discs of §6 were measured on the NAS, one process per disc
and all six at once, with no sampling anywhere:

```
PYTHONPATH=. python3 tools/owner/ea_module_readiness.py --iso "<image>" --out <dir> \
    --label "<Title> (USA)" --shps-sample 0 --nested-sample 0 --archive-depth 2
```

`--shps-sample 0` decodes **every image of every bank** rather than a sample per
archive, `--nested-sample 0` opens every nested archive, and `--archive-depth 2`
is deep enough that nothing was left unopened on any of the six.

The twenty `<SERIAL>.<label>.readiness.json` files sit beside the pages in
`docs/owner/scoping/readiness/`, so `--page` re-run on any of them reproduces its
page's every mechanical cell and a diff shows exactly what prose was added. They
carry counts, names, digests and schema field names and widths only; two tests
assert that no member payload and no byte of a CSV table reaches one.

Wall time: the ten of §1, 1,269 s single-threaded on this box. The six of §6,
220 s of CPU across all six — 11.7 s for FIFA Street, 25.5 s for FIFA Street 2,
99.9 s for FIFA 14, 7.0 s for NBA Street Vol. 2, 8.6 s for NBA Street V3 and
67.2 s for MVP Baseball 2005 — run concurrently on the NAS, peak 429 MB resident
on FIFA 14 and under 160 MB on every other disc. A 905 MB audio archive and a
413 MB texture archive are read through a memory map, never loaded.
`--shallow` skips every deep pass and answers the container and member rows in
about 30 s per disc. Nothing was written outside the output directory, no disc
was copied or modified, and nothing under `/mnt/c` was touched.
