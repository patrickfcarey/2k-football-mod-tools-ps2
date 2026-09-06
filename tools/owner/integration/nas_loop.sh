#!/bin/bash
# Run the full test loop for a worktree on the NAS turret. Usage: nas_loop.sh <worktree> [workers] [name]
#   rsyncs the tree (retrying the link, which drops for ~30 s at times), ships the current
#   ci_tests_nas.sh beside it, leaves a .git marker (self_update tests as 'tarball' without one),
#   copies the gitignored fixtures, runs the loop, prints the SUMMARY and FAILED FILES lines.
# Env: NAS (default pacarey@192.168.68.185), NAS_BASE (default /turret/builds/2k5).
set -u
W="${1:?worktree}"; WORKERS="${2:-28}"; NAME="${3:-$(basename "$W")}"
NAS="${NAS:-pacarey@192.168.68.185}"; BASE="${NAS_BASE:-/turret/builds/2k5}"; D="$BASE/$NAME"
HERE="$(cd "$(dirname "$0")" && pwd)"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15"
for i in 1 2 3 4 5 6; do
  rsync -a --delete --exclude '/.git' --exclude reports/assets --exclude '.tests-parallel-logs' -e "$SSH" "$W/" "$NAS:$D/" && break
  echo "rsync attempt $i failed; retrying in 30 s"; sleep 30
done
for i in 1 2 3 4 5 6; do
  scp -q -o BatchMode=yes -o ConnectTimeout=15 "$HERE/ci_tests_nas.sh" "$NAS:$BASE/ci_tests_nas.sh" && break
  echo "scp attempt $i failed; retrying in 30 s"; sleep 30
done
HEAD_SHA=$(git -C "$W" rev-parse --short HEAD 2>/dev/null)
$SSH "$NAS" "export HEAD_SHA='$HEAD_SHA'; { [ -d '$D/.git' ] || { rm -f '$D/.git'; mkdir -p '$D/.git'; }; }; mkdir -p '$D/reports' && rm -rf '$D/reports/assets' && cp -r '$BASE/fixtures-assets' '$D/reports/assets' && cd '$BASE' && bash ci_tests_nas.sh '$D' '$WORKERS' 2>&1 | tail -8"
