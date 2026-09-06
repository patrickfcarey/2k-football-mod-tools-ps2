# Madden NFL 09 (PS2) — the texture-dump session, step by step

You are at the rig's keyboard. This session gives the tools two things they cannot get without a
running game: the **PCSX2 texture-replacement identities** of Madden 09's uniforms (so the Uniforms
page can write a PCSX2 pack with the right file names), and, if you also boot a rebuilt disc, the
**in-game witness** that turns an offline-proved writer into a runtime-proved one. Nothing here
modifies your disc image. Budget: about 30 minutes for the dump, 10 more per rebuilt disc you check.

Everything below runs on the rig (`pacarey-IdeaPad-Gaming-3-15ARH7`), in a terminal, as you.

## 0. Before you start

1. Make sure nobody is in the VR headset and no emulator is running:

       pgrep -x pcsx2-qt; pgrep -x mupen64plus; pgrep -f "[q]emu-system-i386"

   All three must print nothing. If one prints a number, stop and close that program first.
2. The disc is already on the rig: `~/Games/ps2/Madden NFL 09 (USA).iso` (retail, SLUS-21770). Do not
   use the Deluxe image for this: the identities we want are the retail game's.
3. The emulator is the PenguinScreen2 build at `~/penguinscreen2-dev/build/bin/pcsx2-qt`. Its
   settings live in `~/.config/PenguinScreen2/`. Dumps will land in
   `~/.config/PenguinScreen2/textures/SLUS-21770/dumps/`.

## 1. Tell the emulator to dump textures for this game only

Create the per-game settings file (retail CRC `38014255`; if the emulator writes a file with a
different CRC in its name after the first boot, copy these lines into that file instead):

    mkdir -p ~/.config/PenguinScreen2/gamesettings ~/.config/PenguinScreen2/textures/SLUS-21770/dumps
    cat > ~/.config/PenguinScreen2/gamesettings/SLUS-21770_38014255.ini <<'INI'
    [EmuCore/GS]
    DumpReplaceableTextures = true
    DumpReplaceableMipmaps = false
    DumpTexturesWithFMVActive = false
    LoadTextureReplacements = false
    ClassicTextureNames = true
    [EmuCore]
    EnablePatches = true
    EnableCheats = false
    INI

`ClassicTextureNames = true` is deliberate: it makes the dumped file names use the same convention the
2K5 pack uses (the one every PCSX2 build loads), so our tools read both discs the same way.
`LoadTextureReplacements = false` keeps this a clean dump: nothing is swapped in while we record.

## 2. Boot the game

    cd ~/penguinscreen2-dev && ./build/bin/pcsx2-qt ~/Games/ps2/"Madden NFL 09 (USA).iso"

The window opens and the game boots. If it asks about a BIOS or a memory card, accept the defaults
(the profile already has `SCPH39001.bin`). Leave every graphics setting as it is.

## 3. Make the game draw every uniform

The dump only contains textures the game actually drew, so walk the screens that draw them. Take
your time on each; a second or two per screen is enough.

1. **Team select.** Play Now → Exhibition. On the team-select screen, cycle through all 32 teams on
   both sides (left stick / d-pad). Each team's helmet and jersey preview is a texture upload.
2. **Uniform select.** On the same screen (or the next one, "Uniforms" / triangle), cycle every
   uniform choice for a few teams: home, away, alternate, throwback where the team has one.
3. **Play a few snaps.** Start the game with two teams. Play or sim two or three plays from
   scrimmage, then pause. This draws the on-field uniforms, helmets, numbers and the field art.
4. **Swap the two teams and repeat once** with two different teams (ideally a team with an
   alternate uniform), so both home and away kits are drawn at field resolution.
5. **Create-a-Team / Edit Player** if you have five more minutes: Features → Create Team → the
   uniform editor draws the blank uniform templates, which is exactly what a modder edits.
6. Optional but valuable: make a **save state** at the team-select screen (F1 by default, or
   System → Save State → slot 1). A state lets us re-run dumps headless later without you.

Watch the dump folder grow in a second terminal:

    watch -n 5 'ls ~/.config/PenguinScreen2/textures/SLUS-21770/dumps | wc -l'

Several hundred to a few thousand files is normal. When the count stops rising as you cycle, the
screens are exhausted.

## 4. Quit cleanly and package

Quit the emulator from its menu (System → Shut Down, then close the window). Then:

    pgrep -x pcsx2-qt && echo "still running - wait, then check again" || echo "clean"
    cd ~/.config/PenguinScreen2/textures/SLUS-21770
    ls dumps | wc -l
    tar czf ~/madden09-dumps-$(date +%Y%m%d).tgz dumps
    ls -la ~/madden09-dumps-*.tgz
    ls ~/.config/PenguinScreen2/sstates/ | grep -i 21770

Tell me the file count and the tarball name. I fetch the tarball over SSH (read-only), run the
identity matcher against your disc's own textures, and the Uniforms page starts naming its pack
files. Nothing from the dump is committed anywhere: the identities we keep are names and hashes.

## 5. Later: witnessing a rebuilt disc (the in-game proof for a writer)

When a writer is offline-proved, I will build an image for you from your disc with one visible
edit (a renamed player, a changed jersey number, a recoloured helmet) and put it at
`~/2k5-ps2-final/madden09/<name>.iso` on the rig with a receipt beside it saying exactly what
changed and where to look. The check:

1. Same step 0 (nothing running).
2. `cd ~/penguinscreen2-dev && ./build/bin/pcsx2-qt ~/2k5-ps2-final/madden09/<name>.iso`
3. Go to the screen the receipt names (for a roster edit: the team's roster; for a uniform: that
   team on team select). Look for the edit.
4. Tell me what you saw, in one line: "Bears WR #85 now reads DEMO WRITER" or "no change" or "the
   game crashed at X". A photo of the screen is a bonus, not required.
5. Quit the emulator from its menu.

That one line is what moves the row from offline-proved to runtime-proved, and it goes into the
release notes with the date.

## What not to do

- Do not enable texture loading (`LoadTextureReplacements`) during the dump.
- Do not use the Deluxe disc for the dump.
- Do not delete the `dumps` folder afterwards; I may need to re-match later.
- Do not launch a second emulator while one is running; if the window hangs, `pkill -x pcsx2-qt`,
  wait ten seconds, check with `pgrep -x pcsx2-qt`, and start again.

## The GS-dump route (what actually happened on 2026-09-05)

You took single-frame GS dumps instead of texture dumps, and that works just as well: a GS dump replays
headless with texture dumping on. So the alternative to sections 1 to 4 is:

1. Boot the game as in section 2 with no special settings.
2. On each screen you want covered, take a GS dump (the GS-dump hotkey; the emulator writes
   `~/.config/PenguinScreen2/snaps/<Title>_<SERIAL>_<stamp>.gs.zst` and a `.png` beside it). The
   thumbnail is what the fixtures manifest describes, so aim the frame at what you want named.
3. Quit, and tell me. I file the dumps in the private fixtures repo, then run
   `tools/owner/harvest_textures.sh` on the rig (`ssh rig 'bash -s' < tools/owner/harvest_textures.sh`,
   after the live-session check as its own command). It replays every dump of the day twice, classic
   and modern names, and leaves `~/texdumps-<day>.tgz`. It parks the texture keys of any per-game ini
   for the run and restores the files byte-identical.

2026-09-05: 18 dumps, 8 games, 8,718 texture files in 60 seconds; the Madden 09 frame (Giants and
Patriots captains) gave 348 classic-named textures, 77 of them the 128x128 uniform-part size.

## Per-draw dumps: when the replacement dumper cannot see a texture (added 2026-09-06)

The texture-replacement dumper only writes textures whose source is a plain EE→GS transfer. A
texture the game builds **on the GS** — drawn into a render target and then sampled — never
appears in it, however many frames are captured. MVP Baseball 2005's `0x0E` kits and portraits
are that case: three frames drew them and the replacement dump held none of them, which two
pairing methods proved (`docs/product/EA_SHPS_FORMAT.md` §5.1 on the lane).

The same `.gs.zst` files hold the answer. The runner's per-draw dump writes every texture a draw
uses regardless of source, the render targets before and after, every transfer image and the
per-draw registers and vertices:

```bash
pgrep -x pcsx2-qt; pgrep -x mupen64plus; pgrep -f "[q]emu-system-i386"      # H-2, its own command, read it
SERIAL=SLUS-21135 DAY=20260905 ssh rig 'bash -s' < tools/owner/harvest_draws.sh
```

`tools/owner/harvest_draws.sh` passes `-dump rt,tex,i,tr -dumpdir <dir>`; `-dumpdir` is load-bearing
because `Pcsx2Config` disables draw dumping unless **both** the HW and SW dump directories are set and
`-dumpdir` seeds both (`-dumpdirhw` alone does not — measured, it logged "directory is unconfigured"
twice). One frame is ~17,000 files and ~700 MB in about 40 s. File names carry the draw number, the GS
address and the pixel format (`itex_gs_<addr>_P_8` is an 8-bit paletted input texture; `itpx` is its
palette as a 16×16 image; `rt0`/`rt1` the target before and after; `*_transfers.txt` lists the uploads).
Pair an `itpx` against the disc palettes to find the decoded image, invert the palette for the true
index image, and the codec is a truth table. Nothing from these dumps is committed: names, hashes and
counts only, as with the texture harvest.
