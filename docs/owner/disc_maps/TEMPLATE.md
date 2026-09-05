# <Title> (<Region>) — PlayStation 2 disc map

Mapped <YYYY-MM-DD> with `tools/owner/ea_disc_map.py` (<schema>), read-only. Source: `<SERIAL>.<label>.map.json` / `.map.md` (counts below are copied from its Totals table by `--page`).
Grades: [M] measured by the mapper, [S] sourced (cite), [A] assumed. Every cell not marked otherwise is [M].

<!--
This file is the shape `tools/owner/ea_disc_map.py --page <map.json>` writes. Start from the generated
`.page.md`, not from this template: every cell marked [--page] below is written by the mapper and
must not be edited by hand. The agent fills only the cells marked [agent].
-->

## Identity [M]

| field | value |
|---|---|
| image | [--page] `<name>`, <bytes> bytes, <files> files / <dirs> dirs (raw CD noted when the sector size is 2352) |
| boot file / serial | [--page] `<BOOT>` / **<SERIAL>** |
| boot ELF | [--page] <bytes> bytes, sha256 `<hex>`, PCSX2 CRC `<HEX>` |
| whole image sha256 | [--page] `<hex>` |

## What is on the disc [M]

| kind | files | notes |
|---|---:|---|
| TERF | [--page] <n> | [--page] chains: <chain histogram>; alignments: <histogram> |
| TDB | [--page] <n> | [--page] <bare .DB paths> |
| ELF | [--page] <n> | [--page] <EXEC n, IRX n> |
| BIGF | [--page] <n> | [--page] <entries; RefPack-packed n; SHPS n> |
| QL01 | [--page] <n> | [--page] preload copies of container directories and members |
| VC-pack | [--page] <n> | [--page] pointer to the 2K5 inventory lane |
| <every other named kind> | [--page] | |
| other (unrecognised magic) | [--page] <n> | [--page] <k> distinct heads, hints by extension in the map [A] |

### Containers that matter (largest 12 by bytes, plus every container holding TDB or TEXT) [M]

| container | bytes | chain | members | codecs | decompressed formats | what it is for |
|---|---:|---|---:|---|---|---|
| [--page] `/DATA/….DAT` | … | TERF→DIR1→COMP→DATA | … | stored …, LZH1 … | MMAP …, SMF … | [--page] glossary phrase [S]/[A], or **[agent]** `<what it is for> [A]` — one phrase from the name, nothing from pixels or strings |

Refused containers, if any: [--page] path and the mapper's sentence.

### Archives that matter (largest 12) [M] — only on a disc with EA BIG archives

| archive | bytes | entries | member kinds (after RefPack) | extensions | RefPack | SHPS (images) | what it is for |
|---|---:|---:|---|---|---:|---|---|
| [--page] `/DATA/….BIG` | … | … | SHPS …, SCHl … | ssh …, dat … | … | … (…) | **[agent]** `<what it is for> [A]` |

### Databases [M]

| where | TDB members | schema → members | tables (records) of the first member per schema |
|---|---:|---|---|
| [--page] `/DATA/….DAT` | … | `<sig>` ×… | `TEAM` (33), `PLAY` (…), … |
| [--page] `/DATA/….DB` | 1 (bare file) | `<sig>` | … |

[--page] Distinct schema shapes: <n>. Table names shared with the Madden 08/09 TDB stack (`PLAY`, `TEAM`, `DCHT`, `INJY`, `COCH`, `SEAI`, `SLRI`, `PBPL`, `PLYS`): <list or "none">.
(On a disc without EA TDB the mapper writes the one sentence saying so.)

### Textures [M]

[--page] MMAP members: <n> across <k> containers; dimensions (disc-wide top 6, format 0x400 excluded): <WxH ×n, …>. MMAP version / format ids: <histogram>. SHPS image banks: <n> inside archives, <n> loose files. Faces / kits / UI split: from the container glossary above ([S]/[A] as marked), never from pixels.

### Text and audio [M]

[--page] TEXT members: <n> (<bytes>) in <k> containers. SCHl members: <n> in <k> containers (<paths>); PT-header platform / codec ids: <histogram> [S: vgmstream ea_schl]. Nested TERF: <n>. Unclassified members: <n> (magic histogram in the map).

## Page-by-page: what a studio could offer today (rungs as they stand, not as they could be)

| page | feeding containers | format | rung today | what lifts it |
|---|---|---|---|---|
| Uniforms & Equipment | [--page] | [--page] | [--page] | [--page] |
| Names, Numbers & Faces | [--page] | | | |
| Text & Team Identity | [--page] | | | |
| Field Art & Create-Team Art | [--page] | | | |
| Stadiums | [--page] | | | |
| Presentation | [--page] | | | |
| Menus & UI | [--page] | | | |
| The Crib | — | — | honest empty page | not a concept on this disc |
| Audio | [--page] | | | |
| Gameplay | executable | R5900 | unknown (code-patch scaffold) | translations |
| Playbooks & Plays | [--page] | | | |
| All Textures | [--page] | | | |
| Saves | — | — | honest empty page | saves are not the disc |

The rung column holds one of five values only: `read-only-mapped`, `read-only-mapped (schema + rows)`, `unknown (code-patch scaffold)`, `honest empty page`, `unknown`. Never an arrow, never a future rung.

## Writers: what could be rewritten with what exists today [M]/[A]

- [--page] `DATA`-chain containers (every member stored): `ea_terf.rewrite_member` exists. <n> containers: <list>.
- [--page] `COMP`-chain containers with LZH1 members: read only until an LZH1 encoder exists. <n> containers: <list>.
- [--page] `COMP`-chain containers whose packed members are RLE1 only (encoder exists in `ea_terf`): <n>.
- TDB rows: reader exists; writer needs the four CRCs and a verifier. [A] until built.
- [--page, BIG discs] EA BIG archives: no writer in the fork (BIG is not TERF; `ea_terf.rewrite_member` does not apply). [M]
- [--page, discs with .QKL] `QL01` preload files copy container directories and members: any edit to a container they name must be applied there too. [S: census §3]

## Open questions (one line each, no speculation)

- [--page] the top unclassified magics and the format-0x400 MMAP members, as questions.
- **[agent]** <add only questions the map raises; cite the map's row>

<!--
Do not:
- compute a sum, a count or a "top N" yourself — if the number is not in the .map.md, it is not in the page;
- copy one container's MMAP sizes into the disc-wide Textures sentence;
- call SHPS geometry, call a `.BIG`-named file an archive when its kind is SCHl, or say BIG archives are rewritable with ea_terf;
- write "read-only-mapped → extract-only" or any other arrow;
- quote a string from a member, describe a texture, or paste bytes.
-->
