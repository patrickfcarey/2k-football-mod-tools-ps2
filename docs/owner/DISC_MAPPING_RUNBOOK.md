# Disc mapping runbook — one disc, one command, one page

This is the procedure for turning a PlayStation 2 disc the owner holds into a **disc map**: a
retail-free page under `docs/owner/disc_maps/` that says what is on the disc, in what
containers and formats, and therefore which studio pages a game module could fill and at which
registry rung. It is written so that a low-reasoning agent, or a person in a hurry, can do it
without judgement calls. Since v5 the mapper writes the page skeleton itself (`--page`); the
agent adds the "what it is for" phrases and the open questions, and nothing else.

## Rules (read before anything else)

1. **Read-only.** The image is never modified, copied, renamed or moved. The mapper opens it
   read-only. Nothing is extracted from it except into memory.
2. **Retail-free outputs.** Only counts, names, sizes, offsets, digests and format ids leave the
   disc. Never quote game text, never save a decoded texture, never paste a hexdump of a member
   into a repository file. The mapper already obeys this; the page you write must too.
3. **No emulator.** Mapping never launches PCSX2 or PenguinScreen2 and never touches
   `wivrn-server`. If a step seems to need the game running, it is not a mapping step.
4. **The rig is where the discs live.** Run the mapper there over SSH; bring back only the
   `.map.json`, `.map.md` and `.page.md` files. On the rig, write only under `~/ps2-maps/out`.
5. **One disc, one page.** The page is the `--page` skeleton with its placeholders filled. Every
   number in it was written by the mapper; a number you computed yourself does not go in.
   Every sentence not from the map or a cited document is marked `[A]`.
6. **Rungs are TODAY's.** Write the rung the map earns now and name what lifts it. Never write
   an arrow (`read-only-mapped → extract-only`) or the rung a future decoder would earn.
7. **Do not commit.** Write the page into the scratch area named by whoever dispatched you; the
   integrator commits with the owner's identity.

## The tool

`tools/owner/ea_disc_map.py` (`ea_disc_map/v3`; stdlib + this repository only; selftested; 40 unit tests):

    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --iso "<image>" --out <dir> --label "<Title> (USA)" --hash-image
    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --page <dir>/<SERIAL>.<label-slug>.map.json         # the page skeleton
    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --render <dir>/<SERIAL>.<label-slug>.map.json       # the Markdown again
    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --compare A.map.json B.map.json [--out diff.md]     # retail vs Deluxe
    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --summary <dir> [--out SUMMARY.md]                   # one table over every map
    PYTHONPATH=. python3 tools/owner/ea_disc_map.py --selftest

It writes `<SERIAL>.<label-slug>.map.json` (everything) and `<SERIAL>.<label-slug>.map.md` (the
summary a person reads); the label is in the name because a Deluxe disc shares its serial with
the retail one. `--page` writes `<SERIAL>.<label-slug>.page.md` next to the JSON (or into
`--out`).

What the map holds: identity (boot file, serial, boot-ELF sha256 and PCSX2 CRC, whole-image
sha256); every file's kind from its magic (`TERF`, `TDB`, `ELF`, `QL01`, `BIGF`, `SHPS`,
`SCHl`, `MPCh`, `ABKC`, PS2 system files, `TEXT`, `VC-pack`, or `other:<hex>` with an
extension hint); every `TERF` container's chain, alignment, codecs, decompressed formats,
member-size statistics, MMAP dimension / version / format-id histograms, TEXT totals, SCHl
header ids, nested containers three levels down, and the EA TDB schema of every database member
(each distinct shape once); every EA BIG archive's entries, RefPack-packed members classified by
their decompressed head, nested archives, SHPS image banks, SCHl headers and TERF/TDB members;
bare databases; `QL01` preload copies; every ELF/IRX. A **Totals** table at the top of the
`.map.md` carries every number a page quotes.

Since v3 it also reads the **non-EA families** on the Midway Blitz discs and AND 1 Streetball,
which earlier versions listed as `other:<hex>`: a ZIP archive and the Midway `.ZIH` index
beside it, the `MWo3` overlay, the `PAK ` pack and its `0x11111111` resource metadata, the
Midway sound bank and `.OBF` option tree, AND 1's `EFS ` archive with its `.HDR` member
directories, and Sony `VAGp` streams. Three of those (`.ZIH`, the sound bank, the metadata
list) have no usable magic and are claimed **only when their own reader validates them**, so a
file the reader cannot stand behind stays in the unrecognised-magic table where it belongs.
Each reader states an identity it could be wrong about and checks it — the `.ZIH`'s offsets
must land on ZIP local file headers carrying the same names and its CRC-32 fields must
recompute; `64 + segment1 + segment2` must be the overlay's length; the sound bank's fifth
header word must be the file's length. A header word with no checked meaning is printed as a
numbered word, never given a plausible name. `docs/owner/scoping/BLITZ_AND1_FORMATS.md`
carries the field-by-field study and says what stays unknown.

Containers are read through a memory map (a 1.7 GB movie container costs no memory); a raw-CD
image (2352-byte sectors, e.g. Madden NFL 2001) is read sector by sector. A container whose
ISO9660 record is shorter than its own `DATA` chunk is read to its declared length. A refusal is
a sentence in the table, never a traceback. Madden 09 maps in about 45 s plus the image hash;
Madden 2004 with its 1.7 GB movie container in about a minute; a full-disc hash adds roughly
10 s per GB.

## Steps

1. Confirm the disc exists on the rig, read-only:
   `ssh pacarey@192.168.68.85 'ls -la ~/Games/ps2/ | grep -i "<title>"'`
2. Run the mapper on the rig (the clone lives at `~/2k-football-mod-tools-ps2`, kept at the lane's head):
   `ssh pacarey@192.168.68.85 'cd ~/2k-football-mod-tools-ps2 && PYTHONPATH=. python3 tools/owner/ea_disc_map.py --iso ~/Games/ps2/"<image>" --out ~/ps2-maps/out --label "<Title> (USA)" --hash-image --quiet'`
   Expected: one line `EA_DISC_MAP_DONE serial=<SERIAL> files=… containers=… refused=… archives=… databases=… schemas=… members=… unclassified=… seconds=…`.
   `refused=0` is normal for a retail disc; a Deluxe disc may show refusals that the `.map.md`
   explains in its container table. A disc with `containers=0` is not an EA TERF disc: its page is
   the archive-shaped skeleton `--page` writes for it (VC packs for ESPN titles; `BIGF` archives +
   `SHPS` image banks for MVP Baseball). Anything else: stop and report the line verbatim.
3. Write the page skeleton on the rig and fetch the three files:
   `ssh pacarey@192.168.68.85 'cd ~/2k-football-mod-tools-ps2 && PYTHONPATH=. python3 tools/owner/ea_disc_map.py --page ~/ps2-maps/out/<SERIAL>.<label-slug>.map.json'`
   `scp pacarey@192.168.68.85:~/ps2-maps/out/<SERIAL>.<label-slug>.* <your scratch dir>/`
4. Open `<SERIAL>.<label-slug>.page.md`. Fill **only**:
   - every `<what it is for> [A]` cell — one phrase from the container's name, marked `[A]`, or
     `[S]` with a citation if a document names it (the glossary the mapper applies already cites
     the owner's Madden 09 census where it can);
   - the **Open questions** — one line each, each pointing at a row of the map.
   Do not edit a number, a rung, a "what lifts it" cell or a Totals-derived sentence. If one
   looks wrong, say so in your report; do not correct it by hand.
5. Self-check before reporting: no game strings quoted; no number that is not in the `.map.md`;
   no arrow in a rung cell; every `[A]`/`[S]` present; the identity row matches the mapper's
   `EA_DISC_MAP_DONE` line.

## Retail vs Deluxe, and the fleet

- Two maps of the same title: `--compare retail.map.json deluxe.map.json --out <dir>/compare.md`
  lists added / removed / resized files, containers whose members, codecs, formats, MMAP sizes
  or TDB member counts changed, archive and schema deltas, and a totals table. That is the page's
  "what the Deluxe changes" paragraph, verbatim.
- Every map in one table: `--summary <dir> --out <dir>/SUMMARY.md` (disc, serial, files,
  containers, refused, members, archives, entries, schemas, MMAP, SCHl, TEXT, TDB members,
  nested TERF, unclassified, seconds, image sha256).

## Rung rules (mechanical; `--page` applies them)

For each studio page, the containers whose names the glossary maps to it, plus every container
holding the page's format:

| page | feeding formats | rung TODAY (the map alone), and what lifts it |
|---|---|---|
| Uniforms & Equipment, Field Art, Stadiums (textures), All Textures | `MMAP` | **read-only-mapped**; lifted by an MMAP→PNG decoder (none exists for EA titles yet) |
| Names, Numbers & Faces; Text & Team Identity (team data); Playbooks & Plays | `TDB` members, bare `.DB` files | **read-only-mapped (schema + rows)**; lifted by an offline TDB writer with the four CRCs and an independent verifier |
| Text & Team Identity, Menus & UI | `TEXT` members | **read-only-mapped**; lifted by a TEXT decoder |
| Audio | `SCHl`, `BNKl` | **read-only-mapped** (no SCHl decoder in the fork); lifted by one; never a writer (no public encoder) |
| Stadiums (geometry) | `SMF` | read-only-mapped; lifted by an SMF reader |
| Presentation | `MPCh` | read-only-mapped; lifted by a movie decoder |
| Menus & UI (fonts) | `FNTS` | read-only-mapped |
| Textures on a BIG disc (MVP) | `SHPS` | read-only-mapped; lifted by an FSH/SHPS decoder |
| Gameplay | executable | `unknown` (code-patch scaffold); translations |
| The Crib, Saves | not on the disc | honest empty page |
| Textures / Text on a ZIP disc (Blitz 2002/2003) | `ZIP` members | **read-only-mapped**; lifted by decoders for the members' own formats (RenderWare clumps and texture dictionaries, Midway `WIFF`) |
| Textures / Menus on an `EFS ` disc (AND 1) | `EFS ` members | **read-only-mapped**; lifted by decoders for `.HDR` sub-directories and the `BALL` / `NIS0` / `SCR` blobs |
| Audio on a Midway or AND 1 disc | Midway sound bank, `VAGp` | **read-only-mapped**; lifted by a PS-ADPCM / VAG decoder; never a writer |
| Gameplay tuning (Blitz Pro, The League) | `.OBF` | **read-only-mapped (schema + rows)** — the walk consumes the whole file; lifted by a writer with an independent verifier |
| Anything fed by a Midway `PAK ` | `PAK ` | **unknown** — every object is named and none can be located; lifted by whatever turns a named object into a byte range |

A `COMP` container with **LZH1** members can be read but **not rewritten** until an LZH1 encoder
exists; `--page` appends "LZH1 encoder before any rewrite" to the row and lists those containers
in the Writers section. A `DATA` container, or a `COMP` container whose packed members are
**RLE1** only (`ea_terf.rle1_compress` exists), can be rewritten with `ea_terf.rewrite_member`.
EA BIG archives are not TERF: no writer exists and `rewrite_member` does not apply. A `QL01`
preload file copies container directories and members: an edit to a container it names must be
applied there too (the owner's census §3, the three-place edit rule).

## What went wrong before, and the rule that prevents it

Five pages were written from the v4 `.map.md` by hand. Every error below is one `--page` cannot
make, because the sentence is now written from the map's Totals:

| error seen | rule |
|---|---|
| "Dimensions (top)" listed one container's sizes as the disc's | disc-wide MMAP dimensions come from Totals, never from a container row |
| DATA-only / COMP counts wrong (37/4 for 33/8; "DATA chain only" for 39/16; "stored 31, COMP 54" for 50/35) | the chain histogram in Totals |
| "MMAP across 21 containers" (27), "across 85" (35), "across 20" (33) | Totals |
| "Nested TERF: 141" (411) | Totals |
| "Distinct schema shapes: 1" (13), "2" (13) | Totals |
| "other: 20 files" folding QL01 in; "164 distinct kinds" | the kinds table, one row per kind |
| "SCHl: 31 files — all in 8 BIG archives" (31 loose `.BIG`-named files that ARE bare SCHl streams; 9,123 SCHl members inside archives) | the kinds table and the archive table are different rows; never merge them |
| "SHPS (geometry)"; "BIG archives rewritable with `ea_terf.rewrite_member`" | SHPS is an image bank; BIG is not TERF — both sentences come from the glossary and the Writers section |
| "read-only-mapped → extract-only" | rule 6 |
| "TEXT members: 8 (not in the map file)" | the TEXT total is in Totals |
| a `.CNF` file quoted as "the largest MPC sample" | the kinds table keeps kinds apart |

## What the integrator does with the page

Reviews it against the map (`--page` again on the same JSON reproduces every mechanical cell;
a diff shows exactly what the agent added), commits it as `docs/owner/disc_maps/<SERIAL>.md`
with the owner's identity, and files the module work it implies in `GAME_STUDIO_SHELL_PLAN.md`.
