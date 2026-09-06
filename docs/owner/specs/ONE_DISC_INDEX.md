# One disc index

**Specification.** One walk over a PlayStation 2 disc produces one artefact; every tool that
today walks the disc for itself reads that artefact instead. This document decides the artefact,
where it lives, who regenerates it, which code owns "what format is this", what each consumer
stops doing, how much of a member has to be read, how to land it, what it costs, and what it does
not fix. It is written to be built in one pass, so every section is a decision, not a survey.

> **Evidence tags.** **[M]** measured this session on the artefacts named, by
> `tools/owner/prototypes/disc_index/`; the numbers are in
> `docs/owner/specs/measured/disc-index-roundtrip.json` and
> `docs/owner/specs/measured/disc-index-consumers.json`. **[S]** sourced from a named document.
> **[A]** assumed. An untagged claim is `[A]`.
>
> **Status: specified, prototyped, not built.** Nothing under `mod_editor/`, `packaging/` or
> `tools/` outside `tools/owner/prototypes/` changed. `tools/owner/ea_disc_map.py` and
> `ea_module_readiness.py` are described here and were not touched.

---

## 1. Why: three independent walkers disagreed, and the disagreements were filed as documents

The cheap argument for one index is that nine tools walk the same disc. The real argument is
that they walk it *differently*, and when they disagree there is nowhere to fix it.

### 1.1 The three corrections already on record

**`CPTH` written as `HTPC`.** `ea_disc_map.py` prints a head it cannot name as
`other:43505448` — the forward hex of the first four bytes. Read that hex as a *number*, spell
the number's bytes out, and you get `HTPC`. The owner's scoping study did exactly that and
published `.cap` = "members beginning `HTPC`" (`BLITZ_AND1_FORMATS.md` §4.1, §6.1, §5). The
bytes on the disc are `CPTH` — camera path. Two module agents found it independently and filed
the correction in their own module documents rather than in the mapper:

> "**`CPTH` (the study's `HTPC`) — yielded, and a correction.** The scoping study names this
> family `HTPC`, which is its tag read as a little-endian *word*; the bytes on the disc are
> `CPTH`." — `docs/product/NFLBLITZ2002_PS2_MODULE.md` §5, and the same sentence in
> `docs/product/measured/nflblitz{2002,2003}_ps2/probes.json`.

The scoping study still says `HTPC`, in five places, today.

**`.dff` written off as "not RenderWare".** `ea_disc_map.renderware_section` accepts a
RenderWare stream only when `section bytes + 12 == the file`. That is the rule for a stream that
is exactly **one** section. All 2,708 `.dff` members across the two Blitz discs fail it, so the
map left them as a raw magic and the study wrote:

> "**What a `.dff` is on the Blitz discs.** The first word is RenderWare's clump id but the
> section-length rule fails on all 2,708 of them across the two discs [M]. Either Midway wrote a
> variant or the id is a coincidence; the map does not choose." — `BLITZ_AND1_FORMATS.md` §6.2

Neither. They are ordinary multi-section RenderWare — `Clump` then `Extension` — and the
product's own `rw_txd.walk` already knew how to walk them. The module answered it:

> "**`.dff` — answered.** … a walk over the whole member consumes it exactly on 1,043 of 1,272
> and 1,167 of 1,436 … the map's rule was the wrong rule for a multi-section file."

**And a third, unfiled, found while writing this.** The same study calls four `.ban` members
"`BAKE`". The bytes are `EKAB` [M]. Nobody has corrected it because nobody has needed to open a
`.ban` yet. The pattern is not two mistakes; it is a defect in how an unnamed head is
*reported*, and it will keep producing mistakes.

### 1.2 Why the corrections could not be applied once

There is no one identifier to fix. "What format is this run of bytes" is answered in at least
seven places today, with three different vocabularies:

| Where | Vocabulary for an unnamed run |
|---|---|
| `ea_disc_map.identify_head` (file level) | `other:<forward hex>`, plus `PS2-ICO` / `zero-head` |
| `ea_disc_map` member level, via `ea_terf.identify_member` | `unclassified` — knows neither `PS2-ICO` nor `zero-head` |
| `ea_big.entry_format` | `FORMAT_UNCLASSIFIED` / `FORMAT_UNDECODABLE` — two answers where the mapper has one |
| `ea_module_readiness` | per-reader "did it parse", grouped by refusal sentence |
| `mod_editor/games/*/containers.py` × 5 | per-game magics and suffix rules |
| `mod_editor/games/_formats/*.py` magics | the shipped tables, one per family |
| the 29 scratch walkers of one day | whatever the agent typed |

The mapper and `identify_member` disagreeing about `PS2-ICO` is harmless. The mapper and the
module disagreeing about `CPTH` is not, and only one of them can be right. **A single identifier
means a misidentification is fixed once and every consumer inherits the fix.** That is this
document's first purpose; the speed is the second.

### 1.3 The cost side, for completeness

Nine permanent walkers, 10,052 lines [M]:

| File | Lines |
|---|---:|
| `tools/owner/ea_disc_map.py` | 3,161 |
| `tools/owner/ea_module_readiness.py` | 2,666 |
| `tools/mvp05_ps2_texture_identities.py` | 1,891 |
| `tools/ps2_texture_identities.py` | 1,501 |
| `mod_editor/games/madden09_ps2/inventory_lane.py` | 340 |
| `mod_editor/games/ncaa09_ps2/inventory_lane.py` | 310 |
| `mod_editor/games/mvp05_ps2/inventory_lane.py` | 183 |

Plus **29 throwaway walkers in one day** — 7 under `mvp05-id-out/`, 22 under `blitz-pak-out/`
[M] — each of which rediscovered what files the ISO holds, what container each file is, and what
members each container holds, before getting to its actual question.

---

## 2. The artefact

### 2.1 Shape

**One JSON Lines file per disc image**, named `<SERIAL>.<label-slug>.index.jsonl`. Four row
kinds, each self-describing under a `row` key, emitted in walk order.

```
{"row":"disc",      …}   exactly one, first
{"row":"file",      …}   one per ISO9660 file
{"row":"container", …}   one per container opened, at any depth
{"row":"member",    …}   one per member of a container, at any depth
{"row":"totals",    …}   exactly one, last: counts and wall seconds
```

**`disc`** — `schema`, `serial`, `label`, `image_bytes`, `sector_size`, `files`, `boot_file`,
`boot_elf_sha256`, `pcsx2_crc`, `image_sha256` (when asked for), `walk` (`head` or `deep`),
`head_bytes`, `tool_version`, `produced_utc`.

**`file`** — `path`, `bytes`, `lba`, `ext`, then the identity block (§4.2).

**`container`** — `key` (the file path, or `parent!index` / `parent!name` when nested), `kind`,
`depth`, `bytes`, `members`, `shape` (per-family: a TERF chain and alignment, a ZIP central
directory offset, a `.ZIH` variant, a `PAK ` directory span), or `refused` with the reader's own
sentence.

**`member`** — `key`, `container`, `index`, `name` when the container names it, `ext`, `offset`,
`size` (decompressed), `stored_size`, `codec`, `depth`, the identity block, and in a `deep` walk
`stored_sha256` plus `payload_crc32` where the container declares one.

### 2.2 What a row carries beyond the identity

Cheap shape facts, per family, produced by the rule that earned the identity:

| Family | Facts | Read |
|---|---|---|
| `MMAP` | version, width, height, format id | 64-byte window |
| `SCHl` | platform **name**, channels, codec, codec2, rate | 96-byte window |
| `TDB` | version, table count; in a deep walk every table's name, stride, row count and each field's `[name, type, bits, offset]` | header / whole member |
| RenderWare | first section id, library version, section count, top-level sequence, `walk_consumes_the_member`, `one_section_accounts_for_the_file` | 12 bytes per top-level section |
| `CPTH` | record count, header words 1 and 3 | 16-byte window |
| `WIFF` | form type, declared body bytes | 12-byte window |
| ZIP member | stored CRC-32 from the archive's own directory | directory only |
| `.ZIH` record | name, size, data offset, CRC-32 when the shape has one | directory only |

### 2.3 What it deliberately does not carry

An index that describes meaning as well as shape describes neither well. It does **not** carry:

- **Decoded pixels or any digest of them.** A texture identity depends on a decoder version, a
  palette convention and an alpha rule; `docs/product/measured/*/pcsx2-texture-identities.json`
  is that artefact and it stays separate. The index says *where the textures are*.
- **Records.** A TDB's schema is in; a row of it is never in.
- **Any string that came out of a member.** A member's *name* is a container directory entry and
  is structure; a line of game text is payload. §3.3 is the rule and it is executable.
- **Meaning.** No "this is the roster", no lane assignment, no rung, no team attribution. Those
  belong to a module, which reads the index and adds them.
- **Judgement about a rule that failed.** A RenderWare id whose walk does not consume the member
  is recorded as `RW-CLUMP?` with the sequence it did consume. The index states the measurement;
  it does not conclude "not RenderWare".

### 2.4 Format: JSON Lines. Measured, not asserted

Measured on the NCAA Football 09 deep index, 37,017 rows [M]:

| operation | JSONL | one JSON | SQLite |
|---|---:|---:|---:|
| bytes | 15,087,828 | 15,124,845 | 18,726,912 |
| filter without a reader (`grep -c`) | **0.013 s** | not possible | not possible |
| parse every row | 0.381 s | 0.289 s | — |
| indexed query | — | — | 0.0007 s (+0.53 s to build) |

**JSONL, because of how consumers actually read.** An agent greps and then loads: `grep` on
JSONL answers a whole-disc question in 13 ms with no reader at all, which is the single most
common access and the one the other two formats cannot serve. A lane loads the rows for one
container: 0.38 s for the whole file is below the noise floor of a consumer that was previously
spending 15 to 953 s walking. The readiness tool aggregates across the fleet: it streams 28
files and never holds two. A single JSON saves 0.09 s on the parse and gives up `grep`,
streaming, appending and a line-oriented `git diff`. SQLite's indexed query is 500× faster than
a full parse and saves 0.38 s on a 15 s task, in exchange for a binary artefact `git` cannot
diff and `grep` cannot read; a consumer that ever needs indexed queries builds one from the
JSONL in 0.53 s, which is the right place for that cost.

---

## 3. Where it lives, who regenerates it, and what refuses a stale one

### 3.1 A content-addressed cache on the NAS is the store; nothing is checked in

The index is a **derived artefact keyed on the disc image's own sha256**:

```
/turret/builds/2k5/disc-index/<image sha256>/<SERIAL>.<label-slug>.index.jsonl
/turret/builds/2k5/disc-index/<image sha256>/index.meta.json
```

`index.meta.json` carries `image_sha256`, `serial`, `label`, `tool_version`, `walk`
(`head`/`deep`), `head_bytes`, `produced_utc`, and the sha256 of the JSONL itself.

The key is the image, so **a stale index is not representable**: a different disc is a different
directory, and there is nothing to invalidate. The NAS is already the build host and already
holds the disc corpus at `/turret/builds/discs/ps2/`; putting the index beside it means one
place has every disc and every index. A dev-box run writes to `~/.cache/2k5-disc-index/<sha>/`
under the same layout and is interchangeable.

**The repository gets no index and no copy of one.** A checked-in artefact that drifts is worse
than none, and this one would drift on every mapper change.

### 3.2 What the repository keeps, and what refuses a stale one

Two things, both small, both already the pattern here:

1. **Rendered pages stay checked in, unchanged in kind**: `docs/owner/disc_maps/<SERIAL>.*.map.md`,
   `docs/owner/scoping/readiness/*.json`, `docs/product/measured/<game>/*.json`. Every one of
   them gains a `disc_index` provenance block:
   ```json
   "disc_index": {"image_sha256": "...", "index_sha256": "...", "tool_version": "disc_index/1"}
   ```
2. **One gate**: `tools/owner/check_disc_index_provenance.py`, run by `integrate_gate.sh`.
   For every checked-in document carrying a `disc_index` block it asserts the named index exists
   in the store and its sha256 matches. It **does not** rebuild and it does not need a disc: a
   missing or changed index is a refusal naming the document and the command that rebuilds it.

That is the whole staleness contract. A document whose index has been rebuilt fails the gate
until the document is regenerated, which is exactly the coupling that is missing today: the
NCAA 09 page in `docs/owner/disc_maps/` was written by `ea_disc_map/v2` and the mapper is now
`v3`, and nothing anywhere says so.

**Regeneration is one command, and it is the only one:**

```bash
PYTHONPATH=. python3 tools/owner/disc_index.py --iso <image> --label "<Title> (USA)" [--deep]
```

It writes into the store, keyed on the image's hash, and prints the key. Every consumer takes
`--disc-index <path>` **or** `--iso <image>`; given an image it looks the index up by hash and
refuses with the command above if it is absent. No consumer builds an index as a side effect,
because a tool that silently spends 20 s building one is a tool nobody can reason about.

### 3.3 Retail-free, and the proof

**Rule.** A row may carry: a file or member **name** as the container's own directory spells it;
an offset; a length; a count; a format identity; a four-byte tag; a schema field name, type and
bit width; and a digest. **Nothing else that came off the disc.** Specifically elided:

- the head window itself — only the identity derived from it, plus the 4-byte tag, survives;
- every byte below a member's header;
- every decoded pixel, palette entry, audio sample and database record;
- any string read *out of* a member, including a text member's lines and a TDB's row values.

A four-byte tag and a schema field name are the format, identical on every copy of the game, and
the charter already permits them (`MODULE_AGENT_CHARTER.md` §3); disc maps have published both
for months.

**The proof is a function, not a promise.** `retail_free_violations(index)` walks every row of a
built index and flags any string that is neither in the allowed-name set nor a digest field: a
hex run of 9+ characters outside `magic`/`crc32`/`sha256`/`library_version`, or any value longer
than 120 characters. It is the first thing the round-trip runs and it is a gate on the real
builder.

**Measured: 0 violations on all three indexes** — NFL Blitz 2002, NFL Blitz 2003, NCAA Football
09 [M].

---

## 4. The identifier, singular

### 4.1 Which code becomes authoritative

**A new owner-side module, `tools/owner/disc_identify.py`, is the single answer to "what format
is this run of bytes", and it is the only place a magic table, a tag spelling or a structural
rule lives.** It is **not** shipped and it does **not** move into `mod_editor/games/_formats/`.

Why owner-side and not product:

- The product's `_formats` packages answer a *narrower* question — "can **this reader** open
  this?" — and their magic tables exist to guard their own parsers. `ea_big.entry_format`
  distinguishing `unclassified` from `undecodable` is a fact about `ea_big`, and it must stay
  that way.
- The identifier's job includes naming families **no shipped reader can open** (`RYWM`, `EKAB`,
  `Part`, `WIFF` beyond its head). Putting speculative names into shipped code invites a lane to
  claim a rung it has not earned.
- The release allowlist, the registry and the count pins all move when `mod_editor/` moves.
  A census vocabulary that changes whenever a new disc is scoped does not belong there.

**How the others consume it, without a second table anywhere:**

- `disc_identify` **imports** the shipped magic constants rather than copying them:
  `ea_terf.MEMBER_FORMAT_MAGICS`, `ea_big`'s RefPack signature, `rw_txd`'s section ids,
  `blitz_zip`'s shapes. Where a shipped reader knows a magic, that reader is the source; where no
  reader exists, the tag lives in `disc_identify` and nowhere else.
- Shipped `_formats` packages **do not import** `disc_identify` — owner code may depend on
  product code, never the reverse.
- `ea_disc_map.py` and `ea_module_readiness.py` delete their own tables and read the index.
- Each `containers.py` keeps its suffix conventions (`.dff` means model on a Blitz disc) and
  stops keeping magics.
- A scratch walker imports `disc_identify` in one line instead of typing a magic table.

### 4.2 The identity block a row carries

```json
{"format": "CPTH", "tag": "CPTH", "magic": "43505448",
 "rule": "16 + records * 32 == the member",
 "shape": {"records": 466, "header_word1": 7, "header_word3": 0}}
```

Five fields, each load-bearing:

- **`format`** — the canonical name. `unknown` is a measured answer. A name ending `?` means a
  published id matched but its structural rule did not hold — a question recorded, never a
  conclusion.
- **`tag`** — `head[:4]` as **forward ASCII**, or `null` when a byte is not printable.
- **`magic`** — `head[:4]` as **forward hex**, always.
- **`rule`** — the arithmetic that earned the identity, in words, or `null` for a bare magic
  match. A rule that could have failed and did not belongs in the artefact.
- **`shape`** — the cheap facts the rule produced on the way.

`tag` and `magic` are both present on purpose. Every reversal EA and Midway perform is recorded
**once**, in a table keyed by the bytes as they lie on the disc:

```python
REVERSED_MAGICS = ((b" KAP", "MidwayPAK", "PAK "),)   # 'PAK ' stored as a native u32
```

### 4.3 The two corrections, as one-line fixes under this design

**`CPTH`.** The defect is that `other:43505448` is the *only* rendering, and it is ambiguous
between a tag and a number. The fix is one field:

```python
def tag_text(head: bytes) -> Optional[str]:
    raw = bytes(head[:4])
    return raw.decode("ascii") if len(raw) == 4 and all(0x20 <= b < 0x7F for b in raw) else None
```

Every row for those members then reads `"tag": "CPTH", "magic": "43505448"`. The scoping study,
the two module documents and the mapper all quote the same field, and the spelling `HTPC` cannot
be produced by any of them. Verified: 85 members on Blitz 2002 and 88 on Blitz 2003, forward tag
`CPTH` on all 173, one distinct magic `43505448` [M]. The unfiled `EKAB`/`BAKE` case is fixed by
the same line, at the same moment, without anyone noticing it was broken — which is the point.

**`.dff`.** The defect is a single-section rule applied to a multi-section format. The fix is
one loop where there was one comparison — the mapper's

```python
return section_id if section_bytes + 12 == size else None
```

becomes the walk `rw_txd.walk` already implements, with the same stop rule (a section whose
declared body runs past the end is not counted), and the walk's evidence travels in `shape`.
Verified: 1,043 of 1,272 `.dff` on Blitz 2002 and 1,167 of 1,436 on Blitz 2003 walk to the byte,
matching the module's published counts exactly; **0** of either satisfy the old one-section rule
[M]. The remainder are `RW-CLUMP?` — a recorded question, with its sequence, not a verdict.

Both fixes are in `tools/owner/prototypes/disc_index/identify.py` and each has a test that fails
if it regresses (`tests/owner/test_disc_index_prototype.py`, 25 tests).

### 4.4 One vocabulary, and how the old ones are recovered

The index names strictly **more** than `identify_member` does, so every existing count is a
*projection* of the index, computed by two functions and no re-walk:

```python
as_mapper_names_a_file(row)    # unknown / RW-*?  ->  "other:<magic>";  PS2-ICO, zero-head kept
as_mapper_names_a_member(row)  # unknown / RW-*? / PS2-ICO / zero-head  ->  "unclassified"
```

Measured on NCAA Football 09: the index names 36 level-1 members the mapper leaves unclassified
(11 `PS2-ICO`, 3 `zero-head`, 22 speculative RenderWare), and 7,015 + 36 = **7,051**, the
mapper's published figure to the unit; at every depth 10,304 + 308 = **10,612**, likewise [M].

---

## 5. Consumers: what each one stops doing

Measured with `ast` over exact line spans at this branch's head
(`docs/owner/specs/measured/disc-index-consumers.json`) [M]. Three buckets kept apart because
they are three different claims: **moved** leaves the file but survives in the indexer;
**deleted** is duplicate work that goes away; **partial** is a named line range inside a function
that stays.

| Consumer | File | moved | deleted | partial | removed from this file |
|---|---:|---:|---:|---:|---:|
| `tools/owner/ea_disc_map.py` | 3,161 | 1,131 | 331 | 0 | **1,462 (46.3%)** |
| `tools/owner/ea_module_readiness.py` | 2,666 | 0 | 305 | 0 | **305 (11.4%)** |
| `mvp05_ps2/inventory_lane.py` | 183 | 0 | 31 | 17 | **48 (26.2%)** |
| `ncaa09_ps2/inventory_lane.py` | 310 | 0 | 14 | 40 | **54 (17.4%)** |
| `madden09_ps2/inventory_lane.py` | 340 | 0 | 14 | 40 | **54 (15.9%)** |
| `tools/ps2_texture_identities.py` | 1,501 | 0 | 0 | 15 | **15 (1.0%)** |
| `tools/mvp05_ps2_texture_identities.py` | 1,891 | 0 | 0 | 39 | **39 (2.1%)** |
| **total** | **10,052** | **1,131** | **695** | **151** | **1,977 (19.7%)** |

**`ea_disc_map.py` becomes a renderer over an index.** It reads file kinds, container chains,
alignments, codecs, member formats and shape facts, TDB schemas, archive entries and the non-EA
family blocks. Moved: the 35 walk/parse/identity functions and `_Extent`/`_View`. Deleted: the
331 lines of `map_disc`, `totals_of`, `foreign_totals` and the four statistics helpers, which
aggregate rows the index already has. Kept: `render_markdown`, `render_foreign`, `render_page`,
`render_summary`, `render_compare` and the CLI. This is the largest single win and it is honest
about its shape: 1,131 of those lines move rather than vanish.

**`ea_module_readiness.py` keeps every reader and stops hunting for targets.** "Can `ea_terf`
open this member" is a question about the product and no index answers it, so every `measure_*`
that runs a shipped reader stays. What goes is `measure_disc`'s enumeration, `_evenly`'s
sampling, `measure_loose_archive`, `size_field` and the two schema-shape helpers — 305 lines.
The gain is larger than the line count: `DEFAULT_MMAP_SAMPLE = 48` exists because finding and
decoding members is expensive, and with the index the tool knows every MMAP member's location
before it starts, so the sample becomes a decode budget rather than a discovery budget.

**The three `inventory_lane.py` files (833 lines) read the census instead of taking it.**
`mvp05`'s `_count` (31 lines) and both `_member_format` helpers vanish; each `build_catalogue`
loses its disc walk (17, 40, 40 lines). The quality gain is bigger than 156 lines: `ncaa09` and
`madden09` classify only the first `FORMAT_SAMPLE` members of each container because a full walk
is too slow, and publish `formats_sampled` to say so. From an index, every member's format is
already there and the cap disappears.

**The two identity tools save almost nothing, and that is the honest answer.** They pair *decoded
pixels* with a PCSX2 dump; the index carries no pixels and never will (§2.3). What it replaces is
the enumeration at the top of each `index_disc` — 15 lines in `ps2_texture_identities.py`, 39 in
`mvp05_ps2_texture_identities.py` — which is 1.0% and 2.1% of those files. The second tool's own
docstring already reaches the same conclusion: *"the three readers here (`scan_dump`, `pair`,
`derivation_check`) are the parts worth lifting; the disc walk is not."* Anyone selling this
proposal on those two files is selling it wrongly.

**The scratch walkers are where the real saving is, and it cannot be measured in lines.** The 29
throwaway scripts of 2026-09-06 each opened the ISO, walked the archives and classified entries
before reaching their question. `mvp05-id-out/index_disc.py` is 132 lines of which ~55 are that
preamble. With an index the preamble is `regen.load(path)` and a list comprehension.

---

## 6. Bounded reads: what needs a window and what needs a member

`EFFICIENCY_REVIEW.md` proposal 8 measured a 65,576-byte LZH1 member [S]:

| decode | time |
|---|---:|
| 32 bytes (classify) | 0.324 ms |
| 64 bytes (MMAP header) | 0.340 ms |
| 96 bytes (SCHl header) | 0.401 ms |
| **whole member** | **55.954 ms** |

**A whole member is 140× a 96-byte window.** Building an index must therefore be bounded work,
and the specification fixes the budget:

### 6.1 The head walk (default)

**One window per member, `HEAD_BYTES = 96`, and never a second.** 96 is the largest header any
rule below reads. Proposal 8's other finding — that the mapper calls `member_format(index)`
(32 bytes) and then `member(index, max_output=64|96)` for the same member, paying
0.664 ms against 0.401 ms, 1.66×, ~55 s across the fleet's 209,312 MMAP+SCHl members — is
designed out rather than fixed: `identify()` takes the window once and returns the format **and**
the shape from it.

Answered from the 96-byte window alone: every `format` and `tag`; MMAP version / dimensions /
format id; SCHl platform / channels / codec / codec2 / rate; TDB version and table count; CPTH
records and header words; WIFF form and declared length; the ELF class/type/machine.

Answered from **sparse 12-byte seeks**, not a decode: the RenderWare top-level walk. Measured on
a synthetic two-section clump, the identifier's only reads are 12 bytes each, one per top-level
section, and nothing else — asserted by `test_the_identifier_never_asks_for_more_than_a_head_and_section_headers`.

Answered from the **container's own directory**, no member read at all: every offset, size,
stored size, codec, name and the ZIP/`.ZIH` CRC-32 columns.

### 6.2 The deep walk (`--deep`, opt-in, and the disc row says which you have)

Only these need a whole member, and each is named:

| Fact | Why a window will not do |
|---|---|
| `stored_sha256` | a digest is over the bytes |
| `payload_crc32` | recomputing a declared CRC is the point of recomputing it |
| TDB table/field schema | the field directory follows a per-table header at an offset the header gives; bounded in principle, whole-member in the reader that exists |
| nested `TERF` / `BIGF` recursion | the child's directory can be anywhere in the parent member |

A head-only index costs **14.3 s** on NCAA Football 09 and a deep one **20.4 s** [M]: the deep
extras are 43% on top, not a different order. The disc row carries `"walk": "head"` or
`"deep"`, so a consumer can never mistake one for the other, and the provenance gate (§3.2)
records which a document was built from.

### 6.3 Two reads a builder must not perform

- **Never decode a member to classify it when the container declares its format.** A ZIP central
  directory, a `.ZIH`, a `PAK ` object table and a TERF `DIR1`/`COMP` pair all name a member's
  extent without touching it.
- **Never map a whole file to read its head.** Files whose format is settled by their first four
  bytes and whose size makes a map pointless — `MPEG-PS`, `MPEG-video` — get a file row and
  nothing more. Blitz 2002's index takes **0.17 s** over a 1.46 GB image precisely because its
  1.10 GB of `.PSS` movies (10 files) are never mapped [M].

---

## 7. Migration, in separately-green steps

Each step lands on its own, leaves every gate green, and is useful before the next one exists.

**Step 1 — the identifier and its tests, alone.** `tools/owner/disc_identify.py` plus
`tests/owner/test_disc_identify.py`, importing the shipped magic constants and adding the tag
spelling and the RenderWare walk. Nothing consumes it. **Green when** the new test file passes
and `ea_disc_map --selftest` (109 checks) and `ea_module_readiness --selftest` are unchanged.

**Step 2 — the builder and the store.** `tools/owner/disc_index.py` with `--iso`, `--deep` and
`--selftest` over a synthetic ISO; the content-addressed store layout; `index.meta.json`. Still
nothing consumes it. **Green when** `--selftest` passes and `retail_free_violations` is empty on
a synthetic disc.

**Step 3 — the proof, and the step that makes the rest safe.**
`tools/owner/disc_index_verify.py --iso <image> --against <checked-in census>` rebuilds the
census from the index alone and diffs it against the checked-in file. It must reproduce, from
one index per disc:

- every `docs/product/measured/nflblitz{2002,2003}_ps2/containers.json`;
- every `docs/product/measured/nflblitz{2002,2003}_ps2/zip-index.json`;
- the **File kinds** and **Totals** tables of each `docs/owner/disc_maps/*.map.md`;
- each `docs/owner/scoping/readiness/*.readiness.json` block that is a count of what is on the
  disc rather than of what a reader did with it.

**This step is the gate on the whole migration.** No consumer is changed until its own census
reproduces. Where a census does not reproduce, §8 says what the index must gain — and the answer
is written into this document before any code moves.

**Step 4 — `ea_disc_map.py` becomes a renderer.** Its walk moves into the builder; `--iso` keeps
working by building an index first. **Green when** every `.map.md` in `docs/owner/disc_maps/`
regenerates byte-identically, which step 3 has already proved for its two tables, and the 40
mapper unit tests pass against the moved functions.

**Step 5 — `ea_module_readiness.py` takes its targets from the index.** Its readers do not
change. **Green when** every `readiness/*.json` regenerates with identical counts and its
`--selftest` passes. (Note: one of its 37 self-test checks has been red since it was written —
`EFFICIENCY_REVIEW.md` §11.2, `LESSONS_2026-09-06.md` #13 — and must be fixed before this step,
not by it.)

**Step 6 — the three `inventory_lane.py` files.** One per commit, each with its module's
conformance run and `pins --check`. `FORMAT_SAMPLE` is removed in the same commit that removes
the walk, and the lane's `format_totals` becomes complete rather than sampled — a count change,
so the module's count pins move with it under `tools/registry_add_rows.py` in a separate commit
(charter §5).

**Step 7 — the two identity tools' enumeration.** Smallest gain, last, and skippable.

**What does not move.** The shipped `_formats` packages; every module's `containers.py` beyond
its magic table; anything under `packaging/`.

---

## 8. What it costs, and what it saves

### 8.1 Building an index costs about one mapper run [M]

| | NFL Blitz 2002 (1.46 GB, ZIP) | NCAA Football 09 (2.18 GB, TERF+BIG) |
|---|---:|---:|
| `ea_disc_map.py`, same box | 0.2 s | 15.0 s |
| index, head-only | **0.17 s** | **14.3 s** |
| index, deep | 1.62 s | 20.4 s |
| index bytes, head / deep | 1.8 MB / 2.1 MB | 10.3 MB / 15.1 MB |
| rows | 4,892 | 37,017 |

**The index does not make the first walk cheaper; it makes every subsequent walk free.**
Regenerating the whole NCAA 09 Totals census from the index takes **1.1 s** [M] against 15.0 s to
re-walk the disc — and that 1.1 s is dominated by parsing 37,017 rows, so a consumer that greps
first pays 13 ms.

### 8.2 What that is worth against the recorded walks

Recorded costs, from the brief and `LESSONS_2026-09-06.md` [S]: an MVP disc walk **188 s**; the
Madden derivation **819–992 s**; the NCAA derivation **953 s**; a ten-disc readiness census
**1,269 s**; a five-disc map run **4.7 s**.

- **The ten-disc readiness census, 1,269 s.** Every one of those ten discs is walked to find
  targets before a reader is run. With indexes present, discovery is ~10 × 0.4 s of parsing and
  what remains is the reader time, which is the part worth spending. Even taking the whole
  1,269 s as the pessimistic baseline, the index costs ~10 × 15 s = 150 s to build once and is
  then reusable by every other consumer.
- **The derivations, 819–992 s and 953 s.** These are pixel work. The index saves their
  enumeration and nothing else — **seconds out of fifteen minutes**. Say so plainly.
- **Re-measurement, ~0.4M tokens in one day** (`LESSONS_2026-09-06.md` #11). Ten discs measured
  at 1,269 s were re-measured anyway, and one disc's preload-cache semantics were measured three
  times, because the facts lived in agents' context rather than files. An index keyed on the
  image's hash is the file. This is the largest saving in the document and the hardest to put a
  number on.
- **The 29 throwaway walkers.** Each one's preamble becomes one import.

### 8.3 The honest ledger

| | |
|---|---|
| **Cost** | ~15 s per disc to build (once, cached by image hash); ~2,000 lines of new owner code, of which 1,131 are moved not written; 28 indexes at ~10 MB each ≈ 280 MB on the NAS; one new gate |
| **Saves** | 1,977 lines across seven permanent consumers (19.7%); one identifier instead of seven; discovery time in every future census; the third `HTPC`-shaped mistake, which is already sitting unfiled in a checked-in document |
| **Saves little** | the two texture-identity tools (1.0% and 2.1%); any pass whose cost is decoding, not finding |

---

## 9. The round trip: does an index reproduce what is published?

Run over **two disc families**, and a third disc for free. Recorded in
`docs/owner/specs/measured/disc-index-roundtrip.json`.

| # | disc | family | published census | result |
|---|---|---|---|---|
| 1 | NFL Blitz 2002 | Midway stored ZIP + `.ZIH` | `docs/product/measured/nflblitz2002_ps2/containers.json` | **identical** |
| 2 | NFL Blitz 2002 | " | `docs/product/measured/nflblitz2002_ps2/zip-index.json` | **identical** |
| 3 | NFL Blitz 2003 | " | `docs/product/measured/nflblitz2003_ps2/containers.json` | **identical** |
| 4 | NFL Blitz 2003 | " | `docs/product/measured/nflblitz2003_ps2/zip-index.json` | **identical** |
| 5 | NCAA Football 09 | EA `TERF` + EA `BIG` | `docs/owner/disc_maps/SLUS-21752.NCAA-Football-09-USA.map.md`, both tables, 29 keys | **identical** |

```bash
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=. python3 -m tools.owner.prototypes.disc_index.walk \
    --iso $S/discs/blitz2002.iso --out $S/dix-out/deep --label "NFL Blitz 2002 (USA)" --deep
PYTHONPATH=. python3 -m tools.owner.prototypes.disc_index.regen \
    --index $S/dix-out/deep/SLUS-20051.index.jsonl --check blitz2002
#   REGEN blitz2002 identical=2/2 retail_free_violations=0
#     containers.json  IDENTICAL
#     zip-index.json   IDENTICAL

PYTHONPATH=. python3 -m tools.owner.prototypes.disc_index.walk \
    --iso $S/discs/ncaa09.iso --out $S/dix-out/deep --label "NCAA Football 09 (USA)" --deep
PYTHONPATH=. python3 -m tools.owner.prototypes.disc_index.regen \
    --index $S/dix-out/deep/SLUS-21752.index.jsonl --check terf-map \
    --map docs/owner/disc_maps/SLUS-21752.NCAA-Football-09-USA.map.md
#   REGEN terf-map identical=True compared=29 unanswerable=0 retail_free_violations=0
#     SLUS-21752.NCAA-Football-09-USA.map.md IDENTICAL
```

Every regenerator opens **only** the JSONL — never a disc image, never a format reader — so a
match is a statement about the index, not about a second walk that happens to agree.

### 9.1 What it took to make them reproduce, and what each one is telling you

Nothing here failed permanently, but five things had to be got right, and each is a requirement
on the real builder rather than an accident of the prototype.

1. **A histogram truncated to a top-N is not reproducible from a differently ordered walk.**
   `containers.json`'s `clump_top_level_sequences` keeps the top six by count, and below rank
   four every sequence has count 1, so ranks five and six are decided by first-seen order. The
   lane iterates members sorted by name; a walk in ZIP data-offset order produced two different
   entries with the same counts. **Requirement:** the index emits rows in walk order and carries
   `index` per member, so a consumer can re-impose any order; and a census whose tail is an
   insertion-order tie-break should sort its ties. The regenerator sorts by name to match.
2. **Two vocabularies for "I cannot name this".** §4.4. **Requirement:** ship both projection
   functions with the builder, and never let a consumer invent a third.
3. **A published count can be extension-driven, not identity-driven.** `clump_members` is 1,272
   because 1,272 members are named `*.dff`, not because 1,272 identified as RenderWare (1,043
   did). **Requirement:** every member row carries `ext` **and** `format`, and a consumer must
   say which it is counting. Where the two disagree that is a finding, not a bug.
4. **A rendering rule is part of the identity.** The map prints SCHl platform 5 as `PS2`, from a
   table `ea_disc_map` and `ea_module_readiness` each hold a copy of. **Requirement:** the name
   belongs in the identifier and the id beside it (`"platform": "PS2", "platform_id": 5`), so no
   consumer keeps a third copy.
5. **A distinctness count depends on a signature rule.** The map's "13 distinct schema shapes"
   comes from table + field name/type/width, deliberately excluding row counts and bit offsets;
   the index carries offsets and counts too, and by *its* stricter key there are 238. It also had
   to include the disc's one bare `.TDB` **file**, not only the 581 container members, to reach
   13. **Requirement:** the index stores the full schema; `tdb_signature()` ships beside it as
   the published projection.

One parser bug is worth recording because it will bite the real verifier: reading "581 (0 not the
**v8** layout); bare TDB files 1; distinct schema shapes 13" by taking integers in order yields
`8` as the bare-file count. **Parse a published page with targeted patterns, never positionally.**

### 9.2 What the index could not answer: nothing, on these three discs

`keys_the_index_cannot_answer` is empty for all 29 compared keys, and
`retail_free_violations` is empty for all three indexes [M]. The index also carries facts the
page does not: `file_kinds_measured` and `decompressed_formats_measured` (the finer vocabulary),
`big_entries_all_depths`, `big_nested`, `text_containers`, `mmap_containers`.

**The assumption that would make this wrong.** Five censuses over three discs of two families is
not the fleet. The claim proved is: *for a stored-ZIP disc and a TERF+BIG disc, the shape facts a
96-byte window plus a container directory yield are sufficient to reproduce every published
count.* Two families are untested and are the risk: **`PAK `** (Blitz Pro, Blitz: The League),
where objects are located through a trailing directory and `SEC ` containers list sections, and
**`EFS `/`.HDR`** (AND 1 Streetball), where 7,200 member sub-directories carry their own entry
tables. Both are read by `ea_disc_map` today and both should be added in migration step 2 and
proved in step 3 before step 4 removes the mapper's walk. Nothing measured here suggests they
will not fit; nothing measured here shows they do.

---

## 10. What this does not fix

- **It does not decode anything.** A `.dff`'s geometry, a `WIFF`'s chunks, an `SHPS` code-`0x0E`
  image, a `PAK ` member's pixels — all still unread. The index says where they are and what
  shape they are, which is what it is for.
- **It does not answer "can the shipped reader open this".** That is
  `ea_module_readiness.py`'s question, it requires running the readers, and it stays.
- **It does not give a texture its PCSX2 name.** That needs decoded pixels and a dump to pair
  against (§2.3, §5).
- **It does not make a first walk cheaper.** ~15 s per disc, same as a mapper run (§8.1).
- **It does not fix the fleet's shared-file problem.** That is efficiency proposal 1
  (fragments-authoritative registry), designed and not built, and a parallel specification.
- **It does not stop an agent writing a throwaway walker.** It makes not writing one easier. The
  enforcement, if any is wanted, is a review habit, not a gate.
- **It does not settle a disagreement about what a format *is*.** It makes a disagreement
  visible in one place and cheap to fix once — `RW-CLUMP?` is a recorded question, and someone
  still has to answer it.
- **It does not backfill provenance.** The checked-in `docs/owner/disc_maps/` pages were written
  by `ea_disc_map/v2` and `v3` at different times; the gate of §3.2 only binds pages regenerated
  after it lands.

---

## 11. The prototype

`tools/owner/prototypes/disc_index/` — **prototype, not shipped, deleted when this is built.**

| File | What |
|---|---|
| `identify.py` | the single identifier: forward tags, the RenderWare walk, per-family shape rules, bounded to a 96-byte window plus 12-byte section seeks |
| `walk.py` | the builder: ISO9660 → files → containers (TERF, BIGF, ZIP, `.ZIH`) → members, JSONL out, `--deep` opt-in |
| `regen.py` | regenerates published censuses **from an index alone** and diffs them; carries `retail_free_violations` and the two projections |
| `map_md.py` | parses the numbers back out of a checked-in `.map.md`, so the diff is against the repository and not against typed-in figures |

`tests/owner/test_disc_index_prototype.py` — 25 tests, synthetic bytes only, including one that
reproduces the `HTPC` misreading from first principles and one that asserts the identifier never
reads more than a head window plus 12 bytes per section.

```
PYTHONPATH=. python3 tests/owner/test_disc_index_prototype.py
Ran 25 tests in 0.007s
OK
```

Not in the prototype, and needed by the real builder: `PAK `, `EFS `/`.HDR`, `MWo3`, the Midway
sound bank, `.OBF`, `VAGp`, `QL01` preload caches, raw-CD (2352-byte sector) images, and the
`--summary`/`--compare` aggregations.
