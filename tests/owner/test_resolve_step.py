"""The conflict resolver's rules, each pinned to the integration that paid for it."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("resolve_step", ROOT / "tools/owner/integration/resolve_step.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


def conflict(ours: str, theirs: str) -> str:
    return f"<<<<<<< HEAD\n{ours}=======\n{theirs}>>>>>>> theirs\n"


class HunkUnionTests(unittest.TestCase):
    def test_a_digit_only_difference_keeps_ours_for_the_count_reset(self) -> None:
        text, n = rs.hunk_union(conflict("registry has 125 rows\n", "registry has 120 rows\n"))
        self.assertEqual((text, n), ("registry has 125 rows\n", 1))

    def test_other_hunks_union_ours_then_theirs_without_repeats(self) -> None:
        text, _ = rs.hunk_union(conflict("a\nshared\n", "shared\nb\n"))
        self.assertEqual(text, "a\nshared\nb\n")


class SurfaceGamesUnionTests(unittest.TestCase):
    def test_both_sides_widening_by_the_same_length_keeps_both_games(self) -> None:
        # 2026-09-06: NCAA 09 and MVP 2005 each appended one game to the same five coverage lines; the
        # old rule kept "the widest" and silently dropped one side when the two were the same length.
        text, _ = rs.hunk_union(conflict(
            'SURFACE_GAMES["colors"] = _ESTABLISHED_GAMES + ("madden09_ps2",) + ("ncaa09_ps2",)\n',
            'SURFACE_GAMES["colors"] = _ESTABLISHED_GAMES + ("madden09_ps2",) + ("mvp05_ps2",)\n'))
        text, folded = rs.union_surface_games(text)
        self.assertEqual(folded, 1)
        self.assertEqual(text, 'SURFACE_GAMES["colors"] = _ESTABLISHED_GAMES + ("madden09_ps2",) + ("ncaa09_ps2",) + ("mvp05_ps2",)\n')

    def test_a_key_widened_on_one_side_only_is_left_alone(self) -> None:
        line = 'SURFACE_GAMES["saves"] = _ESTABLISHED_GAMES + ("ncaa09_ps2",)\n'
        text, folded = rs.union_surface_games("x = 1\n" + line)
        self.assertEqual((text, folded), ("x = 1\n" + line, 0))


class AllowlistTests(unittest.TestCase):
    def test_exact_duplicates_across_the_two_sides_are_dropped_once(self) -> None:
        note, text = rs.merge_allowlist("# head\ntools/a.py\n" + conflict("tools/b.py\n", "tools/b.py\ntools/c.py\n"))
        self.assertEqual(note, "entries=3 dropped=1")
        self.assertEqual(text.strip().splitlines(), ["# head", "tools/a.py", "tools/b.py", "tools/c.py"])


class CountRuleTests(unittest.TestCase):
    def test_deferred_means_names_no_validator_not_classification(self) -> None:
        rows = [{"id": "a", "validation_command": "bash x.sh", "classification": "unknown"},
                {"id": "b", "validation_command": None, "classification": "read-only-mapped"}]
        self.assertEqual(rs.deferred_ids(rows), ["b"])


if __name__ == "__main__":
    unittest.main()
