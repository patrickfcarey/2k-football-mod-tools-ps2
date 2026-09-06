#!/bin/bash
# harvest_textures.sh — replay today's GS dumps headless ON THE RIG and collect the
# texture dumps each frame produces, in both naming conventions (classic, modern).
# Run as:  ssh rig 'bash -s' < harvest_textures.sh
# The caller has ALREADY run the H-2 live-session check as its own command and read
# it; this script re-checks and refuses on a hit, and is never chained behind a launch.
# It creates files under ~/texdumps-<day>/ and touches nothing else permanently:
# the two per-game ini files that carry texture keys are copied aside, edited for the
# run, and copied back on exit; no pre-existing dumps directory is deleted (a run
# refuses if one exists).
set -u
CHECKOUT="$HOME/penguinscreen2-dev"
GSRUNNER="$CHECKOUT/build/bin/pcsx2-gsrunner"
CFG="$HOME/.config/PenguinScreen2"
# DAY selects which day's GS dumps to replay; SERIAL narrows to one disc (default: every serial
# that day). Both were hardcoded until 2026-09-06, so a caller passing them silently re-harvested
# the wrong day -- one wasted 25,867-file run before it was noticed.
DAY="${DAY:-$(date +%Y%m%d)}"
SERIAL="${SERIAL:-}"
OUT="$HOME/texdumps-$DAY${SERIAL:+-$SERIAL}"
[ -x "$GSRUNNER" ] || { echo "FATAL: no gsrunner at $GSRUNNER"; exit 1; }
if pgrep -x pcsx2-qt >/dev/null 2>&1; then echo "H-2: a live pcsx2-qt exists; refusing."; exit 3; fi
mkdir -p "$OUT"

mk_ini() { # dump classic load path
  printf '[EmuCore/GS]\nDumpReplaceableTextures=%s\nDumpDirectTextures=true\nDumpPaletteTextures=true\nClassicTextureNames=%s\nLoadTextureReplacements=%s\nLoadTextureReplacementsAsync=true\nDumpTexturesWithFMVActive=false\n' \
    "$1" "$2" "$3" > "$4"
}

# Per-game settings override the -ini we pass: park the three texture keys while we run.
GS_BAK="$OUT/gamesettings-backup"; mkdir -p "$GS_BAK"
restore() {
  for b in "$GS_BAK"/*.ini; do [ -e "$b" ] && cp -f "$b" "$CFG/gamesettings/$(basename "$b")"; done
  echo ">> per-game settings restored from $GS_BAK"
}
trap restore EXIT

SERIALS=()
total=0
for DUMP in "$CFG"/snaps/*_${SERIAL:-*}_"$DAY"*.gs.zst; do
  [ -e "$DUMP" ] || { echo "no GS dump matches *_${SERIAL:-<any>}_${DAY}*.gs.zst"; exit 4; }
  name=$(basename "$DUMP" .gs.zst)
  SERIAL=$(printf '%s' "$name" | sed -E 's/.*_(S[LC][UE]S-[0-9]+)_.*/\1/')
  stamp=$(printf '%s' "$name" | sed -E 's/.*_([0-9]{14})$/\1/')
  case " ${SERIALS[*]:-} " in *" $SERIAL "*) ;; *)
    SERIALS+=("$SERIAL")
    if [ -e "$CFG/textures/$SERIAL/dumps" ]; then echo "REFUSE: $CFG/textures/$SERIAL/dumps already exists; move it aside first"; exit 4; fi
    for g in "$CFG"/gamesettings/${SERIAL}_*.ini; do
      [ -e "$g" ] || continue
      if grep -qE '^[[:space:]]*(LoadTextureReplacements|DumpReplaceableTextures|ClassicTextureNames)[[:space:]]*=' "$g"; then
        cp -f "$g" "$GS_BAK/$(basename "$g")"
        grep -vE '^[[:space:]]*(LoadTextureReplacements|DumpReplaceableTextures|ClassicTextureNames)[[:space:]]*=' "$GS_BAK/$(basename "$g")" > "$g"
        echo ">> parked texture keys in $(basename "$g")"
      fi
    done;;
  esac
  for leg in classic modern; do
    [ "$leg" = classic ] && classic=true || classic=false
    dest="$OUT/$SERIAL/$stamp/$leg"; mkdir -p "$dest" "$CFG/textures/$SERIAL/dumps"
    mk_ini true "$classic" false "$dest.ini"
    t0=$(date +%s)
    "$GSRUNNER" -renderer Vulkan -surfaceless -loop 1 -noshadercache -ini "$dest.ini" -logfile "$dest.emulog" -- "$DUMP" > "$dest.stdout" 2>&1
    rc=$?
    n=$(find "$CFG/textures/$SERIAL/dumps" -type f | wc -l)
    find "$CFG/textures/$SERIAL/dumps" -type f -exec mv -t "$dest/" {} +
    rmdir "$CFG/textures/$SERIAL/dumps" 2>/dev/null
    total=$((total+n))
    printf '%s %s %-8s exit=%s dumped=%5s in %ss\n' "$SERIAL" "$stamp" "$leg" "$rc" "$n" "$(( $(date +%s) - t0 ))"
  done
done
echo "total texture files: $total"
tar czf "$OUT.tgz" -C "$HOME" "texdumps-$DAY" && ls -la "$OUT.tgz" | awk '{print "tarball:", $5, "bytes", $NF}'
sha256sum "$OUT.tgz" | cut -c1-16
echo "HARVEST_DONE"
