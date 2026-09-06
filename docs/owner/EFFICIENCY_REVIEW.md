# Efficiency review — what the next game module should cost, and why

**Question.** Where are we spending tokens and wall time that we do not have to, and what would
make each additional game module markedly cheaper than the last?

**Method.** Everything below was measured in this worktree on 2026-09-06, single-threaded, and
the command that produced each number is given. Nothing is estimated except where it says so.

**The day being reviewed.** Fourteen agents built the Madden 09 module, its gap register, the
witness discs, the NCAA 09 scaffold, the MVP readers and two censuses. Their reported token use:

| agent | k tokens | agent | k tokens |
|---|---:|---|---:|
| gap register | 821 | art pages | 539 |
| NCAA 09 | 767 | playbooks | 531 |
| audio | 674 | MVP readers | 519 |
| art encoders / identities | 627 | readiness census | 498 |
| RC89 fixes | 603 | witness discs | 447 |
| team identity | 602 | TDB writers | 464 |
| code patches | 382 | RC88 docs | 352 |
| **fourteen agents** | **7,826** | **integration, roughly again** | **~7,800** |

So the module cost on the order of **15.6M tokens**, and about half of it was integration:
rebasing six branches through sixteen shared files, collapsing the duplicated lines their unions
produced, 40-minute local test loops, re-explaining the same rules in every brief, and agents
re-measuring facts other agents had already measured.

---

## The ranked table

| # | Proposal | Measured waste | Expected saving | Cost | Risk | State |
|---|---|---|---|---|---|---|
| 1 | Invert the registry and allowlist mirrors: fragments authoritative, canonical composed | 527-line allowlist touched by **50 commits in 3 days**, registry by 31, runtime gate by 35 — every one a conflict site for six concurrent branches | A module PR touches its own package only. Removes the largest single class of rebase work, roughly **half the integration cost** | ~2 days: `registry_merge` gains a compose direction, `stage_release` gains an include, one migration commit | Medium — it is the release manifest | **Proposed, designed below** |
| 2 | A standing charter every brief references, plus a per-disc measured-facts ledger | The same rules restated in 14 briefs; preload-cache semantics measured 3× for 1 fact; `docs/product` is **81 files, 1.23 MB ≈ 310k tokens** to sweep | ~**30–60k tokens per agent** not spent re-reading or re-measuring: **0.4–0.8M per module** | 1 file, written | Low | **Done** |
| 3 | One parameterised lane validator | Fifteen near-identical scripts; ten Madden 09 validators ran **48 s** of which **40 s was the same conformance harness ten times**, printing **10 × 56,700 bytes** | Fifteen validators **54 s → 9 s**; output **567 KB → 1.7 KB**; a new lane is a JSON entry, not a script | Half a day | Low — proved in a staged tree | **Done** |
| 4 | Derive the capability counts and check every site (§1) | 15 sites hold 4 numbers; **2 were wrong**, and `106 + 5 ≠ 112` made `validate_all` refuse | The gate is green again and cannot drift silently; `--json` is the input a generator needs | 2 literals, 1 tool, 7 tests | Low | **Done** |
| 5 | The MMAP decoder moves to `_formats` | A decoder that works on **13,053 of 13,802** sampled members across ten discs was reachable by one game | Every future EA module gets MMAP for free; NCAA 09's texture row needs a lane, not a decoder | Done in an hour | Low | **Done** |
| 6 | Generic lane bases: TDB-record, TERF-member-art, text-bank | **17 lane implementations** hand-write the same 8 methods; 20,641 lines across three packages | A declarative lane is a container map plus a schema table: **~60–70% of a new module's lane code** | 3–4 days, contract-additive | Medium | **Proposed** |
| 7 | Run only the suites a change can affect | **395 test files**; a Madden 09 change plausibly touches **29 (7%)**. The full loop is 2m53s / 5,549 tests on the shared runner | Seconds in the inner loop; the full loop stays the gate before the final commit | Half a day | Low | **Proposed** |
| 8 | Header windows instead of whole-member decodes | A whole 64 KB LZH1 member costs **140×** a 96-byte window (55.95 ms vs 0.40 ms); the mapper decodes each MMAP/SCHl member **twice** | The double decode is **1.66×**; over the fleet's 209,312 MMAP+SCHl members, ~55 s. The 140× is what turns a 7-minute pass into ~3 s | Hours | Low | **Proposed** |
| 9 | Four validators that cannot pass in a shipped tree (§3) | `validate_nfl2k5_ps2_{text,playbook,stadium_position,fixture_audit}.sh` run `python3 -m unittest`; `tests/` is not staged | A latent release-gate failure removed | Half a day | Low | **Reported, not fixed** |
| 10 | Conformance `--lane` and a shared harness result | The harness is 544 checks / 5 s for one game; 84 of them (**1 s**) are static | Marginal now; matters at ten modules | Contract change | Low | **Proposed** |

---

## 1. Shared-file churn — the mirrors point the wrong way

### Measured

Commits touching each shared file in the three days of this module (`git log --since`):

| file | commits |
|---|---:|
| `packaging/release-allowlist.txt` | **50** |
| `packaging/check_2k5_mod_studio_runtime.py` | 35 |
| `mod_editor/capabilities/registry.v1.json` | 31 |
| `docs/mod_editor/2k5_mod_studio_getting_started.md` | 31 |
| `STATUS.md` | 29 |
| `tests/mod_editor/test_phase1_packaging.py` | 24 |
| `tools/validate_all_mod_editor_capabilities.py` | 15 |
| `packaging/check_apf2k8_mod_studio_runtime.py` | 14 |
| `tests/mod_editor/test_apf_studio_installer.py` | 12 |
| `mod_editor/capabilities/validate_registry.py` | 11 |
| `APF2K8-README.md`, `docs/mod_editor/APF2K8_STATUS.md` | 10 each |

Six branches, all appending to the same files. Every pair of branches conflicts in every one of
them, and the conflicts are *append-vs-append*, which git resolves by producing both — which is
why the union then had to be read line by line for duplicated rows and duplicated allowlist
entries. `stage_release.py` treats a duplicate allowlist line as fatal, so the damage is caught,
but only after the merge.

### The count pins: can they be derived? (proposal 4)

**Partly, and the split is sharp.** Only **three of the fifteen sites ship**:
`packaging/check_2k5_mod_studio_runtime.py`, `docs/mod_editor/2k5_mod_studio_getting_started.md`
and the registry itself. The other twelve exist only in the repository.

- A literal in a **repo-only** site compares the registry against a number derived from the
  registry. Computing it at check time loses nothing: `tools/check_registry_counts.py` does
  exactly that for all fifteen and finishes in 0.1 s.
- The literal in the **shipped** runtime gate is different in kind. It compares a *staged*
  registry against an expectation written *before* staging. Derive it from the staged registry
  and the check becomes `x == x`. **That one must stay a literal** — or better, become a sha256
  pin on `registry.v1.json`, which is strictly stronger and uses machinery that gate already has
  for seven other files.
- The prose counts in four documents are not gates at all; they are sentences that must stay
  true, and should be rendered.

**So the answer is: twelve of fifteen can be derived with nothing lost, one must stay, and two
should be rendered.** That was worth proving, because the pins turned out to be the drift:

> `validate_all_mod_editor_capabilities.py` asserted 112 rows, **106** covered and **5**
> deferred. The same file asserts `covered + deferred == total`, and 106 + 5 = 111. The tool
> would refuse with `canonical capability counts changed: actual=(112, 107, 5, 77)
> expected=(112, 106, 5, 77)`.

The cause was two tools counting by different rules: `build_validation_plan` defers a row when
its `validation_command` is `None`, while `registry_add_rows.counts()` counted by
*classification*. One row (`nfl2k5ps2.gameplay.executable_patches`, classified `unknown` and
carrying a validator that runs) is covered under the first rule and deferred under the second.
Fixed, with a test, in "The count pins were themselves the drift they exist to refuse".

**Note for the integrator:** the scratch `pin_audit.py` uses the classification rule this change
retires, so it now reports one problem against a self-consistent repository.
`tools/check_registry_counts.py` replaces that section of it, and covers nine sites `pin_audit`
never looked at.

### The design that ends the churn (proposed, not done)

The mirrors already exist and are already generated — in the wrong direction.
`mod_editor/games/fragments.py` computes `registry.fragment.json` **from** the canonical registry
and `allowlist.fragment.txt` **from** `packaging/release-allowlist.txt`. **Invert it.**

1. **The fragment becomes authoritative.** `registry_merge` gains
   `compose(fragments) -> canonical`, and `registry.v1.json` becomes a generated artefact checked
   by `--check` exactly as the fragments are today. The composition rule is already written and
   tested in the other direction; `fragment_for` and `canonical_bytes` are its two halves.
2. **The allowlist gains one include line per module.** `stage_release._manifest_entries` learns
   a single directive, `@include mod_editor/games/<game>/allowlist.fragment.txt`, expanded
   in place before the existing canonicalisation and duplicate checks — so every guarantee it
   makes today (canonical relative paths, no symlinks, no duplicates, no directories, nothing
   undeclared) is unchanged, and no file ships because it happened to be in a directory.
   `tools/check_registry_counts.py` reports the size of the prize: **152 of the allowlist's 527
   lines already are the union of three module fragments**, and that share grows with every
   module while the other 375 lines are stable repository furniture.
3. **The prose counts get rendered.** `STATUS.md`, `APF2K8-README.md`,
   `docs/mod_editor/APF2K8_STATUS.md` and the getting-started page carry a marked span filled
   from `check_registry_counts.py --json`. A `--check` mode fails when a rendered span is stale.
4. **What is left is one literal**, in the shipped runtime gate, moved deliberately at release
   time — or replaced by a sha256 pin on the registry.

After this, a module PR touches `mod_editor/games/<game>/**`,
`tests/mod_editor/test_<game>_*.py`, one include line, and one runtime-gate literal. Six
concurrent branches stop conflicting.

**Cost** about two days. **Risk** medium: it is the release manifest, and it must be landed
alone, on a quiet lane, with the release gate run before and after. **Do not land it during a
module push.**

---

## 2. Briefs and the measured-facts ledger — done

Fourteen briefs restated the gates, the commit identity, the retail-free rule, the shared-file
rules and the report shape. That is the same paragraph paid for fourteen times, and fourteen
chances to word one of them differently.

- `docs/product/MODULE_AGENT_CHARTER.md` — the standing rules, once. Product docs, retail-free,
  referenced from `AGENTS.md`, `CLAUDE.md` and `ADDING_A_GAME_MODULE.md`.
- `docs/owner/AGENT_BRIEF_TEMPLATE.md` — the shape of a brief that references the charter
  instead of restating it, with the paragraph that matters most: **already measured, do not
  re-derive**, naming the JSON records rather than the rendered pages.

The ledger already exists and was not being read: `docs/owner/scoping/readiness/*.readiness.json`
(15 files), `docs/owner/disc_maps/*.map.md` (25 discs), `docs/owner/scoping/READINESS_SUMMARY.md`,
`docs/product/measured/<game>/*.json`. Ten discs took **1,269 s** of measurement to produce; the
preload-cache semantics inside them were measured three separate times anyway.

`docs/product` holds **81 files and 1,261,823 bytes** — roughly 310k tokens to read whole, which
is more than half of what an average agent spent on everything. The charter tells agents to
search it and to read exactly one module document.

**Expected saving** 30–60k tokens per agent — 0.4–0.8M per module — plus the removal of the
worst failure mode, which is two agents recording the same fact differently.

---

## 3. The ten validators — done

Fifteen validators across two modules ran the same four steps and differed in two: which sources
they compiled, and which sentence they echoed.

**Measured before:** ten Madden 09 validators, run the way a registry row runs them, took
**48 s**; each ran the full conformance harness (**~4 s**, 544 checks, **56,700 bytes**), so
**40 of the 48 seconds and 510 KB of the 567 KB were the same proof, ten times**. Two of the ten
also ran the ISO9660 self-tests, paying for that proof twice.

**Now:** `tools/validate_game_lane.py` holds the behaviour; each game declares what differs in
`mod_editor/games/<game>/validators.json`; each `validate_<game>_<lane>.sh` is a wrapper of one
line, and each `.bat` changes only its payload — the Python-discovery block, which is what was
smoke-tested on cmd.exe, is untouched byte for byte.

- Fifteen wrappers individually: **54 s → 9 s** via `--all`, which runs the harness once for the
  game and de-duplicates repeated self-tests.
- Output: **567 KB → 1,749 bytes.** A step's own output appears only on failure or `--verbose`.
- The pass token is **derived** as `<GAME_ID>_<LANE>_VALIDATION_PASS`. All twenty-six validators
  in the repository already spelled it that way, so no registry row changed and nothing was
  renamed. A test fails if a wrapper's name and its `--lane` ever disagree.
- The compile step writes its `.pyc` to a scratch directory, so a staged tree no longer gains a
  `__pycache__` from being validated.
- Executable-line count in the fifteen `.sh` files: **117 → 45**, and the 45 are identical.

**A new lane's validator is now a JSON entry and two three-line wrappers**, which is the form a
scaffold can generate.

### The defect this exposed (proposal 9)

`tools/validate_nfl2k5_ps2_{text,playbook,stadium_position,fixture_audit}.sh` run
`python3 -m unittest tests.mod_editor.…`. `tests/` is **not** in the release allowlist, so those
four pass in a checkout and fail in a shipped tree — proved by staging the tree and running
`validate_nfl2k5_ps2_text.sh` inside it (exit 1). Three have `.bat` twins with the same defect.
Fixing them means moving the assertions from the test files into the tools' own `--selftest`
paths; that is a real piece of work on a module this review did not otherwise touch, so it is
reported rather than done. The migrated validators are held to the rule by a test.

---

## 5. The MMAP decoder — done

`mmap_art.py` (1,275 lines) sat in `mod_editor/games/madden09_ps2/`, and
`mod_editor/games/_formats/__init__.py` says *a game imports a format package; it never imports
another game*. So NCAA Football 09's kit-texture row was filed `read-only-mapped` for want of an
import: its own docstring and three sentences of its registry row said so.

The wrapper is not Madden's. `READINESS_SUMMARY.md` records this decoder drawing **13,053 of
13,802** sampled MMAP members across ten EA PS2 discs — NCAA Football 09 at 95.2%, Madden 12 at
95.7%, NFL Street and the rest of the fleet in the same band. It now lives in `_formats`, with a
compatibility import left behind that a test parses and fails if it ever grows a statement that
is not an import.

Nothing was claimed that was not proved: the NCAA 09 row stays `read-only-mapped`, because the
lane still has no export path, no independent verifier and no evidence from that disc. The row
now says *that*, instead of saying the decoder is out of reach.

**Saving for the next EA module:** MMAP is the format every EA Tiburon PS2 disc uses for
textures, and it is now free. Judged against the Madden 09 art work — the art encoders/identities
agent alone spent 627k tokens — a module that inherits the decoder instead of copying it saves a
large fraction of one agent.

---

## 6. Lane boilerplate — proposed

**Measured:** seventeen lane implementations across three packages hand-write the same eight
methods — `build_catalogue`, `check_edit`, `compose_recipe`, `plan`, `build`, `verify`,
`synthetic_source`, `conformance_edits` — appearing 16 or 17 times each. The three game packages
are **20,641 lines** (Madden 09 13,332; NFL 2K5 4,328; NCAA 09 2,981).

The repetition is not the eight signatures; the contract has to have those. It is that every
TDB-backed lane re-writes the same walk (open container → find member → decode → parse TDB →
locate table → read field → compose an edit → re-encode → re-pack → recompute four CRCs →
verify every byte outside the declared ranges), and every TERF-member-art lane re-writes the
same one for textures.

**Proposal.** Three generic lane bases in `_formats`, each instantiated by data:

- **`TdbRecordLane`** — takes a container map (which file, which member) and a schema table
  (table, field, width, meaning, editable). Gives catalogue, `check_edit` from the field widths,
  recipe, build with CRC recomputation, and a verifier that re-derives the edit from the built
  image. NCAA 09's `database_lane`, Madden 09's `team_data` and `identity_lane`, and the
  playbooks lane's database half are all this shape.
- **`TerfMemberArtLane`** — takes a container map and an image codec from `_formats`
  (now including `mmap_art`). Gives catalogue, PNG decode/encode, `replacement_identity`, the
  fixed-allocation build and the byte-range verifier.
- **`TextBankLane`** — takes a container map and an encoding. Madden 09 and NCAA 09 both have
  one; they share no code.

A new EA title's lanes then become a container map plus a schema table — data a disc map and a
schema census already produce — and the module's Python is the parts that are genuinely
particular. Estimated **60–70% of a new module's lane code**, and more of its *proof*: the bases
carry the verifier and the refusal sentences, so a new lane inherits its tests.

**Cost** 3–4 days and a minor contract bump (additive: new base classes, no signature moves).
**Risk** medium — the abstraction has three examples per shape today, which is enough to
generalise from and not enough to be sure. Build it against NCAA 09 first, where the lanes are
smallest, and only then re-express Madden 09's.

---

## 7. The test loop — proposed

**Measured:** 395 test files in `tests/mod_editor/`. The loop moved from ~40 minutes locally to
~3 minutes on the NAS with 28 workers, which is the single biggest wall-time win already banked
and should be the default for every agent, not a coordinator trick.

What is still spent: a Madden 09 change plausibly affects **29 files** — the module's own, the
contract suites, and the `_formats` suites — which is **7%** of the suite. Every agent ran all
395 anyway, because there is no way to ask for less.

**Proposal.** `tools/affected_tests.py <path>…` maps changed files to test files by two rules
that need no new metadata: a test file whose name contains the game id or module stem, and a
test file that imports the changed module (an AST import scan of `tests/mod_editor/`, cached).
It prints the file list; the runner takes it. The full loop stays mandatory before the final
commit, on the NAS. **Cost** half a day. **Risk** low, because the full loop is still the gate —
the selective run only shortens the inner loop.

Also worth banking: `ci_tests_nas.sh` and `pin_audit.py` live in a scratch directory and are the
coordinator's alone. The parts that are general — the parallel runner, the exec-bit-in-the-index
check, the allowlist duplicate check — belong in `tools/owner/` where every agent can run them
before pushing, rather than being discovered at integration.

---

## 8. Decode windows — proposed

`ea_terf` already takes `max_output`, and the classify pass already uses `IDENTIFY_HEAD` = 32
bytes. Two things are still paid for that need not be.

**Measured** on a 65,576-byte member packed to 22,983 bytes by the repository's own
`lzh1_compress`:

| decode | time |
|---|---:|
| to 32 bytes (classify) | 0.324 ms |
| to 64 bytes (MMAP header) | 0.340 ms |
| to 96 bytes (SCHl header) | 0.401 ms |
| **whole member** | **55.954 ms** |

The window costs almost nothing beyond building the Huffman table; **a whole member is 140× a
96-byte window.** That ratio is what turns a pass that full-decodes ~8,000 members — about
7 minutes — into about 3 seconds.

1. **The mapper decodes each MMAP and SCHl member twice.** `map_terf` calls
   `container.member_format(index)` (which decodes 32 bytes), then immediately
   `container.member(index, max_output=0x40)` for an MMAP header or `96` for an SCHl header —
   a second decode from bit zero. Measured cost **0.664 ms against 0.401 ms for a single
   96-byte window, 1.66×**. One 96-byte read answers all three questions. Over the fleet's
   94,882 MMAP + 114,430 SCHl members that is ~55 s of pure duplication.
2. **Give the readiness tool a `--head-only` mode.** Its TDB and MMAP passes must decode whole
   members and legitimately do; its sampling constants (`DEFAULT_MMAP_SAMPLE = 48`) exist
   because of exactly the 140× above. A head-only mode would answer "does this disc's shape
   match" — the question a scoping pass actually asks — over *every* member instead of a sample,
   and faster than the sampled whole-member pass it replaces.

**Cost** hours. **Risk** low; the API and its self-tests exist.

---

## 10. Conformance — proposed

The harness is not a problem yet: **544 checks in 5 s** for Madden 09, of which the static half
is **84 checks in 1 s**. It becomes one at ten modules, and two changes are worth making before
then, both requiring the contract procedure:

- **`conformance --game X --lane <id>`**, so a lane validator proves its own lane rather than
  all 544 checks. Today `--all` makes the loop cheap; `--lane` would make a single validator
  cheap too.
- **A machine-readable summary** (`--format json`), so a gate reads a verdict instead of parsing
  56 KB of PASS lines.

---

## 11. Two red gates found on the way, reported here

Neither was introduced by this review; both were found by running gates that were not being run.

1. **`validate_all_mod_editor_capabilities.py` refused.** Fixed — see §1. The arithmetic
   (`106 + 5 != 112`) had been wrong since the row that carries it gained a validator.
2. **`tools/owner/ea_module_readiness.py --selftest` fails one of its 37 checks**, and
   `tests/owner/test_ea_module_readiness.py` fails one of its 24 with it:
   `every synthetic cache copy is byte-identical (got 3/4)` — the synthetic disc now yields three
   preload-cache copies where the check expects four. Verified present at this branch's head with
   the tool unmodified, so it predates this review and is not a consequence of the decoder move.
   It is owner tooling and touches no shipped file, so it is reported rather than fixed here; the
   fix is either the synthetic disc's cache builder or the constant, and only whoever changed the
   builder knows which.

### And one this review caused, which is the argument for proposal 7 from the other side

Moving the behaviour out of the twenty-five `.bat` files took the `echo` with it, and with it the
only place their pass token appeared. `test_madden09_ps2_art_pages.py` reads the validator file
and looks for `MADDEN09_PS2_ART_PAGES_VALIDATION_PASS` in it, so it failed. The gate run after
that change covered conformance for three games, fragments, pins, the registry, the release
stage, the release check, the runtime closure, all fifteen validators in a staged tree, and four
test files — and not the module's own eleven. **The full loop on the shared runner found it in
2m53s.**

That is the honest shape of proposal 7: a selective run is for the inner loop and must never be
the last word. `tools/affected_tests.py` would have caught this one, because
`test_madden09_ps2_art_pages.py` names the game whose files changed — which is the point. But
the full loop stays the gate before the final commit, and at 2m53s for 395 files and 5,549 tests
there is no excuse for skipping it.

The general point is proposal 7's: a gate nobody runs is not a gate. Both of these sat green in
everyone's mental model and red on disk, because the loop that would have run them was 40 minutes
long and the scratch audit that stood in for it used a different rule.

## What the next module costs, before and after

A rough model, calibrated on the fourteen agents above. "After" counts only what is **done**;
proposals 1, 6 and 7 are excluded.

| | before | after (banked) | after (+ proposals 1, 6, 7) |
|---|---:|---:|---:|
| lane agents (7 × ~550k) | 3.9M | 3.6M — MMAP inherited, charter read instead of swept | ~1.5M — declarative lanes |
| census / scoping agents | 1.8M | 1.3M — the ledger is read, not re-measured | 1.0M |
| docs / register agents | 1.7M | 1.4M | 1.2M |
| fixes and re-work | 0.6M | 0.5M | 0.4M |
| **integration** | **~7.8M** | **~6.5M** | **~2.5M** — one conflict site, not sixteen |
| **total** | **~15.6M** | **~13.3M (-15%)** | **~6.6M (-58%)** |
| validator wall time per gate run | 48 s | **6 s** | 6 s |
| gate output an agent reads back | 567 KB | **1.7 KB** | 1.7 KB |
| shared files a module PR touches | 16 | 16 | **2** |

The banked 15% is real and cost a day. **The other 43% is proposal 1**, and it is one focused
change to two files — `mod_editor/games/registry_merge.py` and `packaging/stage_release.py` —
landed on a quiet lane, alone.

---

## Files this review changed

**Product lane** (cherry-pickable, four commits):

| commit | files |
|---|---|
| The MMAP decoder is a shared format | `mod_editor/games/_formats/mmap_art.py` (moved), `mod_editor/games/madden09_ps2/{mmap_art.py,containers.py,uniform_art.py,game.json,allowlist.fragment.txt,pins.json}`, `mod_editor/games/ncaa09_ps2/{texture_lane.py,registry.fragment.json}`, `mod_editor/capabilities/registry.v1.json`, `packaging/release-allowlist.txt`, `docs/product/{MADDEN09_PS2_ART_PAGES,MADDEN09_PS2_MODULE}.md`, `tests/mod_editor/test_formats_mmap_art.py` |
| One lane validator, parameterised | `tools/validate_game_lane.py`, 30 × `tools/validate_{madden09,ncaa09}_ps2_*.{sh,bat}`, `mod_editor/games/{madden09_ps2,ncaa09_ps2}/validators.json`, both modules' `allowlist.fragment.txt` and `pins.json`, `packaging/release-allowlist.txt`, `tests/mod_editor/test_validate_game_lane.py` |
| The standing rules go in one file | `docs/product/MODULE_AGENT_CHARTER.md`, `docs/product/ADDING_A_GAME_MODULE.md`, `AGENTS.md`, `CLAUDE.md` |
| The count pins were themselves the drift | `tools/check_registry_counts.py`, `tools/validate_all_mod_editor_capabilities.py`, `tools/registry_add_rows.py`, `tests/mod_editor/test_registry_counts.py` |

**Owner lane:** `docs/owner/EFFICIENCY_REVIEW.md`, `docs/owner/AGENT_BRIEF_TEMPLATE.md`,
`tools/owner/ea_module_readiness.py` (the decoder's path).
