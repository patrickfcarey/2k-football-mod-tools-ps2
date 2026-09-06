# Savestate diffs — reading a field's address off two screenshots

Two PCSX2 savestates of the same screen, one on-screen value apart, are a
controlled experiment. Everything the game changed by itself between them is
noise; the one thing the player changed is the answer. This page records the
first two runs of that experiment, the sieve that separates the two, and what
each answer unlocks.

Evidence tags: **[M]** measured here, on the artefact named; **[S]** sourced
from a document named; **[A]** assumed.

Numbers live in [`measured/savestate-diffs.json`](measured/savestate-diffs.json);
this page quotes it. The tool is
[`tools/owner/sstate_diff.py`](../../../tools/owner/sstate_diff.py) and it proves
every pass on bytes it builds (`--selftest`, 29 checks).

**Retail-free.** Everything below is an offset, a length, a count, a
four-character field name, a bit offset, a bit width, or one of the handful of
integers the owner's own screenshots put on screen. No RAM bytes, no strings,
no pixels, and no state file are in this repository. The savestates were read
from the rig read-only, copied to scratch, and the copies deleted.

---

## 1. The fifteen states

Captured 2026-09-06 on the rig, `~/.config/PenguinScreen2/sstates`. Each `.p2s`
is a zip; `eeMemory.bin` is 33,554,432 bytes of EE main memory and
`Screenshot.png` is what was on screen [M]. Every inventory row below is what
the pixels show, read one screenshot at a time.

| # | serial | title | slot | what the pixels show |
|---|---|---|---|---|
| 1 | SLUS-20051 | NFL Blitz 2002 | 01 | pre-game **TODAY'S MATCHUP** versus card; two crests, three play-call rings below |
| 2 | SLUS-20474 | NFL Blitz 20-03 | 01 | pre-game **TONIGHT'S MATCHUP** versus card; the same shape one year on |
| 3 | SLUS-20919 | ESPN NFL 2K5 | 01 | pre-game **LOADING**: two helmets on a studio shelf, and a seated presenter rendered with an unresolved texture — flat diagonal stripes where the suit should be |
| 4 | SLUS-21135 | MVP Baseball 2005 | 01 | **Baserunning** controller-tutorial card with a Loading… bar |
| 5 | SLUS-21135 | MVP Baseball 2005 | 02 | main menu, Play Now highlighted, portrait backdrop |
| 6 | SLUS-21135 | MVP Baseball 2005 | 03 | in-game at-bat behind the plate; batter lower-third with AVG / HR / RBI / H / OBP and a headshot inset |
| 7 | SLUS-21135 | MVP Baseball 2005 | 04 | **replay free camera** — infield view with the GAME CAMERA / FREE CAMERA transport bar |
| 8 | SLUS-21752 | NCAA Football 09 | 01 | pre-game rivalry loading card: two crests, series record, recent-history table, Loading… |
| 9 | SLUS-21752 | NCAA Football 09 | 02 | main menu (corkboard), PLAY NOW highlighted |
| 10 | SLUS-21752 | NCAA Football 09 | 03 | **SELECT CONTROLLER** team card with the pre-game uniform selector; `Uniform: Home`; 3D preview of player 7 in the dark kit |
| 11 | SLUS-21752 | NCAA Football 09 | 04 | the same screen, `Uniform: Away`, the same preview in the light kit. **Nothing else on screen differs.** |
| 12 | SLUS-21770 | Madden NFL 09 | 01 | SUPER SIM feature loading card, LOADING… |
| 13 | SLUS-21770 | Madden NFL 09 | 02 | main menu, PLAY NOW highlighted |
| 14 | SLUS-21770 | Madden NFL 09 | 03 | **VIEW ROSTERS**, one team sorted by OVR, top row selected; the panel reads jersey **54**, MLB, Ht 6'4", Wt 254, Yrs Pro 8, OVR 98; the six listed OVRs are 98 / 96 / 95 / 94 / 93 / 92 |
| 15 | SLUS-21770 | Madden NFL 09 | 04 | the same screen, jersey **56**. Every other pixel of the panel and the list is identical. |

Two pairs, then: **10 ↔ 11** (NCAA 09, kit) and **14 ↔ 15** (Madden 09, jersey).
The other eleven states are inventory, and three of them — the two main menus
and a loading card per title — are what told the sieve which memory is long-lived.

### A note for whoever captures the next set

`unzip` cannot read these. PCSX2 stores savestate members with zip compression
method **93 (Zstandard)**, and `unzip -p` yields *nothing* with exit status 0 for
those members while happily returning `Screenshot.png`, which is deflated [M].
That cost the first pass of this run. `sstate_diff.py` reads method 93, 8 and 0.

---

## 2. The sieve, and what it filtered

A naive diff drowns you. On the Madden pair, **1,097,719 of 33,554,432 bytes
differ — 3.271%** [M]. On the NCAA pair, **516,983 — 1.541%** [M]. The two
states are seconds apart on a static menu; almost all of that is frame counters,
timers, RNG, audio ring buffers, render and DMA packets, and heap churn.

Four passes, in the order they earn their keep.

**Pass 1 — cluster, and rank by shape, not size.** Grouping differing bytes into
runs with a 16-byte gap gives 2,915 runs (Madden) and 1,101 (NCAA) [M]. The
answer is nowhere near the top by size: Madden's largest run spans 196,608 bytes
and the answer spans **two**. The ranking that works is *isolation* — how many
other differing bytes lie within ±512. A menu value scores 1 or 2; a counter
inside a busy structure scores tens; a churning buffer scores hundreds. Both
NCAA candidates surface in the top six of that ranking [M].

**Pass 2 — search for the transition, not the difference.** A *w*-bit field
going *x* to *y* XORs its record by `(x ^ y) << p` for the field's bit offset
*p*. Sliding a little-endian window over every differing byte and trying every
`p` finds every site in the image that holds that value at any alignment,
byte-aligned or not. On the Madden pair that took 1,097,719 differing bytes to
**10 sites** for a 7-bit 54 → 56 [M]. This is the pass to run first whenever the
ground truth is known, and it is why the Madden case is the control: the method
had to find a known answer before the NCAA case was trusted.

**Pass 3 — attribute the address to the executable's own section table.** A PS2
boot ELF says where `.text`, `.data`, `.sdata`, `.sbss` and `.bss` live. That one
table turns an address into a *kind* of memory, and it is the strongest single
filter this run found:

| section | NCAA 09 differing | Madden 09 differing | what a hit here means |
|---|---:|---:|---|
| `.rodata`, `.text`, `.vutext`, `.vudata` | 0 | 0 | nothing changed in code or constants — a sanity check the diff passed |
| `.data` | **41** | 32 | an initialised global. Its default is on the disc, at a computable ELF file offset |
| `.sdata` | 25 | 18 | the same, small-data addressed |
| `.sbss` | 16 | 11 | a zero-initialised global; no disc image |
| `.bss` | 9,852 | 1,520 | the same, larger |
| `.stack` | 538 | 889 | transient |
| above the executable image | 506,511 | 1,095,249 | heap: 98% of the noise |

Of NCAA's 41 `.data` bytes, 39 are in seventeen runs that are plainly counters or
allocator pointers — they *increase* between the two states (6,477 → 6,761;
4,059 → 4,127; 1,003 → 1,045) [M]. **Two are clean 0 → 1 booleans.** That is a
two-candidate shortlist out of half a million bytes, from one table.

**Pass 4 — ask whether the hit is a record.** Scan the image for EA `TDB`
headers, read the resident table headers and field directories, and decode the
bytes at a candidate offset against them. This is what turns "these two bytes
changed" into "this is field *X* of record *n*".

**What was filtered, and why.** Some of it is worth naming because the next run
will meet it again:

- *Free-running counters.* Isolated single-byte changes that increment. They
  pass the isolation filter and fail the value filter, which is exactly why both
  filters exist.
- *A parity toggle.* NCAA's `.sbss` word at `0x007E5530` reads 1, 0, 1, 0 across
  states 01–04 [M] — it flips on every state regardless of screen, so it is a
  frame or double-buffer parity and not a choice.
- *Churning buffers.* Runs of 30 KB to 190 KB where nearly every byte differs.
- *Byte-aligned copies of the right value.* Madden's transition search found
  five byte-aligned sites holding 54 → 56 besides the answer [M]. They hold the
  right number; only one sits at a declared field offset inside a record array.

**What was not available.** This capture set holds **no second same-screen
pair**, so there was no differential noise baseline to subtract — the filter used
is structural. The Madden pair, whose answer is known, is the control that
proves it works. A future capture should add one deliberate no-op pair per title
(save, change nothing, save again); subtracting that would cut the candidate
list again for free.

---

## 3. Madden NFL 09 — does EE RAM hold `PLAY` in the disc's layout?

### Verdict: **yes, byte for byte and bit for bit.** [M]

The strong claim was: is the run that carries 54 → 56 a `PLAY` record laid out
with *the disc's* field offsets and bit widths, such that its neighbours decode
to the other values on screen? It is, and four independent facts say so.

**1. A whole disc database is resident, verbatim.** `/DATA/TEMPLATE.DAT`
member 2 — 21 tables, 369,524 bytes — sits at EE `0x01BEBF30` with a
**49,404-byte exact prefix** [M]: the database header, the table directory, and
every one of the 21 table headers and field directories are the disc's bytes
unchanged. The divergence begins 22,436 bytes into `PLAY`'s record array, i.e.
after about 170 records, which is where the game has written its own rows.

**2. The runtime `PLAY` table carries the disc's schema.** A second copy of the
same 127-entry field directory sits at `0x01DF70EC`, and a record array of
**1,986 records at stride 132** at `0x01DF95D0` [M]. Comparing that directory,
and the resident one, against the disc's `PLAY` field directory read straight
out of `TEMPLATE.DAT`: **127 of 127 fields equal in name order, type id, bit
offset and bit width** [M]. Not similar — equal.

The rows come from a *different* table: `TEMPLATE.DAT` member 1's `PLAY` holds
1,986 records at stride 104 with 110 fields (the roster layout, no contract
fields), and member 2's schema is the 132-byte, 127-field one. So the game
loads the narrow table and materialises it into the wide layout — and the wide
layout it uses is the disc's own, declared in the disc's own field directory [M].

**3. The change is exactly one field of one record.** Across the whole
262,152-byte record array, **two bytes differ** — `0x01DF99C7` and `0x01DF99C8`
[M]. They are byte 91 bits 6–7 and byte 92 bits 0–4 of record index 7, which is
`PJEN`: a 7-bit unsigned field the disc declares at **bit offset 734** [M].
734 ÷ 8 = byte 91 remainder 6. Decoding the whole record field by field: **one
field changed, `PJEN`, 54 → 56** [M].

**4. The neighbouring bits decode to the rest of the screen.** Reading record 7
with the disc's offsets:

| field | bit offset | width | decoded | what the screen showed |
|---|---:|---:|---:|---|
| `PJEN` | 734 | 7 | **54 → 56** | jersey 54 → 56 |
| `POVR` | 848 | 7 | 98 | OVR 98 |
| `PPOS` | 943 | 5 | 14 | MLB |
| `PHGT` | 983 | 7 | 76 | Ht 6'4" |
| `PWGT` | 256 | 8 | 94 | Wt 254 (the field stores lb − 160) [S] |
| `PYRP` | 795 | 5 | 8 | Yrs Pro 8 |
| `PAGE` | 566 | 6 | 30 | — |
| `TGID` | 549 | 10 | 1 | the team the list was filtered to |
| `PGID` | 534 | 15 | 224 | — |

And the whole visible list: filtering the 1,986 records to `TGID == 1` gives
**53 records**, whose six highest `POVR` are **98, 96, 95, 94, 93, 92** with
`PPOS` **14, 12, 15, 7, 19, 16** — MLB, DT, ROLB, C, K, CB — in that order [M].
That is the on-screen list, row for row, position for position, decoded out of
RAM with a schema read off the disc.

The record array itself lives **above the executable image**, i.e. on the heap
[M] — so this is not a static the ELF ships; it is a table the game builds at
load time and builds *in the disc's format*.

### What this unlocks

A RAM diff maps directly onto disc fields for this whole family. Any future
field question on an EA TDB title becomes: capture two states one value apart,
run `transition`, decode the hit against the disc's own field directory, done —
instead of guessing at a schema or hex-editing a save and rebooting.

**One sentence for the fleet:** thirteen of the mapped disc images carry EA `TDB`
tables and eleven of them are not this one — NFL Street, NFL Street 2 and 3,
Madden NFL 2004, 06, 08 and 12 (retail and Deluxe), and NCAA Football 2004, 06
and 09 — and because the format is self-describing and RAM keeps it verbatim,
every one of them can now be interrogated by pressing a button twice.

---

## 4. NCAA Football 09 — where does the uniform choice live?

### Verdict: **a 32-bit index in the boot ELF's `.data`, in a two-element per-side record. Its default is on the disc; the choice itself is in no database.** [M]

The module could not answer this because every uniform-shaped table on the disc
ships with **0 rows** [S — `docs/product/NCAA09_PS2_SCHEMA.md` §4a], so the
assignment had to be built at runtime. The diff names the bytes.

### (a) What shape is the changed value

**A small index — a 32-bit little-endian word taking 0 for the home kit and 1 for
the away kit.** Not a pointer, not a record, not a texture handle.

Of the 41 `.data` bytes that changed, two are clean 0 → 1 booleans and the other
39 are counters [M]. The one that decides it is at EE **`0x00737F60`**, and it is
a field of a **two-element array of 76-byte records** whose heads sit at
`0x00737F48` and `0x00737F94` — one per side of the matchup. The choice is at
**+0x18** of each record.

The record shape is not inferred from RAM. The ELF's own `.data` initialiser
contains the record head **exactly twice, 76 bytes apart** [M], and its `+0x18`
words ship as **0 and 1** — home kit for side 0, away kit for side 1. That is
the state observed in the untouched loading-screen state and in the pre-change
uniform state, and the player's press wrote 1 over side 0's word.

The second `.data` boolean, `0x007374BE`, also went 0 → 1. It is one byte of a
zero-initialised 0/1 array whose set members are scattered rather than paired per
side, so it reads as a "this option was touched" flag rather than the choice
[A]. Its meaning is not established and nothing here rests on it.

### (b) Is it near anything identifiable

Yes, and the neighbour is what confirms the object. **858 bytes below** the
uniform word, at `0x00737C04` and `0x00737C06`, sit **two 16-bit team ids** [M].
They were checked against two different fixtures in this capture set: in the
loading state they read 67 and 35, and in the uniform pair they read 61 and 60 —
which are the school-catalogue ids of the two schools each screenshot names, in
both cases [M]. They are unchanged across the pair, as they must be.

So the uniform word is a field of the **game-setup object**: the same `.data`
structure that carries who is playing whom.

It is **not** near a texture address. The render-side consequence is elsewhere: a
pair of heap pointers at `0x0085A3A4` / `0x0085A3A8` in `.bss` **exchange
places** across the pair, swapping which of two 72-byte objects each side is
bound to [M]. That is the effect, not the cause.

### (c) Does anything on the disc correspond to it

**Two answers, and the distinction is the point.**

**No database row — measured, not assumed.** `/DATA/TEMPLATE.DAT` member 0 (49
tables, 153,504 bytes) is resident at EE `0x01D52AE0` with a 61,292-byte exact
prefix and an 87,392-byte resident extent [M]. That extent contains all four
kit-shaped tables the schema page names, present and empty:

| table | fields | bytes/rec | rows resident | bytes that changed |
|---|---:|---:|---:|---:|
| `CTCD` | 45 | 108 | 0 | 0 |
| `CTUN` | 28 | 76 | 0 | 0 |
| `USTG` | 19 | 40 | 0 | 0 |
| `USLG` | 11 | 24 | 0 | 0 |

**Across the entire 87,392-byte resident extent, zero bytes differ** when the
on-screen uniform flips [M]. The disc's "the table is not there" is now also a
runtime measurement: the table is there, it is loaded, it is empty, and the game
does not write the choice into it.

**But the default *is* on the disc.** The word lives in `.data`, which is an
*initialised* section, so the disc's boot ELF carries its starting value at a
computable file offset:

| what | EE address | ELF section | ELF file offset | disc image byte offset | ships as |
|---|---|---|---|---:|---:|
| side 0's kit | `0x00737F60` | `.data` | `0x00638F60` | 1,573,898,080 | 0 (home) |
| side 1's kit | `0x00737FAC` | `.data` | `0x00638FAC` | — | 1 (away) |

So "purely a runtime menu variable with nothing on the disc to write" is *almost*
right and the correction is useful: there is nothing in a **table**, and there is
something in the **executable**. Changing the shipped default is an ELF
`.data` byte patch, which is a code-patch lane, not a database lane.

**The assumption that would make this wrong.** That the choice is not also
persisted to a memory-card save. This capture set holds no memory-card image, so
persistence was not tested. A save written before and after the change would
settle it, and until then the claim is "no *disc* database row", not "nowhere".

### (d) What it means for the Uniforms page's rung

**Nothing changes, and now that is a finding rather than a silence.** The page's
two rows — `uniforms.texture_census` at `extract-only` and
`uniforms.disc_art_writer` at `offline-writer-proved` — are correctly scoped:
a school's kit on this disc *is* its `MMAP` textures, and the Home/Away selection
is a two-word default in the executable that no editor of kit art needs to touch.
The page owes no database lane, and the reason is now measured in the running
game instead of inferred from an empty table.

Recommendations, as recommendations — **these files were not edited**:

| file | what to add |
|---|---|
| `docs/product/NCAA09_PS2_SCHEMA.md` §4a | the RAM measurement: member 0 resident at EE `0x01D52AE0`, all four kit-shaped tables present with 0 rows, **0 bytes changed** across the resident extent when the uniform flips. The "no equivalent" is now measured in the running game. |
| `docs/product/NCAA09_PS2_ART_PAGES.md`, the uniforms page | one line: the pre-game Home/Away selection is a 32-bit index at `+0x18` of a 76-byte per-side game-setup record (EE `0x00737F60` / `0x00737FAC`; disc defaults 0 and 1 at ELF file offsets `0x00638F60` / `0x00638FAC`), not a record in any table. It does not change either row's rung. |

---

## 5. The tool

`tools/owner/sstate_diff.py`, standard library plus the `zstd` command:

```bash
python3 tools/owner/sstate_diff.py inventory  DIR
python3 tools/owner/sstate_diff.py diff       A.p2s B.p2s
python3 tools/owner/sstate_diff.py transition A.p2s B.p2s --from 54 --to 56 --width 7
python3 tools/owner/sstate_diff.py sections   A.p2s B.p2s --elf BOOT.ELF
python3 tools/owner/sstate_diff.py tdb        A.p2s B.p2s
python3 tools/owner/sstate_diff.py record     A.p2s B.p2s --at 0x01DF996C --schema S.json
python3 tools/owner/sstate_diff.py --selftest
```

`--selftest` builds a synthetic state pair — a static backdrop, a churning
buffer, scattered counters, a bit-packed record array with one 7-bit field that
moves 54 → 56, a small `TDB` with its own header and field directory, and a
minimal ELF — and proves all four passes on it, 29 checks, no game data
[M: `SSTATE_DIFF_SELFTEST_PASS checks=29`]. `extract` refuses to write a member
inside a git checkout, because an EE image and a screenshot are payload.

Bit order is the shared reader's: least-significant-bit first, within each byte
and within the field [S — `mod_editor/games/_formats/ea_tdb.py`].

---

## 6. What the next agent should not have to rediscover

1. **PCSX2 savestate members are zstd (zip method 93).** `unzip -p` returns
   nothing and succeeds. Use `sstate_diff.py`.
2. **A PS2 boot ELF's section table is the best first filter on a RAM diff.**
   `.text` differing at all means the diff is wrong; `.data` differing points at
   a global whose default is on the disc.
3. **Madden NFL 09's runtime `PLAY` table** is 1,986 records at stride 132 with
   the disc's 127-field schema, materialised from `TEMPLATE.DAT` member 1's
   110-field / 104-byte rows. `PJEN` is bit 734, width 7.
4. **NCAA Football 09's game-setup object** is in `.data`: two 16-bit team ids at
   `0x00737C04` / `0x00737C06`, and a two-element 76-byte per-side record at
   `0x00737F48` whose `+0x18` word is the kit index.
5. **Capture a no-op pair.** One extra savestate per title, taken with nothing
   changed, would give every future run a differential noise baseline this one
   did not have.
