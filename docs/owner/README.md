# Owner tooling (not shipped, not in the upstream PR)

The disc mapper (`tools/owner/ea_disc_map.py`, tests in `tests/owner/`), the mapping runbook and page template, the
retail-free disc maps and pages under `docs/owner/disc_maps/`, the scoping studies under `docs/owner/scoping/`, and the rig
runner `tools/owner/run_all_maps.py`. This branch tracks `ps2-lane` plus these files; it is never merged into `ps2-lane`
and never sent upstream. Rebase it onto `ps2-lane` when the lane moves.

## Runbooks

- `docs/owner/DISC_MAPPING_RUNBOOK.md` — mapping a disc on the rig with `ea_disc_map.py`, and writing its page.
- `docs/owner/DUMP_SESSION_MADDEN09.md` — the owner's Madden 09 texture-dump session at the rig's keyboard (PCSX2
  replacement identities), and how a rebuilt disc is witnessed in one line.
