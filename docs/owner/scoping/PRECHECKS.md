# Pre-checks before any new PS2 game module is started

> Scoping artefact, 2026-09-05. Companion to `MULTI_GAME_SCOPING.md`.
> Every command below is **read-only** unless the step is explicitly labelled
> `[WRITES]`. Evidence tags: **[M]** measured in this survey, **[S]** sourced (URL in the
> study), **[A]** assumed / not yet checked.
>
> Two hard rules this checklist obeys and every follow-on task must obey:
>
> 1. **Never write a multi-GiB image on the dev box.** `/mnt/c` measured at **50 GiB free of
>    953 GiB (95% used)** [M]. The C: drive filling to 32 MB free crashed WSL three times on
>    2026-09-05; the Disc Studio's own free-space rule was tightened because of it.
>    All image work runs **on the rig**, detached (`setsid nohup … &`), intermediates deleted.
> 2. **H-2 before any GPU/emulator action on the rig.** One VR headset is shared by three
>    emulators. Run the live-session check *as its own command* and read the result before
>    anything that touches the GPU. Never chain a launch behind it.

---

## 0. Standing safety check (run first, every session that will touch the rig)

| # | Command | Expected |
|---|---|---|
| 0.1 | `ssh pacarey@192.168.68.85 'pgrep -x pcsx2-qt; pgrep -x mupen64plus; pgrep -f "[q]emu-system-i386"'` | **No output.** Any PID = someone may be in the headset → stop and ask the owner. The `-f` pattern must stay bracketed. Measured empty at survey time [M]. |
| 0.2 | `ssh pacarey@192.168.68.85 'uname -n; df -h /home'` | `pacarey-IdeaPad-Gaming-3-15ARH7`; **1.4 TiB free of 1.8 TiB (23% used)** [M] |
| 0.3 | `df -h /mnt/c` (dev box) | 50 GiB free / 953 GiB. If below ~20 GiB, do §E before anything else [M] |

---

## A. ISOs to acquire and stage on the rig

### A.1 What is already present — nothing to acquire

Measured 2026-09-05 by opening each image read-only and reading `SYSTEM.CNF`'s `BOOT2` line
(`scoping/probe_serial.py`, at most a few 2048-byte sectors per image). Full listing in
`scoping/iso_inventory.json`.

| Title | Serial [M] | Dev box `/mnt/c/Roms/PS2` | Rig `~/Games/ps2` | Size |
|---|---|---|---|---|
| ESPN NFL 2K5 (USA) | `SLUS-20919` | ✅ + `.7z` | ✅ (+ `NFL 2K27.iso`, + demo image in `~/2k5-ps2-final`) | 4.34 GiB |
| Madden NFL 08 (USA) | `SLUS-21638` | ✅ | ✅ | 1.77 GiB |
| Madden NFL 09 (USA) | `SLUS-21770` | ✅ | ✅ | 1.54 GiB |
| Madden NFL 09 **Deluxe** | `SLUS-21770` | ✅ | ❌ **rig copy missing** | 1.72 GiB |
| Madden NFL 12 (USA) | `SLUS-21946` | ✅ | ✅ | 1.48 GiB |
| Madden NFL 12 **Deluxe 2026** | `SLUS-21946` | ✅ | ✅ | 1.52 GiB |
| Madden NFL 06 (USA) | `SLUS-21213` | ✅ | ✅ | 3.16 GiB |
| Madden NFL 2004 (USA) | `SLUS-20752` | ✅ | ✅ (+2 patched variants) | 2.99 GiB |
| NCAA Football 09 (USA) | `SLUS-21752` | ✅ | ❌ **rig copy missing** | 2.03 GiB |
| NCAA Football 2004 (USA) | `SLUS-20719` | ✅ + `.zip` | ❌ **rig copy missing** | 2.46 GiB |
| Madden NFL 2001 (USA) | not read (CD `.bin/.cue`, 2352-byte sectors) | ✅ | ✅ | 0.59 GiB |

### A.2 What is **missing everywhere** — the acquisition list

Searched: dev box `/mnt/c/Roms` (67 files, 43.0 GiB total), rig `~/Games ~/roms ~/2k5-ps2-final
~/Downloads ~/spec2` (309 files), NAS `/mnt/Z_Share/roms` (contains only `_loadout_scratch`,
no images). **None of the following is present on any of the three machines** [M].

*Priority here means "unblocks a measurement soonest", not "build this first".* NBA 2K5 ranks
first because a single read-only command against its disc changes the size of the basketball
estimate by a factor of several — the module itself is still sequenced late (study §10).

| # | Title needed | Serial (NTSC-U) | Redump | Why | Priority |
|---|---|---|---|---|---|
| A.2.1 | **ESPN NBA 2K5** | **`SLUS-20920`** [M] | `disc/8378`, v1.02, CRC-32 `e84f812b`, "2+ dumps" [S] | The whole NBA 2K5 question is "does its root carry `/VC_20920`, the way NFL 2K5's carries `/VC_20919`?" — unanswerable without the disc. Owner-added target. | **first** |
| A.2.2 | **NCAA Football 06** | **`SLUS-21214`** [M], PCSX2 compat 5 | not confirmed [A] | **The** year the NCAA community mods (NCAA Next covers 06 and nothing else) [S]; we own only 2004 and 09. | second |
| A.2.3 | **MVP Baseball 2005** | **`SLUS-21135`** [M] | `disc/11469` [S, search-index only] | Only if the owner overrules the study's deferral. `mvpmods.com` went **permanently offline ~April 2026**; the surviving hub is a PC conversion scene [S]. One PS2-native tool exists: `github.com/CollinErickson/MVP2005` (memcard rosters, active Apr 2026) [S] — read it before spending anything. | **do not schedule** |
| A.2.4 | ESPN College Hoops 2K5 | **`SLUS-20922`** [M] | `disc/8377`, v1.02, CRC-32 `bf547c9e` [S] | Only if A.2.1 shows container reuse — **and note PCSX2 rates it `compat: 2` — "Menu", broken in-game** [M] | last |
| A.2.5 | MVP 06 NCAA Baseball | **`SLUS-21367`** [M] | Redump ID **8389** [S] — *not* `disc/10276`, which is MVP **07** | Only if MVP 2005 pans out. No community found. | last |
| — | ESPN NHL 2K5 | `SLUS-20921` [M] | `disc/8381`, v1.03, "2+ dumps" [S] | **Do not acquire.** Scene is dormant (one alpha effort, Nov 2023, nothing since) [S] | — |
| — | NCAA Football 07 / 08 | `SLUS-21459` / `SLUS-21620` [M] | — | **Do not acquire.** Community attention is on 06 and 11; a live thread literally *asks* for NCAA 07 PS2 rosters [S] | — |

**Staging rule.** The owner already sources his own images; nothing here downloads anything.
Target path on the rig is **`/home/pacarey/Games/ps2/`** — it is what PCSX2 scans
(`RecursivePaths = /home/pacarey/Games/ps2` in `~/.config/PCSX2/inis/PCSX2.ini` [M]), so a
staged image appears in the game list with no config edit.

**Disk needed on the rig, per title, before any *build* work** (not just inventory):

```
free_bytes >= image_size * 2 + 1.25 GiB
```

That is the Disc Studio's own tightened rule (`PS2_DISC_STUDIO_PLAN.md` §15 — always the new
image **plus one intermediate** plus the ~1 GiB staged pack, whatever the step count) [M].

| image | worst case | rig headroom (1.4 TiB) |
|---|---|---|
| 4.7 GiB DVD (NBA 2K5 upper bound) | **10.7 GiB** | fine |
| 4.34 GiB (NFL 2K5, measured) | 9.9 GiB | fine |
| 2.03 GiB (NCAA 09) | 5.3 GiB | fine |
| all five missing titles staged + one build each | ≈ 25 GiB staged + 11 GiB peak | fine |

Read-only inventory (`nfl2k5_ps2_disc_inventory.py`-shaped work) needs **no extra space at
all** — it opens the image read-only and emits names/offsets/digests.

| # | Command (after staging) | Expected |
|---|---|---|
| A.3 | `ssh pacarey@192.168.68.85 "ls -l '/home/pacarey/Games/ps2/<new>.iso'"` | file present, size plausible |
| A.4 | `ssh pacarey@192.168.68.85 "python3 - '/home/pacarey/Games/ps2/<new>.iso'" < scoping/probe_serial.py` | prints `serial`, `root_entries`. **For a VC title the decisive line is whether the root holds a `VC_<serial-digits>` directory** — NFL 2K5's root is exactly `SLUS_209.19, SYSTEM.CNF, VC_20919` [M]. So for NBA 2K5 the literal question is: **does `SLUS-20920`'s root contain `VC_20920`?** Yes → the container is shared and `_formats/vc_ps2` is worth extracting. No → basketball is a new engine and every estimate in the study's §6.1 is wrong. |
| A.4b | For an EA title: `python3 scoping/lsdir.py <iso> DATA` then `python3 scoping/scan_tdb.py <iso> DATA TEMPLATE.DAT STRMDATA.DB` | expect `TERF` outer magic and a bare `DB`-magic TDB inside, as measured for Madden 08 / 12 and NCAA 09 [M] |
| A.5 | `ssh pacarey@192.168.68.85 'df -h /home'` | ≥ `image*2 + 1.25 GiB` free before any build |

---

## B. Hashes to pin

The contract requires **two** digests per game identity: `executable_sha256` (the boot ELF
extracted from the image) and `content_sha256` (the whole image). Both go in
`GameIdentity`, in `registry.fragment.json`'s `games[].retail_identity`, and in `pins.json`
(the NFL 2K5 module carries exactly this shape [M]).

| # | Step | Command | Expected |
|---|---|---|---|
| B.1 | Whole-image sha256, **on the rig** (never over the SMB/`/mnt/c` mount — slow and it is the drive that crashes) | `ssh pacarey@192.168.68.85 "sha256sum '/home/pacarey/Games/ps2/<title>.iso'"` | 64 hex chars; record in the study and the fragment |
| B.2 | Boot-ELF sha256 | extract `SLUS_xxx.xx` from the image read-only and hash it. The shipped route is `mod_editor/games/_formats/ps2_elf.read_boot_elf()` over `tools/ps2_iso9660.py` [M] | 64 hex chars |
| B.3 | PCSX2 game CRC of the boot ELF (needed only for a code-patch/pnach lane) | `ps2_elf.pcsx2_crc()` — XOR of every 32-bit LE word of the ELF (`pcsx2/Elfheader.cpp`) [M] | 8 hex chars; NFL 2K5's is `42F9D5AF` [M, from the lane docs] |
| B.3b | Serial ↔ title cross-check without a browser | fetch PCSX2's upstream `GameIndex.yaml` from GitHub raw and `grep` it locally (a copy is at `scoping/gameindex.yaml`, 2.6 MB) | the one source that answered reliably this session — redump.org, wiki.pcsx2.net, GameFAQs, XeNTaX and GameHacking.org all refused automated fetches [S]. It also carries each title's `compat:` rating and its per-game GS fixes. |
| B.3c | Cross-check the sibling repo's **save-directory** names against real serials | `grep -A2 '^SLUS-NNNNN:' scoping/gameindex.yaml` | `BASLUS-21620LClass07` → `SLUS-21620` = **NCAA Football 08** ✓; `BASLUS-21932LClass10` → `SLUS-21932` = **NCAA Football 11** ✓; **but `BASLUS-21769LClass08` → `SLUS-21769` = Yakuza 2** ✗, while NCAA Football 09 is `SLUS-21752` [M]. The sibling repo's own Tier-11 note already says the BASLUS suffix convention is unverified — verify it before the M09 draft-class row claims anything. |
| B.4 | Compare against **redump.org**'s PS2 datfile entry for that serial | look up the redump title string + SHA-1/MD5 for the serial; record match / mismatch / not-in-datfile | A "verified dump" match makes the identity trustworthy; a mismatch means the image is a rebuild and must be labelled so. **Note the precedent:** the Madden 09/12 *Deluxe* images share the stock serials (`SLUS-21770` / `SLUS-21946`) and are community rebuilds — they will *never* match redump, and the module must accept them by a second, separately-recorded digest, exactly as the PS2 lane already does for the Deluxe-sourced Madden templates [M]. |
| B.4b | **Record for the project:** an earlier project note gives ESPN NFL 2K5 as `SLUS-20916`. That serial is **Dance Dance Revolution EXTREME** per PCSX2's own `GameIndex.yaml` [M, grepped]. NFL 2K5 is **`SLUS-20919`** [M, read from our own disc; redump `disc/8379` v1.01 CRC-32 `d16bec78` [S]] | fix wherever `SLUS-20916` appears |
| B.5 | Hashes already computed in this survey | `Madden NFL 2001 (USA).bin` = `8c1e967db605f1fb9ce03f5289ecc862cd4fe30fa067ede1d8327da027ed84d0`; its `.cue` = `8d2a230ce630e1265c7affd5372fc9c4d3d6e4ad93a691bf98c653eb941d1efb` [M] | every other in-scope image is ≥ 1 GiB and was deliberately **not hashed** (recorded as `not hashed (size …)` in `iso_inventory.json`) |

**Do not** put a retail byte, texture, string or sample anywhere near the repository. Hashes,
offsets, lengths, FourCCs, names and counts only — the release gate enforces this
bidirectionally and `reports/**` is a FORBIDDEN_COMPONENT [M].

---

## C. Emulator boot + GS-dump capture, per game — **HUMAN REQUIRED, DO NOT RUN**

These are listed so they can be scheduled, not executed by an agent. Every one of them starts
a GPU process on the rig and therefore needs the §0.1 H-2 read first, taken by a human who
knows nobody is in the headset.

**Why a GS dump per game is unavoidable.** The PCSX2 replacement identity is
`<TEX0Hash>-<CLUTHash>-<bits>.png`, XXH3-64 over the block image and CLUT. Our
`tools/nfl2k5_ps2_texture_map.py` proves those names can be **computed offline from the disc**,
but only once you know which resources the game actually draws — and the frame-content witness
that a pack engaged can only come from a real dump replay [M].

**Current dump inventory on the rig** (measured, names only):

| serial | dumps | which game |
|---|---|---|
| `SLUS-20919` | **122** | ESPN NFL 2K5 — the only sports title with dumps |
| SCUS-97124 / 97198 / 97328 / 97436, SLES-52323, SLUS-20062 / 20090 / 20268 / 20318 / 20786 / 20851 / 20932 | 8–45 each | unrelated titles |
| **Madden / NCAA / NBA / MVP** | **0** | ← every new module starts from zero here |

PCSX2 texture-replacement trees present: `SCUS-97124` (129,090 entries), `SCUS-97198`,
`SLUS-20062`, `SLUS-20090`, `SLUS-20786`, `SLUS-20919` (92), `SLUS-20932`. PenguinScreen2 has
one, `SLUS-20919`, and it is a **symlink** into `~/2k5-ps2-final/replacement-pack/...` — any
harness must stage a private dir and swap the link under an EXIT trap, then restore [M].

| # | Human step, per candidate game | Notes / traps already known |
|---|---|---|
| C.1 | H-2 read (§0.1), by a human, as its own command | never chain a launch behind it |
| C.2 | Boot the staged ISO in PCSX2 **cold** (no save state) and confirm it reaches the title | cold boots are frame-deterministic; **save-state boots are not** — state-based frame diffs are meaningless [M] |
| C.3 | Capture ≥1 GS dump at a screen that shows the surface being scoped (menu for text/UI, gameplay for uniforms/field) | dumps land in `~/.config/PCSX2/snaps/` or `~/.config/PenguinScreen2/snaps/` as `<Title>_<SERIAL>_<stamp>.gs.zst`. **Filenames contain spaces** — never `for f in $(ls …)`; use `find -print0` [M] |
| C.4 | For a replacement-pack witness, confirm the per-game ini does not force replacements off | NFL 2K5's `SLUS-20919_42F9D5AF.ini` sets `LoadTextureReplacements=false` and **overrides `-ini`**; the harness neutralises it with sed + an EXIT trap. Assume every new serial may have the same trap [M] |
| C.5 | For PenguinScreen2, decide `ClassicTextureNames` per serial | `s_classic_default_serials` already contains **M09 / NCAA09 / M12** but *not* SLUS-20919 — so the Madden/NCAA family may need **no** flag while a new VC title will [M, from the lane's own notes]. Verify per serial, never assume. |
| C.6 | Save a **Week-1 fresh franchise** and a roster save to a memory card, per Madden/NCAA year in scope | the franchise template must be pre-Week-2 (`SEAI` flags `SEYR=0 SEWN=0 SEWT=200 SEST=10`); a later export silently degrades the cap economy [S: sibling repo `CLAUDE.md`] |
| C.7 | Record which memory card each save came from | rig cards measured: `~/.config/PCSX2/memcards/{Madden09 2011,2015,2019,2023}.ps2, Mcd001, Mcd002, NFL 2K27, NFL 2K27 TEST`; PenguinScreen2: `Mcd001, Mcd002, NFL 2K27` [M] |
| C.8 | The final "row moves to `runtime-proved`" witness | the validator binds `runtime-proved` to `(operation=write, gui.mode=edit)` **and** `runtime.status == "visible-proved"` with evidence paths. An **exporter can never be `runtime-proved`** — `extract-only` is bound to `(export, export)`. Know which rung a lane is aiming at before the human is booked [M] |

**Estimated human time:** ~30–45 min per game for C.1–C.5 (boot, reach two screens, dump);
~45 min per Madden/NCAA year for C.6 (start franchise, do not advance, export save).

---

## D. Tooling gaps and how they would be closed

| # | Gap | Where it lives now | What must happen before a module can use it |
|---|---|---|---|
| D.1 | **EA TDB reader/writer** — the single highest-value asset for Madden/NCAA | `/mnt/c/GitHub/NCAA-Draft-Class-Editor`: Python `tools/parse_madden_tdb.py` (248 lines) + `tools/write_madden_tdb.py` (225) — byte-exact roundtrip; C# `NcaaDraftEditor.Compiler/MaddenTdb.cs` (629 lines) with LE/BE endian flag and 4-CRC recompute [M] | Becomes `mod_editor/games/_formats/ea_tdb/`. **Python is the only viable form** — the fork is a stdlib-only Python/PyQt5 tool with a three-OS CI matrix and no .NET anywhere; the C# would have to be re-expressed, not vendored. The Python pair is the port base; the C# is the reference for the endian flag, the franchise 4-byte preamble and the four CRC-32/MPEG-2 fields. Budget ~3 agent-days incl. a synthetic-TDB builder and tests. |
| D.2 | **Licence** — blocker, not a nicety | The fork is **MIT** (`LICENSE`: "Copyright (c) 2026 Noah and the 2K Football Mod Tools contributors") [M]. The sibling repo `NCAA-Draft-Class-Editor` has **no LICENSE file at all** [M] | The owner must add an explicit licence to the sibling repo (or a written grant) before one line moves. He owns both, so this is a formality — but a PR that vendors unlicensed code is not mergeable. **Do this first; it is free and it unblocks D.1.** |
| D.3 | **PS2 memory-card containers** (`.psu`, `.max`, the 8 MB `.ps2` card, ECC) | Two implementations exist. The sibling repo's `tools/pack_baslus.py` **shells out to `mymcplus`** (`run(["mymcplus", card, "format"])` etc.) [M]. The fork already has **MIT** PSU + card read/write with ECC inside `tools/nfl2k5_ps2_save.py` (41 KB) [M] | `mymcplus` is **GPL — do not vendor**. The route is the fork's own MIT code, generalised out of `nfl2k5_ps2_save.py` into `_formats/ps2_memcard` with the save-directory name as a parameter (`BASLUS-21638DRost5` instead of `BASLUS-209192K5Roster`). ~2 agent-days. |
| D.4 | **NCAA draft-class binary** (`46 00 40 06` + 1600 × 86 = 138,240 bytes) | C# `DraftClassFile.cs` / `FieldMap.cs` / `PlayerRecord.cs` in the sibling repo [M] | Small and self-contained; re-express in Python inside the game module (not `_formats/` — only one game uses it). ~1 day. Synthetic source is generated data, no retail byte. |
| D.5 | **TERF / DIR1 on-disc container** (EA PS2 `/DATA/*.DAT`) | Nothing anywhere. A closed-source tool ("DFR" by JDHalfrack) is referenced by the community but there is no public spec [S] | **Measured this survey and much less scary than the plan assumed** — see the study §3. Header is `TERF` + `40 00 00 00` (0x40 header) + `02 02 00 05` + two u16s; at 0x40 a `DIR1` index; payloads follow. Decoding the DIR1 index is a bounded reverse-engineering task, ~3–5 days, and **only needed for on-disc lanes** — every save-based lane skips it entirely. |
| D.6 | **VC PS2 container** (`/VC_<serial>`, 0x20 chunk headers, `TXTR/TSET/AUDO/AUSB`, VC-LZ) | Fully implemented but spelled `nfl2k5_ps2_*` — the constants live inside six tool trios [M] | For a second VC title: extract `_formats/vc_ps2` from the restated constants, have the NFL adapter compose it (its 502 tests must stay green), then the new game composes it too. **Only worth doing after A.2.1 measures actual reuse.** ~5 days extraction + 2 days the new identity/inventory lane. |
| D.7 | **EA BIG / VIV / FSH** (MVP) | Nothing in-repo; open specs and open readers exist outside (`big4f`, `libbig`, EA Graphics Manager) [S] | New `_formats/ea_big` + `ea_fsh`. Read is known, **write is partial** (FSH GST compression is export/preview only in the public tools). Do not promise a texture writer for MVP. |
| D.8 | **EA SCxl audio** (`SCHl/SCCl/SCDl`, VAG/EA-XA) | Nothing in-repo. `tools/spu_adpcm.py` is a real PS2 SPU-ADPCM codec but it is the **raw sample codec**, not the EA bank format [M] | Decode is known (vgmstream); **no public SCHl writer or bank rebuilder exists**. Treat EA audio as `unknown` classification until proven. |
| D.9 | **Game-agnostic primitives — already reusable, no work** | `tools/ps2_iso9660.py` / `_writer.py` / `_verify.py`, `tools/xxh3.py`, `tools/spu_adpcm.py`, `mod_editor/games/_formats/ps2_disc`, `_formats/ps2_elf` [M] | Nothing. `ps2_disc.Ps2DiscIdentifier(identity)` is already *parameterised by the game's identity* and its own docstring names "an ESPN NBA 2K5 module" as the intended second caller. |
| D.9b | **Prior art nobody has read yet** | `github.com/antdroidx/NCAA-Football-PS2-Modding-Resources` ("lessons learned for modding NCAA Football"), `NCAA-DB-Editor`, `NCAA-Football-PS2-Coach-Editor`, `NCAA-Football-PS3-to-PS2-Roster-Porting-Tool` [S] | **Read these before starting any EA lane.** They are by the sibling repo's own upstream author, they are free, and the Coach Editor directly overlaps the sibling repo's open coaches workstream. Zero cost, potentially days saved. |
| D.10 | **Scaffold** | `python -m mod_editor.games new <id> --title T --platform P --serial S` [M] | Nothing — it writes the whole directory and a passing conformance test on day one. Verify with `python -m mod_editor.games conformance --game <id>` before writing any real lane. |
| D.11 | **Upstream hooks** | `MULTI_GAME_INTERFACES_PLAN.md` §5.4: registry/allowlist/runtime-gate/count-pin derivation is designed but **not landed**; `studio_qt.py` + `__main__.py` hooks **are** landed | Until §5.4 lands, every new game PR must run `tools/registry_add_rows.py --new-game …`, which moves **13 count pins in 9 files** [M]. Budget 0.5 day of pin-chasing per game, or land the hooks PR (1 day) once and pay zero thereafter. |

| # | Read-only verification command | Expected |
|---|---|---|
| D.12 | `python3 -m mod_editor.games` (in a **copy** of the tree, never the worktree in use) | lists `nfl2k5_ps2` as `Ready` |
| D.13 | `python3 -m mod_editor.games conformance --game nfl2k5_ps2` | every check named, all PASS — this is the bar a new module must clear |
| D.14 | `python3 -m mod_editor.games pins --check` | unchanged (game files are not frozen; core contract files are) |

---

## E. Dev-box disk cleanup — do this before anything else

Measured: **`/mnt/c` = 50 GiB free of 953 GiB, 95% used** [M]. WSL crashed three times on
2026-09-05 when this hit ~32 MB free.

| # | Candidate (from the project memory's own cleanup log + this survey) | Size | Action |
|---|---|---|---|
| E.1 | `~/.claude/jobs/6dc78be1/tmp/madden2004-c1.xiso.iso` | 3.1 GiB | owner's call — a duplicate of a rig-side file |
| E.2 | `/tmp/claude-1000/**` scratch from other sessions (incl. a 3.3 GiB `KrnlDebug.txt` in the pcsx2-VR scratch) | ~10 GiB | delete after checking nothing is live |
| E.3 | `scratchpad/hop1/` (hash-proof research data) | 2.4–2.7 GiB | keep until the texture work is finished, then delete |
| E.4 | `scratchpad/wp7b/iso/` (Agent B's) | 4.4 GiB | already flagged for deletion |
| E.5 | `~/.local/lib/python3.9` user-site packages | 7.5 GiB | owner's call |
| E.6 | Podman tagged images `private-hlds:1.0` (10.5 GiB), `xemu-win64-cross` (5.2 GiB), `duckstation-vr-build` (1.9 GiB) | 17.6 GiB | owner's call — the `hlds` container is a **live Half-Life server the user runs**; leave the running one alone |
| E.7 | **The VHDX does not shrink on its own.** After deleting inside WSL: `wsl --shutdown` then `Optimize-VHD -Path <ext4.vhdx> -Mode Full` (or diskpart `compact vdisk`) | reclaims to Windows | owner's call — it kills the session |
| E.8 | `/mnt/c/Roms/PS2/*.7z` / `*.zip` duplicates of ISOs already extracted (`ESPN NFL 2K5 (USA).7z` 2.59 GiB, `NCAA Football 2004 (USA).zip` 2.22 GiB) | 4.8 GiB | owner's call — the extracted ISOs sit beside them |
| E.9 | Verify after | `df -h /mnt/c` | ≥ 100 GiB free is comfortable; the *rule* is still "never write images here" |

---

## F. Order of operations

1. **E** (disk) and **D.2** (licence) — both free, both block later work.
2. **0.1–0.3** safety + capacity read.
3. **D.12–D.14** — prove the existing module passes conformance in a scratch copy, so the bar
   is known before anything new is written.
4. **A.2.1** — owner stages **ESPN NBA 2K5 (PS2)** on the rig. Then **A.4**: does its root
   carry `VC_<digits>`? That single read-only answer decides whether basketball is a
   2-day parameterisation or a from-scratch reverse-engineering project.
5. **B.1–B.4** for whatever is staged.
6. **D.1 + D.3** — the `ea_tdb` and `ps2_memcard` format packages (the Madden/NCAA critical path).
7. **C** — book the human for the first GS dump / franchise export only when a lane actually
   needs the witness. Nothing before that requires the GPU.
