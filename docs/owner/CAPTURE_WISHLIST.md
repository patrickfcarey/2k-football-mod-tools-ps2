# What to capture next, and what each capture buys

The owner can take a savestate or a GS dump on the rig in minutes and has said so. This file is the
standing queue so a single rig session serves every question at once instead of one agent at a time
asking for one frame. Ranked by what the capture unblocks per minute of capture.

Two kinds, and they answer different questions:

- **GS dump** (`.gs.zst`, the existing runbook) — a recording of one frame's draw commands. Replayed
  headless it yields either texture files (`tools/owner/harvest_textures.sh`) or every draw's textures,
  render targets and registers (`tools/owner/harvest_draws.sh`). Answers *"what reached the screen and
  from which disc bytes"*, which is what turns a derived texture identity into a confirmed one.
- **Savestate** (`.p2s`) — the whole machine. EE RAM holds the **decoded** form of everything the game
  built: textures the GS produced, tables the boot ELF assembled, rosters after load-time transforms.
  Answers *"what did the game turn this disc data into"*. **Two savestates around one in-game change,
  diffed, name the bytes of a field** — the fastest field map there is, and the only route to data that
  exists at runtime but not as a disc table.

Both go to `penguinscreen2-fixtures` (private, LAN-only) with a manifest describing what the pixels
actually show. Nothing from a capture is committed to a code repo: names, hashes and counts only.

## The queue

| # | Disc | Capture | Kind | Buys |
|---|---|---|---|---|
| 1 | **NFL Blitz 2002 / 2003** `SLUS-20051` / `SLUS-20474` | any two frames each: one in-game play, one team-select screen | GS dump | **No dump of either disc exists.** All 4,166 and 6,365 texture identities are derived and none confirmed. Two frames per disc is the whole difference between "computed" and "witnessed" for both new modules |
| 2 | **MVP Baseball 2005** `SLUS-21135` | a savestate **in-game with kits and a batter's face on screen** | savestate | The `0x0E` codec. Its decoded pixels are in EE RAM; the endpoint-thumbnail correlation finds them at every `0x0E` size (stride `w` for 8-bit, `4w` for RGBA). This is the only remaining route if the per-draw dumps do not close it, and it unblocks **23,954 images** — every kit, portrait, head and piece of field art on the disc |
| 3 | **NCAA Football 09** `SLUS-21752` | two savestates around one in-game uniform change (pick a team's alternate kit in the UI, save either side) | savestate ×2 | The missing kit table. NCAA's six kit tables are all zero rows, so the assignment is built at runtime; a two-state diff names the bytes directly. Would move the uniform page from repainting textures to editing kit records |
| 4 | **NCAA Football 09** | gear/equipment select, team-select or schedule screen, stadium select, a loading screen, a coach close-up | GS dump ×5 | 1,111 textures across five containers that the two existing frames never drew. Equipment select is the cheapest rewrite on the disc (no preload cache names it) |
| 5 | **MVP Baseball 2005** | the front end: main menu, mode select, team select, roster/lineup | GS dump | 706 images over 161 archives with nothing confirmed, almost all front-end; `BKGNDS.BIG` (105), `SHARED.BIG` (50), `EASOART.BIG` (48) |
| 6 | **Madden 09** `SLUS-21770` | the four witness discs on the rig, booted against `WITNESS_CHECKLIST.md` | boot | Eleven offline-proved writers become runtime-proved. Not a capture, the last gate on the module |
| 7 | **MVP Baseball 2005** | Home Run Showdown | GS dump | `HRSONLY.BIG`, 48 images reachable no other way |
| 8 | **Blitz Pro / The League** `SLUS-20631` / `SLUS-21128` | one in-game frame each | GS dump | Their pack objects are located and their RenderWare dictionaries named but nothing is drawn; a frame says whether the shared TXD reader decodes them |

## Standing rule

When an agent's report ends with "the owner should capture X", the coordinator adds a row here rather
than letting it sit in a transcript. When a capture lands, strike the row and say which measured
document it moved.
