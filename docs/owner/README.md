# Owner tooling (not shipped, not in the upstream PR)

The disc mapper (`tools/owner/ea_disc_map.py`), the module-readiness measurer
(`tools/owner/ea_module_readiness.py`), their tests in `tests/owner/`, the mapping runbook and page template, the
retail-free disc maps and pages under `docs/owner/disc_maps/`, the scoping studies under `docs/owner/scoping/`, and the rig
runner `tools/owner/run_all_maps.py`. This branch tracks `ps2-lane` plus these files; it is never merged into `ps2-lane`
and never sent upstream. Rebase it onto `ps2-lane` when the lane moves.

## The two tools, and the question each answers

- `ea_disc_map.py` — **what is on a disc**: containers, members, formats, archives, schemas, preload caches, and
  since `ea_disc_map/v3` the non-EA families on the Midway Blitz discs and AND 1 Streetball (ZIP + `.ZIH`,
  `MWo3`, `PAK ` + `0x11111111` metadata — whose objects, members, databases and `SEC ` containers it reads
  through the product packages `midway_pak` / `midway_db` / `midway_sec` — the Midway sound bank, `.OBF`,
  `EFS ` + `.HDR`, Sony `VAGp`) — see `docs/owner/scoping/BLITZ_AND1_FORMATS.md`.
- `ea_module_readiness.py` — **what the shipped Madden 09 readers can do with it**: the module's own
  `ea_terf`, `ea_tdb`, `ea_schl`, `mmap_art` and preload-cache parser run over another disc, with every
  refusal grouped by sentence and the load-bearing table schemas compared against Madden 09's. It writes
  `<SERIAL>.<label>.readiness.json`, a page under `docs/owner/scoping/readiness/`, and the cross-title
  table in `docs/owner/scoping/READINESS_SUMMARY.md`.

## Runbooks

- `docs/owner/DISC_MAPPING_RUNBOOK.md` — mapping a disc on the rig with `ea_disc_map.py`, and writing its page.
- `docs/owner/scoping/BLITZ_AND1_FORMATS.md` — the Midway / AND 1 container study: what each family is made of,
  what a module for it would need, the rung it earns today, and what stays unknown.
- `docs/owner/DUMP_SESSION_MADDEN09.md` — the owner's Madden 09 texture-dump session at the rig's keyboard (PCSX2
  replacement identities), and how a rebuilt disc is witnessed in one line.

- `LESSONS_2026-09-06.md` — what cost us that day, ranked, with where each fix is enforced; `tools/owner/integration/` — the resolver, pin audit, gate and NAS loop that used to live in a scratch directory.
- `CAPTURE_WISHLIST.md` — the standing queue of savestates and GS dumps to take on the rig, ranked by what each unblocks.
- `SAVESTATE_QUEUE.md` — the rig checklist: which savestates to take, where to stand, and what each unblocks (incl. headless writer proof).

## Specifications (`docs/owner/specs/`)

Designs decided but not yet built. Each says what to build well enough that it can be built in
one pass without re-deciding anything, and each carries its own measurements under
`docs/owner/specs/measured/`.

- `ONE_DISC_INDEX.md` — one walk over a disc, one artefact; every tool that walks the disc for
  itself reads it instead. Leads on accuracy: the `CPTH`-read-as-`HTPC` and the "`.dff` is not
  RenderWare" corrections both exist because there is no single identifier to fix. Decides the
  artefact (JSON Lines, per file → per container → per member), the content-addressed store on
  the NAS, the identifier that becomes authoritative, what each of seven consumers stops doing
  (1,977 of 10,052 lines), the read budget (a 96-byte window, not a 55 ms member decode), and
  the migration. Proved by a prototype under `tools/owner/prototypes/disc_index/` that
  regenerates five published censuses across two disc families byte-identically from the index
  alone — `docs/owner/specs/measured/disc-index-roundtrip.json`.
