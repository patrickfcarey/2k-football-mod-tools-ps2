# Savestate queue — what to capture, where to stand, what each one buys

A rig session checklist. Ordered so the earliest states unblock the most, and grouped so one boot of
a game yields several. Every state goes to `penguinscreen2-fixtures` under
`sstates/<SERIAL>-<game-slug>/<YYYYMMDD>-<scene-slug>/` with a manifest describing what the screen
**actually shows**, then `tools/fixtures.py add` → fill every `FILL-ME` → `index` → `verify` → push.

## Why savestates specifically, and why now

Two uses, and the second is new.

**1. A savestate is the decoded truth.** EE RAM holds what the game *built* from the disc: textures the
GS decoded, tables the boot ELF assembled, rosters after load-time transforms. Any question shaped
"the disc has X, what does the game make of it" is a capture plus a search rather than a format hunt.

**2. A savestate makes writer proof headless — this is the big one.** Today every writer on every
module is `offline-writer-proved`: the verifier re-reads the rebuilt image's own bytes and confirms the
edit landed inside its declared ranges with everything else byte-identical. Nothing boots. The gap to
`runtime-proved` is a person watching a screen, which is the most expensive gate we have and the reason
six modules are stalled at the same place.

A savestate closes it, because **every writer we ship is same-length**: it rewrites bytes inside a file
and the image comes back the exact size it went in, disc geometry untouched. So a state captured on the
original disc restores against a patched copy, and **anything the game loads after the state is restored
comes from the patched bytes**. Boot patched image → load state → advance to the screen → capture frame →
diff against the same run on the original. The changed pixels are the proof, the diff is a file, and the
whole thing is a script that can run on every writer of every module on every change.

**Where to stand is therefore the whole trick: one screen *before* the thing the writer changes gets
loaded.** A state taken while a uniform is already on screen proves nothing, because that texture is
already in RAM. A state at the team-select screen, one step before the game loads kits and the stadium,
proves everything that follows.

## The queue

### A. States for headless writer proof — one boot each, two states per game

For each, take **state 1** at the menu named, then advance to the screen named and take **state 2**.
State 1 is the one the harness restores; state 2 is the reference for what the screen should look like.

| # | Game | State 1 — stand here | Then advance to | Proves |
|---|---|---|---|---|
| A1 | **Madden 09** `SLUS-21770` | team-select / matchup screen, before kickoff | first play from scrimmage | uniforms, field art, stadiums, presentation, faces, team data — **7 of the 11 writers at once** |
| A2 | **Madden 09** | main menu, before entering any mode | roster or depth-chart screen | text, roster/team databases, menu art |
| A3 | **NCAA 09** `SLUS-21752` | team-select, before kickoff | first play | uniforms, field art, stadiums, presentation, faces — 6 of 9 |
| A4 | **NCAA 09** | main menu | roster screen | player records, identity tables, menu text |
| A5 | **MVP 2005** `SLUS-21135` | team-select, before the game loads a park | first pitch | stadium, presentation, menu textures — and the kit/portrait art if the codec lands |
| A6 | **MVP 2005** | main menu | roster / lineup screen | the 18 CSV database tables, LOCH strings |
| A7 | **NFL Blitz 2002** `SLUS-20051` | team-select | first play | player names, crowd tables, field table — **all 4 writers**, and the disc has no capture of any kind yet |
| A8 | **NFL Blitz 2003** `SLUS-20474` | team-select | first play | same 4 writers on the second disc |
| A9 | **NFL 2K5 PS2** `SLUS-20919` | team-select | first play | text, colours, playbooks, stadium position |

### B. Research states — a specific question each

| # | Game | Stand here | Answers |
|---|---|---|---|
| B1 | **MVP 2005** | **in-game with kits and a batter's face on screen** (mid at-bat, close camera) | The `0x0E` codec. Its decoded pixels are in EE RAM; the endpoint-thumbnail correlation finds them at every `0x0E` size (stride `w` for 8-bit, `4w` for RGBA). Unblocks **23,954 images** — every kit, portrait, head and piece of field art on the disc |
| B2 | **NCAA 09** | **two states around one in-game uniform change**: open the uniform selector, save, pick a different kit, save again | The missing kit table. All six of NCAA's kit tables are zero rows, so the assignment is built at runtime. The bytes that differ between the two states **are** the kit field. Would move the uniform page from repainting textures to editing kit records |
| B3 | **Madden 09** | same two-state trick around any single roster edit (change one player's number in the game's own UI) | Confirms the PLAY field map from the game's side rather than from the schema, and gives the same technique a worked example for every future title |

### C. Already covered — do not re-take

GS dumps exist for NCAA 09 (2 frames) and MVP 2005 (3 frames), and their per-draw replays are on the dev
box. Madden 09 has 33 frames and four built witness discs waiting on a boot (`~/2k5-ps2-final/madden09/`,
`WITNESS_CHECKLIST.md`) — that boot is still worth doing, and A1/A2 can be taken in the same session.

## Notes for the session

- **H-2 first**, as its own command, and read it: `pgrep -x pcsx2-qt; pgrep -x mupen64plus; pgrep -f "[q]emu-system-i386"`.
- Retail images only, the ones already pinned; nothing from a state is ever committed to a code repo.
- A `.p2s` is ~16 MB and already a zip — fixtures repo, never a code repo, per the standing rule.
- Name the scene for what is on screen, not for what it is for: the manifest must describe the pixels.
