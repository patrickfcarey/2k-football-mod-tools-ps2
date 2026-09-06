"""The savestate differ: the savestate reader, the clustering, the isolation ranking, the
transition search, the ELF section attribution, the resident-database scan and the record
decode -- on synthetic bytes only.  Nothing here reads a savestate, a disc or a retail file;
every byte it looks at is built by `sstate_diff._synthetic_pair` or by a test below."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _candidate in (ROOT, ROOT / "tools", ROOT / "tools" / "owner"):   # owner first: the tool lives in tools/owner
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

import sstate_diff as sd  # noqa: E402


class SavestateTests(unittest.TestCase):
    def test_a_zip_shaped_like_a_p2s_reads_back(self) -> None:
        image, _other, _facts = sd._synthetic_pair()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SYNTH (00000000).01.p2s"
            sd._synthetic_savestate(path, image)
            state = sd.Savestate(path)
            self.assertTrue(state.has(sd.EE_MEMORY))
            self.assertEqual(state.ee(), image)
            names = [name for name, _m, _c, _u in state.members()]
            self.assertIn("PCSX2 Savestate Version.id", names)

    def test_a_stored_member_reads_back_too(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.p2s"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("Scratchpad.bin", b"\x11" * 64, zipfile.ZIP_STORED)
            self.assertEqual(sd.Savestate(path).member("Scratchpad.bin"), b"\x11" * 64)

    def test_a_missing_member_refuses_and_lists_what_is_there(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.p2s"
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("GS.bin", b"\x00" * 8)
            with self.assertRaises(sd.SstateError) as caught:
                sd.Savestate(path).member(sd.EE_MEMORY)
            self.assertIn("GS.bin", str(caught.exception))

    def test_a_file_that_is_not_a_zip_refuses_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "not.p2s"
            path.write_bytes(b"this is not a zip")
            with self.assertRaises(sd.SstateError) as caught:
                sd.Savestate(path)
            self.assertIn("not.p2s", str(caught.exception))

    def test_a_member_that_decompresses_to_the_wrong_length_is_called_damaged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.p2s"
            sd._write_zip_member(path, "x.bin", b"\x00" * 4, 99, 0, sd.ZIP_STORED)
            with self.assertRaises(sd.SstateError) as caught:
                sd.Savestate(path).member("x.bin")
            self.assertIn("damaged", str(caught.exception))

    def test_an_unknown_codec_says_to_add_it_here(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.p2s"
            sd._write_zip_member(path, "x.bin", b"\x00" * 4, 4, 0, 12)
            with self.assertRaises(sd.SstateError) as caught:
                sd.Savestate(path).member("x.bin")
            self.assertIn("method 12", str(caught.exception))


class ClusteringTests(unittest.TestCase):
    def test_offsets_within_the_gap_join_and_others_do_not(self) -> None:
        self.assertEqual(sd.cluster([1, 2, 3, 40, 41], gap=4), [(1, 4, 3), (40, 42, 2)])
        self.assertEqual(sd.cluster([1, 2, 3, 40, 41], gap=64), [(1, 42, 5)])
        self.assertEqual(sd.cluster([], gap=8), [])

    def test_a_run_reports_its_span_and_its_differing_count_separately(self) -> None:
        run, = sd.cluster([0, 100], gap=200)
        start, end, differing = run
        self.assertEqual((start, end), (0, 101))
        self.assertEqual(differing, 2)

    def test_a_negative_gap_refuses(self) -> None:
        with self.assertRaises(sd.SstateError):
            sd.cluster([1], gap=-1)

    def test_isolation_separates_a_lone_value_from_a_churning_buffer(self) -> None:
        offsets = [10] + list(range(10_000, 10_400))
        scores = sd.isolation(offsets, window=512)
        self.assertEqual(scores[10], 1)
        self.assertGreater(scores[10_200], 300)

    def test_a_length_mismatch_refuses_rather_than_diffing_a_prefix(self) -> None:
        with self.assertRaises(sd.SstateError) as caught:
            sd.differing_offsets(b"abc", b"ab")
        self.assertIn("same length", str(caught.exception))


class TransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.a, self.b, self.facts = sd._synthetic_pair()

    def test_it_finds_the_planted_field_at_its_planted_bit(self) -> None:
        hits = sd.find_transition(self.a, self.b, 54, 56, 7)
        self.assertIn((self.facts["answer_byte"], self.facts["answer_bit"]), hits)

    def test_it_names_each_site_once(self) -> None:
        hits = sd.find_transition(self.a, self.b, 54, 56, 7)
        self.assertEqual(len(hits), len(set(hits)))

    def test_a_byte_aligned_change_is_found_at_bit_zero(self) -> None:
        a = bytearray(64)
        b = bytearray(64)
        a[32] = 7
        b[32] = 9
        hits = sd.find_transition(bytes(a), bytes(b), 7, 9, 8)
        self.assertIn((32, 0), hits)

    def test_a_field_that_straddles_a_byte_boundary_is_found(self) -> None:
        a = bytearray(64)
        b = bytearray(64)
        value_a = 54 << 6
        value_b = 56 << 6
        a[16:18] = value_a.to_bytes(2, "little")
        b[16:18] = value_b.to_bytes(2, "little")
        self.assertIn((16, 6), sd.find_transition(bytes(a), bytes(b), 54, 56, 7))

    def test_a_transition_that_did_not_happen_is_not_found_at_the_planted_site(self) -> None:
        hits = sd.find_transition(self.a, self.b, 12, 13, 7)
        self.assertNotIn((self.facts["answer_byte"], self.facts["answer_bit"]), hits)

    def test_an_unchanged_value_refuses_with_a_sentence_naming_the_fix(self) -> None:
        with self.assertRaises(sd.SstateError) as caught:
            sd.find_transition(self.a, self.b, 54, 54, 7)
        self.assertIn("did not change", str(caught.exception))

    def test_a_value_too_wide_for_the_field_refuses(self) -> None:
        with self.assertRaises(sd.SstateError) as caught:
            sd.find_transition(self.a, self.b, 54, 200, 7)
        self.assertIn("do not both fit", str(caught.exception))

    def test_an_impossible_width_refuses(self) -> None:
        with self.assertRaises(sd.SstateError):
            sd.find_transition(self.a, self.b, 1, 2, 64)


class ElfSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sections = sd.ElfSections(sd._synthetic_elf())

    def test_the_named_sections_come_back_in_address_order(self) -> None:
        self.assertEqual([s[0] for s in self.sections.sections], [".text", ".data", ".bss"])

    def test_an_initialised_section_has_a_file_offset(self) -> None:
        self.assertEqual(self.sections.file_offset(0x00200004), 0x1004)

    def test_a_nobits_section_has_none_because_the_disc_has_no_image_of_it(self) -> None:
        self.assertIsNotNone(self.sections.at(0x00300004))
        self.assertIsNone(self.sections.file_offset(0x00300004))

    def test_an_address_in_no_section_is_reported_as_outside(self) -> None:
        self.assertIsNone(self.sections.at(0x00900000))

    def test_a_file_that_is_not_an_elf_refuses(self) -> None:
        with self.assertRaises(sd.SstateError) as caught:
            sd.ElfSections(b"MZ" + b"\x00" * 64)
        self.assertIn("ELF magic", str(caught.exception))


class DatabaseAndRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.a, self.b, self.facts = sd._synthetic_pair()
        found = sd.scan_tdb(self.a)
        self.db = [d for d in found if d["offset"] == self.facts["tdb_at"]][0]
        self.header = sd.read_table_header(self.a, self.db["directory_end"])
        self.fields = sd.read_field_directory(
            self.a, self.header["fields_offset"], self.header["field_count"])

    def test_the_planted_database_is_found_with_its_table_named(self) -> None:
        self.assertEqual(self.db["tables"], ["PLAY"])
        self.assertEqual(self.db["table_count"], 1)

    def test_a_table_header_reads_back_its_stride_and_field_count(self) -> None:
        self.assertEqual(self.header["record_bytes"], self.facts["stride"])
        self.assertEqual(self.header["field_count"], len(self.facts["fields"]))
        self.assertEqual(self.header["records_offset"],
                         self.header["fields_offset"] + self.header["field_count"] * 16)

    def test_a_field_directory_reads_back_exactly(self) -> None:
        self.assertEqual(self.fields, self.facts["fields"])

    def test_a_bare_field_directory_is_found_without_a_database_header(self) -> None:
        window = (self.header["fields_offset"] - 64,
                  self.header["fields_offset"] + self.header["field_count"] * 16 + 64)
        self.assertEqual(sd.find_field_directory(self.a, *window, min_fields=4),
                         (self.header["fields_offset"], self.header["field_count"]))

    def test_a_run_shorter_than_min_fields_is_not_reported(self) -> None:
        window = (self.header["fields_offset"] - 64,
                  self.header["fields_offset"] + self.header["field_count"] * 16 + 64)
        self.assertIsNone(sd.find_field_directory(
            self.a, *window, min_fields=self.header["field_count"] + 1))

    def test_a_record_decodes_to_the_values_that_were_packed_into_it(self) -> None:
        at = self.facts["array_at"] + self.facts["target_row"] * self.facts["stride"]
        before = sd.decode_record(self.a, at, self.facts["stride"], self.fields)
        self.assertEqual(before["PJEN"], 54)
        self.assertEqual(before["POVR"], 98)
        self.assertEqual(before["PPOS"], 14)
        self.assertEqual(before["PHGT"], 76)
        self.assertEqual(before["PWGT"], 94)
        self.assertEqual(before["TGID"], 1)

    def test_a_signed_field_sign_extends_and_an_unsigned_one_does_not(self) -> None:
        at = self.facts["array_at"]
        values = sd.decode_record(self.a, at, self.facts["stride"], self.fields)
        self.assertEqual(values["PLHY"], -3)
        self.assertGreaterEqual(values["PHGT"], 0)

    def test_exactly_one_field_changed_between_the_two_states(self) -> None:
        at = self.facts["array_at"] + self.facts["target_row"] * self.facts["stride"]
        before = sd.decode_record(self.a, at, self.facts["stride"], self.fields)
        after = sd.decode_record(self.b, at, self.facts["stride"], self.fields)
        self.assertEqual([k for k in before if before[k] != after[k]], ["PJEN"])
        self.assertEqual(after["PJEN"], 56)

    def test_only_the_named_fields_come_back_when_names_are_given(self) -> None:
        at = self.facts["array_at"]
        values = sd.decode_record(self.a, at, self.facts["stride"], self.fields, ["POVR"])
        self.assertEqual(list(values), ["POVR"])

    def test_a_record_past_the_end_refuses(self) -> None:
        with self.assertRaises(sd.SstateError):
            sd.decode_record(self.a, len(self.a) - 4, self.facts["stride"], self.fields)

    def test_an_absurd_table_count_is_not_taken_for_a_database(self) -> None:
        blob = bytearray(256)
        blob[0:4] = sd.TDB_MAGIC_V8
        struct.pack_into("<I", blob, 0x10, 1_000_000)
        self.assertEqual(sd.scan_tdb(bytes(blob)), [])


class ExtractGuardTests(unittest.TestCase):
    def test_extract_refuses_to_write_inside_a_git_checkout(self) -> None:
        image, _b, _f = sd._synthetic_pair()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            state = root / "s.p2s"
            sd._synthetic_savestate(state, image)
            out = root / "sub" / "dir"
            args = type("A", (), {"a": str(state), "member": sd.EE_MEMORY, "out": str(out)})()
            with self.assertRaises(sd.SstateError) as caught:
                sd.cmd_extract(args)
            self.assertIn("scratch directory", str(caught.exception))
            self.assertFalse(out.exists())


class SelftestTests(unittest.TestCase):
    def test_the_tools_own_selftest_passes_and_prints_its_token(self) -> None:
        done = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "owner" / "sstate_diff.py"), "--selftest"],
            capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("SSTATE_DIFF_SELFTEST_PASS", done.stdout)


class RetailFreeTests(unittest.TestCase):
    def test_the_measured_json_holds_no_payload_shaped_keys(self) -> None:
        path = ROOT / "docs" / "owner" / "scoping" / "measured" / "savestate-diffs.json"
        if not path.is_file():
            self.skipTest("the measured file is not in this tree")
        data = json.loads(path.read_text(encoding="utf-8"))
        text = json.dumps(data)
        for banned in ("PFNA", "PLNA", "bytes_hex", "hexdump", "payload"):
            self.assertNotIn(banned, text)
        self.assertEqual(len(data["inventory"]), 15)


if __name__ == "__main__":
    unittest.main()
