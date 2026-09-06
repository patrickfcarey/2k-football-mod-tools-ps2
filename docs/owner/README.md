# Owner tooling (not shipped, not in the upstream PR)

The disc mapper (`tools/owner/ea_disc_map.py`), the module-readiness measurer
(`tools/owner/ea_module_readiness.py`), their tests in `tests/owner/`, the mapping runbook and page template, the
retail-free disc maps and pages under `docs/owner/disc_maps/`, the scoping studies under `docs/owner/scoping/`, and the rig
runner `tools/owner/run_all_maps.py`. This branch tracks `ps2-lane` plus these files; it is never merged into `ps2-lane`
and never sent upstream. Rebase it onto `ps2-lane` when the lane moves.

## The two tools, and the question each answers

- `ea_disc_map.py` — **what is on a disc**: containers, members, formats, archives, schemas, preload caches.
- `ea_module_readiness.py` — **what the shipped Madden 09 readers can do with it**: the module's own
  `ea_terf`, `ea_tdb`, `ea_schl`, `mmap_art` and preload-cache parser run over another disc, with every
  refusal grouped by sentence and the load-bearing table schemas compared against Madden 09's. It writes
  `<SERIAL>.<label>.readiness.json`, a page under `docs/owner/scoping/readiness/`, and the cross-title
  table in `docs/owner/scoping/READINESS_SUMMARY.md`.

## Runbooks

- `docs/owner/DISC_MAPPING_RUNBOOK.md` — mapping a disc on the rig with `ea_disc_map.py`, and writing its page.
- `docs/owner/DUMP_SESSION_MADDEN09.md` — the owner's Madden 09 texture-dump session at the rig's keyboard (PCSX2
  replacement identities), and how a rebuilt disc is witnessed in one line.
