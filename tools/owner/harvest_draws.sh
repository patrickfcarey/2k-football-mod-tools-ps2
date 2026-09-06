#!/bin/bash
# harvest_draws.sh — replay GS dumps headless ON THE RIG with the runner's PER-DRAW dump, which writes
# every texture a draw uses regardless of its source (the replacement dumper skips textures that came
# from a render target), every render target before/after, every EE->GS transfer image, and per-draw
# context/vertex text. This is the answer key for a codec the GS decodes itself (MVP 2005's SHPS 0x0E).
# Run as:  SERIAL=SLUS-21135 DAY=20260905 ssh rig 'bash -s' < tools/owner/harvest_draws.sh
# The caller has ALREADY run the H-2 live-session check as its own command and read it; this script
# re-checks and refuses on a hit, and is never chained behind a launch. Output: ~/drawdumps-<SERIAL>-<DAY>/<stamp>/
# (~17k files / ~700 MB per frame) plus a tarball. Nothing from a dump is ever committed: names, hashes, counts only.
set -u
CHECKOUT="$HOME/penguinscreen2-dev"; GSRUNNER="$CHECKOUT/build/bin/pcsx2-gsrunner"; CFG="$HOME/.config/PenguinScreen2"
SERIAL="${SERIAL:?SERIAL, e.g. SLUS-21135}"; DAY="${DAY:?DAY, e.g. 20260905}"; KINDS="${KINDS:-rt,tex,i,tr}"
OUT="$HOME/drawdumps-$SERIAL-$DAY"
[ -x "$GSRUNNER" ] || { echo "FATAL: no gsrunner at $GSRUNNER"; exit 1; }
if pgrep -x pcsx2-qt >/dev/null 2>&1; then echo "H-2: a live pcsx2-qt exists; refusing."; exit 3; fi
mkdir -p "$OUT"; ini="$OUT/notex.ini"; printf '[EmuCore/GS]\nDumpReplaceableTextures=false\nLoadTextureReplacements=false\n' > "$ini"
total=0
for DUMP in "$CFG"/snaps/*_"$SERIAL"_"$DAY"*.gs.zst; do
  [ -e "$DUMP" ] || { echo "no GS dump matches *_${SERIAL}_${DAY}*.gs.zst"; exit 4; }
  stamp=$(basename "$DUMP" .gs.zst | sed -E 's/.*_([0-9]{14})$/\1/'); dest="$OUT/$stamp"; rm -rf "$dest"; mkdir -p "$dest"
  t0=$(date +%s)
  # -dumpdir seeds BOTH the HW and SW draw-dump directories; Pcsx2Config disables draw dumping unless both are set.
  timeout -k 30 600 "$GSRUNNER" -renderer Vulkan -surfaceless -loop 1 -noshadercache -ini "$ini" -dump "$KINDS" -dumpdir "$dest" -logfile "$dest.emulog" -- "$DUMP" > "$dest.stdout" 2>&1
  rc=$?; n=$(find "$dest" -type f | wc -l); total=$((total+n))
  printf '%s %s exit=%s files=%6s size=%s in %ss\n' "$SERIAL" "$stamp" "$rc" "$n" "$(du -sh "$dest" | cut -f1)" "$(( $(date +%s) - t0 ))"
  grep -q "directory is unconfigured" "$dest.emulog" && echo "  WARNING: draw dumping was disabled by the config sanity check"
done
echo "total files: $total"
tar cf "$OUT.tar" -C "$HOME" "$(basename "$OUT")" && ls -la "$OUT.tar" | awk '{print "tarball:", $5, "bytes", $NF}'
echo "HARVEST_DRAWS_DONE"
