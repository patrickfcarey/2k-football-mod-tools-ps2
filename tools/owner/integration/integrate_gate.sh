#!/bin/bash
# Pre-push gate for a 2k-football-mod-tools worktree. Usage: integrate_gate.sh <worktree> [--no-release]
# One line per gate with its PASS token, then GATE_ALL_PASS or GATE_FAIL. Env: PY (default: python on PATH).
set -u
W="${1:?worktree}"; shift || true
PY="${PY:-python}"; HERE="$(cd "$(dirname "$0")" && pwd)"
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
cd "$W" || exit 2
bad=0
step() { local name="$1"; shift; local out; out="$("$@" 2>&1)"; local rc=$?; local last
  last="$(printf '%s\n' "$out" | grep -E "$TOKEN" | tail -1)"
  if [ $rc -eq 0 ] && [ -n "$last" ]; then printf 'PASS  %-30s %s\n' "$name" "${last:0:100}"
  else printf 'FAIL  %-30s rc=%s\n' "$name" "$rc"; printf '%s\n' "$out" | tail -20; bad=$((bad+1)); fi; }
TOKEN='PIN AUDIT: CLEAN';                        step "pin audit"          "$PY" "$HERE/pin_audit.py" "$W"
TOKEN='REGISTRY_COUNTS_OK';                      step "registry counts"    "$PY" tools/check_registry_counts.py
TOKEN='CONTRACT_PINS_OK';                        step "contract pins"      "$PY" -m mod_editor.games pins --check
for g in $(ls -d mod_editor/games/*/game.json | awk -F/ '{print $3}'); do
  TOKEN='FRAGMENTS_OK';                          step "fragments $g"       "$PY" -m mod_editor.games fragments "$g" --check
  TOKEN='conformance checks passed';             step "conformance $g"     "$PY" -m mod_editor.games conformance --game "$g"
  [ -f "mod_editor/games/$g/validators.json" ] && { TOKEN='_VALIDATION_PASS'; step "validators $g" "$PY" tools/validate_game_lane.py --game "$g" --all; }
done
if [ "${1:-}" != "--no-release" ]; then
  ST="$(mktemp -d "${TMPDIR:-/tmp}/stage-gate.XXXXXX")/stage"
  TOKEN='staged';                                step "stage_release"      "$PY" packaging/stage_release.py packaging/release-allowlist.txt "$ST" "$W"
  TOKEN='^2K5_MOD_STUDIO_RELEASE_PASS';          step "release check"      "$PY" packaging/check_2k5_mod_studio_release.py "$ST"
  TOKEN='^2K5_MOD_STUDIO_RUNTIME_CLOSURE_PASS';  step "runtime closure"    "$PY" "$ST/packaging/check_2k5_mod_studio_runtime.py"
  rm -rf "$(dirname "$ST")"
fi
[ $bad -eq 0 ] && echo "GATE_ALL_PASS head=$(git rev-parse --short HEAD)" || { echo "GATE_FAIL ($bad)"; exit 1; }
