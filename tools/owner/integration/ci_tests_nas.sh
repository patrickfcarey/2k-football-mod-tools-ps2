#!/bin/bash
# Parallel mirror of ci.yml's tests loop for the NAS turret workspace. Usage: ci_tests_nas.sh <repo> <workers>
repo="${1:?repo}"; workers="${2:-24}"; PY=/turret/builds/2k5/venv311/bin/python
export QT_QPA_PLATFORM=offscreen
cd "$repo" || exit 2
[ -e .git ] || mkdir .git   # self_update detects a checkout by .git; an rsynced tree without one tests as a tarball
LOGS="$repo/.tests-parallel-logs"; rm -rf "$LOGS"; mkdir -p "$LOGS"
lean=0; [ -f reports/assets/nfl2k5_all_txtr_inventory_v2.json ] || lean=1
echo "lean_checkout=$lean head=$(git rev-parse --short HEAD) workers=$workers host=$(hostname) $(date -u +%FT%TZ)"
run_one() {
  f="$1"; name=$(basename "$f"); out="$LOGS/$name.log"
  if [ "$LEAN" -eq 1 ]; then case "$name" in
    test_2k5_uniform_equipment_export.py|test_all_textures_workspace.py|test_apf_logo_surface_ownership.py|test_apf_product_findings.py|test_menu_modes.py|test_nfl2k5_crib_geometry_writer.py|test_nfl2k5_crib.py|test_nfl2k5_face_shield_registry.py|test_nfl2k5_stock_midfield_logo_boundary.py|test_no_capability_is_invisible.py|test_presentation_inspection.py|test_uniform_sharing.py) echo "SKIP  $name"; return;; esac; fi
  if [ "$name" = "test_apf_studio_installer.py" ]; then env -u PYTHONPATH timeout -k 30 900 "$PY" "$f" >"$out" 2>&1; rc=$?
  else PYTHONPATH="$REPO" timeout -k 30 900 "$PY" "$f" >"$out" 2>&1; rc=$?; fi
  n=$(grep -oE 'Ran [0-9]+ test' "$out" | grep -oE '[0-9]+' | tail -1)
  if [ "$rc" -eq 0 ]; then echo "PASS  $name  (${n:-?} tests)"; else echo "FAIL  $name  (rc=$rc)"; fi
}
export -f run_one; export LEAN=$lean REPO="$repo" PY LOGS
ls tests/mod_editor/test_*.py | xargs -P "$workers" -I{} bash -c 'run_one "$@"' _ {} | tee "$LOGS/results.txt" | grep -E "^FAIL"
p=$(grep -c "^PASS" "$LOGS/results.txt"); f=$(grep -c "^FAIL" "$LOGS/results.txt"); s=$(grep -c "^SKIP" "$LOGS/results.txt")
t=$(grep -oE '\([0-9]+ tests\)' "$LOGS/results.txt" | grep -oE '[0-9]+' | awk '{s+=$1} END {print s+0}')
echo "SUMMARY: files=$((p+f+s)) passed=$p failed=$f skipped=$s tests=$t  $(date -u +%FT%TZ)"
[ "$f" -ne 0 ] && { echo "FAILED FILES: $(grep '^FAIL' "$LOGS/results.txt" | awk '{print $2}' | tr '\n' ' ')"; exit 1; }
echo "ALL TEST FILES PASSED"
