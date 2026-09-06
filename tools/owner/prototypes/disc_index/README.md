# PROTOTYPE — one disc index

**This is not shipped, not imported by any module, not run by any gate, and is deleted when
`docs/owner/specs/ONE_DISC_INDEX.md` is built for real.** It exists to prove that
specification's load-bearing claim: that one walk over a disc produces an artefact from which
the censuses several independent walkers publish today can be regenerated exactly.

It changes nothing. `tools/owner/ea_disc_map.py` and `tools/owner/ea_module_readiness.py` are
described by the specification and were not touched.

## The four files

| File | What |
|---|---|
| `identify.py` | the single identifier. Forward tags (`CPTH`, never `HTPC`), the RenderWare top-level walk (multi-section streams identify), per-family shape rules. Bounded to a 96-byte window plus 12 bytes per top-level section. |
| `walk.py` | the builder. ISO9660 → files → containers (`TERF`, `BIGF`, ZIP, `.ZIH`) → members, JSON Lines out. `--deep` adds per-member digests and TDB schemas and says so in the disc row. |
| `regen.py` | regenerates published censuses **from an index alone** and diffs them leaf by leaf. Also carries `retail_free_violations` and the two vocabulary projections. |
| `map_md.py` | parses the numbers back out of a checked-in `.map.md`, so the diff is against the repository rather than against figures typed into a script. |

## Running it

```bash
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1

PYTHONPATH=. python3 -m tools.owner.prototypes.disc_index.walk \
    --iso <image>.iso --out <dir> --label "<Title> (USA)" [--deep]

# the two Blitz measured documents, regenerated from the index alone
PYTHONPATH=. python3 -m tools.owner.prototypes.disc_index.regen \
    --index <dir>/SLUS-20051.index.jsonl --check blitz2002

# the NCAA 09 disc-map page's File kinds and Totals tables, likewise
PYTHONPATH=. python3 -m tools.owner.prototypes.disc_index.regen \
    --index <dir>/SLUS-21752.index.jsonl --check terf-map \
    --map docs/owner/disc_maps/SLUS-21752.NCAA-Football-09-USA.map.md

PYTHONPATH=. python3 tests/owner/test_disc_index_prototype.py     # 25 tests, synthetic only
```

Read-only: an image is opened `"rb"` and nothing is written beside it. Retail-free: names,
offsets, lengths, counts, format identities, schema field names/widths and digests — and
`regen.retail_free_violations` is the executable check, run over every index the round-trip
built.

## What it does not cover

The real builder needs `PAK `, `EFS `/`.HDR`, `MWo3`, the Midway sound bank, `.OBF`, `VAGp`,
`QL01` preload caches, raw-CD (2352-byte sector) images, and the `--summary` / `--compare`
aggregations. All are read by `ea_disc_map.py` today; none are here.

Results: `docs/owner/specs/measured/disc-index-roundtrip.json` and
`docs/owner/specs/measured/disc-index-consumers.json`.
