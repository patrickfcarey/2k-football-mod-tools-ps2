"""The module-readiness measurer: refusal grouping, sampling, the per-container passes, the cache
byte-compare, the schema comparison and the two rendered pages -- on synthetic bytes only.  Nothing
here reads a disc or a retail file."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _candidate in (ROOT, ROOT / "tools", ROOT / "tools" / "owner"):   # owner first: the tool lives in tools/owner
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

import ea_module_readiness as readiness  # noqa: E402
import ea_disc_map as mapper  # noqa: E402
from mod_editor.games.contract import Refusal  # noqa: E402
from mod_editor.games._formats import ea_big, ea_shps, ea_tdb, ea_terf  # noqa: E402
from mod_editor.games.madden09_ps2 import containers as m09  # noqa: E402


def _database() -> bytes:
    return ea_tdb.recompute_crcs(readiness._synthetic_tdb_member())


class RefusalGroupingTests(unittest.TestCase):
    def test_numbers_and_quoted_bytes_are_blanked_so_instances_group(self) -> None:
        one = readiness.refusal_class("member 12 runs from 640 for 96 byte(s), past the end")
        two = readiness.refusal_class("member 913 runs from 40,960 for 8 byte(s), past the end")
        self.assertEqual(one, two)
        self.assertIn("#", one)
        self.assertEqual(readiness.refusal_class("starts with b'QL01', not b'TERF'"),
                         readiness.refusal_class("starts with b'BIGF', not b'TERF'"))

    def test_the_ledger_keeps_one_row_per_reader_and_class(self) -> None:
        ledger = readiness.Ledger()
        ledger.add("ea_terf", "A.DAT", ValueError("member 1 is short"))
        ledger.add("ea_terf", "B.DAT", ValueError("member 9 is short"))
        ledger.add("ea_tdb", "A.DAT", ValueError("member 1 is short"))
        rows = ledger.as_list()
        self.assertEqual(len(rows), 2, rows)
        self.assertEqual(rows[0]["count"], 2)
        self.assertEqual(rows[0]["where"], ["A.DAT", "B.DAT"])
        self.assertEqual(ledger.total(), 3)

    def test_the_example_keeps_the_readers_own_sentence(self) -> None:
        ledger = readiness.Ledger()
        ledger.add("ea_tdb", "X", Refusal("this database declares 7 table(s)"))
        self.assertEqual(ledger.as_list()[0]["example"], "this database declares 7 table(s)")
        self.assertEqual(ledger.as_list()[0]["type"], "Refusal")


class SamplingTests(unittest.TestCase):
    def test_a_sample_is_spread_across_the_run_not_taken_from_its_head(self) -> None:
        self.assertEqual(readiness._evenly(list(range(100)), 5), [0, 20, 40, 60, 80])

    def test_a_short_run_and_no_ceiling_both_give_every_member(self) -> None:
        self.assertEqual(readiness._evenly([3, 4, 5], 9), [3, 4, 5])
        self.assertEqual(readiness._evenly([3, 4, 5], None), [3, 4, 5])
        self.assertEqual(readiness._evenly([], 4), [])


class PercentageTests(unittest.TestCase):
    def test_a_shortfall_never_rounds_up_to_a_hundred(self) -> None:
        self.assertEqual(readiness._pct(6268, 6270), 99.9)
        self.assertEqual(readiness._pct(6270, 6270), 100.0)
        self.assertEqual(readiness._pct(0, 10), 0.0)
        self.assertIsNone(readiness._pct(0, 0))


class ContainerPassTests(unittest.TestCase):
    def test_a_non_container_refuses_with_the_readers_own_sentence(self) -> None:
        with self.assertRaises(Refusal) as caught:
            readiness.measure_container(b"NOPE" + bytes(60), "NOPE.DAT",
                                        readiness.Ledger(), readiness._new_tally())
        self.assertIn("not an EA TERF container", str(caught.exception))

    def test_a_member_under_an_unimplemented_codec_is_refused_not_counted_as_read(self) -> None:
        good = ea_terf.build_terf([b"MMAP" + bytes(60), b"a plain ascii member for the test." + bytes(1)],
                                  chunk="COMP")
        comp = ea_terf.parse_terf(good).chunk("COMP")
        assert comp is not None
        hostile = bytearray(good)
        struct.pack_into("<I", hostile, comp.offset + ea_terf.CHUNK_HEADER_SIZE, ea_terf.CODEC_LZM1)
        ledger = readiness.Ledger()
        row = readiness.measure_container(bytes(hostile), "H.DAT", ledger, readiness._new_tally())
        self.assertEqual((row["members_head_decoded"], row["members_refused"]), (1, 1))
        self.assertTrue(any("codec" in r["sentence_class"] for r in ledger.as_list()), ledger.as_list())

    def test_the_deep_passes_are_skipped_when_asked(self) -> None:
        container = ea_terf.build_terf([_database()], chunk="DATA")
        tally = readiness._new_tally()
        row = readiness.measure_container(container, "DB.DAT", readiness.Ledger(), tally, deep=False)
        self.assertEqual(row["formats"], {"TDB": 1})
        self.assertNotIn("tdb", row)
        self.assertEqual(tally["tdb_parsed"], 0)

    def test_the_tdb_pass_counts_tables_fields_and_crc_sites(self) -> None:
        container = ea_terf.build_terf([_database()], chunk="DATA")
        tally = readiness._new_tally()
        row = readiness.measure_container(container, "DB.DAT", readiness.Ledger(), tally)
        self.assertEqual(row["tdb"]["parsed"], 1)
        self.assertEqual(row["tdb"]["tables"], 2)
        self.assertEqual(row["tdb"]["crc_sites"], row["tdb"]["crc_matched"])
        self.assertGreater(row["tdb"]["crc_sites"], 0)
        self.assertIn("PLAY", tally["schemas"])


class DiscTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.work = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _measure(self, image: bytes, name: str = "disc.iso") -> dict:
        path = self.work / name
        path.write_bytes(image)
        return readiness.measure_disc(path, label=name, mmap_sample=None, schl_sample=None)

    def test_a_clean_synthetic_disc_reads_end_to_end(self) -> None:
        database = _database()
        record = self._measure(m09.build_synthetic_disc(tdb_members=[database, database],
                                                        stream_database=database))
        counts = record["counts"]
        self.assertEqual(counts["containers"], {"total": 2, "works": 2, "refused": 0})
        self.assertEqual(counts["members"]["refused"], 0)
        self.assertEqual(counts["tdb"]["works"], 3)
        self.assertEqual(counts["mmap"]["works"], 3)
        self.assertEqual(counts["crc_sites"]["works"], counts["crc_sites"]["total"])
        self.assertEqual(counts["caches"]["identical"], counts["caches"]["copies"])
        self.assertEqual(counts["caches"]["differing"], 0)

    def test_a_stale_cache_copy_is_caught_by_the_byte_compare(self) -> None:
        database = _database()
        image = bytearray(m09.build_synthetic_disc(tdb_members=[database], stream_database=database))
        marker = image.find(b"QL01")
        self.assertGreater(marker, 0)
        image[marker + 400] ^= 0xFF
        counts = self._measure(bytes(image), "stale.iso")["counts"]
        self.assertGreater(counts["caches"]["differing"] + counts["caches"]["unresolved"], 0)

    def test_a_flipped_record_byte_is_caught_by_the_crc_row(self) -> None:
        database = _database()
        tampered = bytearray(database)
        tampered[ea_tdb.parse_tdb(database).record_offset("TEAM", 0)] ^= 0xFF
        record = self._measure(m09.build_synthetic_disc(tdb_members=[bytes(tampered)]), "bad.iso")
        self.assertGreater(record["counts"]["crc_sites"]["refused"], 0)
        self.assertTrue(any(row["reader"] == "ea_tdb.verify_crcs" for row in record["refusals"]))

    def test_the_mappers_wide_disc_exercises_schl_text_and_nested_containers(self) -> None:
        image, _payloads = mapper.build_synthetic_disc()
        counts = self._measure(image, "wide.iso")["counts"]
        self.assertGreaterEqual(counts["schl"]["headers_parsed"], 1)
        self.assertGreaterEqual(counts["formats"].get("TEXT", 0), 1)
        self.assertGreaterEqual(counts["formats"].get("TERF", 0), 1)
        self.assertGreaterEqual(counts["tdb"]["works"], 2)

    def test_nothing_from_a_members_payload_reaches_the_record(self) -> None:
        """The record is names, counts and schema.  A member's own bytes are not in it."""
        image, _payloads = mapper.build_synthetic_disc()
        record = self._measure(image, "leak.iso")
        blob = json.dumps(record)
        self.assertNotIn(mapper.TEXT_MEMBER.decode("ascii")[:32], blob)
        self.assertNotIn("Headline", blob)


class SchemaComparisonTests(unittest.TestCase):
    BASE = {"count": 1, "field_count": 2, "record_bytes": 6,
            "fields": [["TGID", "uint", 8, 0], ["TDNA", "string", 32, 8]]}

    def test_a_table_compared_with_itself_is_identical(self) -> None:
        self.assertEqual(readiness.compare_table(self.BASE, self.BASE)["verdict"], "identical")

    def test_a_widened_field_is_named_with_both_widths(self) -> None:
        wider = dict(self.BASE, fields=[["TGID", "uint", 9, 0], ["TDNA", "string", 32, 9]])
        row = readiness.compare_table(wider, self.BASE)
        self.assertIn("width", row["verdict"])
        self.assertEqual(row["width_differences"], [["TGID", 9, 8]])

    def test_a_moved_field_of_the_same_width_is_reported_as_an_offset_difference(self) -> None:
        moved = dict(self.BASE, fields=[["TGID", "uint", 8, 8], ["TDNA", "string", 32, 40]])
        row = readiness.compare_table(moved, self.BASE)
        self.assertIn("bit offset", row["verdict"])
        self.assertEqual(row["offset_differences"], 2)

    def test_an_absent_table_says_which_side_lacks_it(self) -> None:
        self.assertEqual(readiness.compare_table(None, self.BASE)["verdict"], "absent here")
        self.assertEqual(readiness.compare_table(self.BASE, None)["verdict"], "absent from the control")
        self.assertEqual(readiness.compare_table(None, None)["verdict"], "absent from both")

    def test_the_dominant_shape_is_the_one_most_databases_carry(self) -> None:
        shapes = {"a": {"count": 3, "field_count": 2}, "b": {"count": 9, "field_count": 5}}
        self.assertEqual(readiness.dominant_shape(shapes)["field_count"], 5)
        self.assertIsNone(readiness.dominant_shape({}))


class RenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        path = Path(self._tmp.name) / "disc.iso"
        database = _database()
        path.write_bytes(m09.build_synthetic_disc(tdb_members=[database], stream_database=database))
        self.record = readiness.measure_disc(path, label="Synthetic (USA)", mmap_sample=None, schl_sample=None)

    def test_the_page_carries_the_readiness_table_and_its_definitions(self) -> None:
        page = readiness.render_page(self.record, today="1970-01-01")
        self.assertIn("## Readiness — what runs unchanged", page)
        self.assertIn("| containers | `ea_terf.parse_terf` |", page)
        self.assertIn("| cache copies |", page)
        self.assertIn("What a module for this disc would need", page)
        for row in readiness.PAGE_ROWS:
            self.assertIn("| %s |" % row, page)

    def test_the_page_states_a_schema_verdict_only_when_a_control_is_given(self) -> None:
        self.assertIn("No control was given", readiness.render_page(self.record, today="1970-01-01"))
        self.assertIn("| `PLAY` |", readiness.render_page(self.record, self.record, today="1970-01-01"))

    def test_the_summary_puts_one_row_per_disc(self) -> None:
        table = readiness.render_summary([self.record, self.record])
        self.assertEqual(table.count("Synthetic (USA)"), 2)
        self.assertIn("MMAP", table)


class SelftestTests(unittest.TestCase):
    def test_the_selftest_passes_as_a_subprocess(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "owner" / "ea_module_readiness.py"), "--selftest"],
            capture_output=True, text=True, timeout=900, cwd=str(ROOT))
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("EA_MODULE_READINESS_SELFTEST_PASS", completed.stdout)



# --------------------------------------------------------------------------
# The EA BIG family
# --------------------------------------------------------------------------
def _archive(extra=()) -> bytes:
    """A BIGF archive holding one bank stored, one packed, a database and text."""
    bank = readiness._synthetic_shps_bank()
    return ea_big.build_big([
        ("art/one.ssh", bank),
        ("art/packed.ssh", mapper._refpack_literal(bank)),
        ("data/six.db", _database()),
        ("notes.txt", b"a plain ascii entry for this test, sixty-four bytes long."),
        ("hole/", b""),
    ] + list(extra))


class BigArchiveTests(unittest.TestCase):
    def _measure(self, blob: bytes, name: str = "Z.BIG", available: "int | None" = None):
        ledger = readiness.Ledger()
        tally = readiness._new_tally()
        archive = ea_big.parse_big(blob, name=name)
        row = readiness.measure_archive(archive, name, ledger, tally, head=blob[:16],
                                        available=len(blob) if available is None else available)
        return row, ledger, tally

    def test_every_entry_is_classified_after_refpack_not_before(self) -> None:
        row, _ledger, tally = self._measure(_archive())
        self.assertEqual(row["entries_refused"], 0)
        self.assertEqual(row["formats"].get("SHPS"), 2)
        self.assertEqual(row["formats"].get("TDB"), 1)
        self.assertEqual(row["formats"].get(ea_big.FORMAT_EMPTY), 1)
        self.assertEqual((row["refpack_entries"], row["refpack_unpacked"]), (1, 1))
        self.assertEqual(tally["big_entries"], 5)

    def test_the_size_word_is_named_even_when_the_file_is_sector_padded(self) -> None:
        blob = _archive()
        padded = blob + bytes(2048 - len(blob) % 2048)
        row, _ledger, _tally = self._measure(padded, available=len(padded))
        self.assertEqual(row["size_field"], "little")
        self.assertIn("declares", row["size_note"])

    def test_an_entry_that_points_outside_the_archive_is_refused_with_a_sentence(self) -> None:
        blob = bytearray(ea_big.build_big([("a.bin", b"x" * 64)]))
        struct.pack_into(">I", blob, ea_big.BIG_HEADER_SIZE, 1 << 20)   # the row's offset word
        row, ledger, _tally = self._measure(bytes(blob), "BAD.BIG")
        self.assertEqual(row["entries_refused"], 1)
        self.assertEqual(row["entries_classified"], 0)
        self.assertTrue(any("past the" in r["sentence_class"] for r in ledger.as_list()),
                        ledger.as_list())
        self.assertEqual(row["layout_notes"][0][:8], "entry 0 ")

    def test_big4_and_the_c0fb_spelling_are_refused_by_name(self) -> None:
        for magic, wanted in ((b"BIG4", "BIG4"), (ea_big.C0FB_HEAD, "C0 FB")):
            with self.assertRaises(Refusal) as caught:
                ea_big.parse_big(magic.ljust(4, b"\x00") + bytes(60), name="A.BIG")
            self.assertIn(wanted, str(caught.exception))

    def test_a_csv_table_is_measured_by_its_shape_and_none_of_its_bytes_escape(self) -> None:
        header = b"Age,Name,Team,Bats,Throws\n0 first row of a table nobody may copy\n"
        ledger, tally = readiness.Ledger(), readiness._new_tally()
        readiness._probe_data_table(header, "DATABASE.BIG!attrib.dat", tally, "archive entry")
        probe = tally["data_probes"][0]
        self.assertEqual(probe["format"], "TEXT")
        self.assertEqual(probe["csv_fields"], 5)
        self.assertEqual((probe["magic"], probe["printable"], probe["first_words_le"]), ("", "", []))
        blob = json.dumps({"probes": tally["data_probes"], "magics": dict(tally["data_magics"])})
        self.assertNotIn("Age", blob)
        self.assertNotIn(header[:4].hex(), blob)
        self.assertFalse(ledger.as_list())

    def test_a_database_shaped_entry_name_is_probed_for_its_magic(self) -> None:
        _row, _ledger, tally = self._measure(_archive())
        self.assertEqual(tally["data_tdb"], 1)
        probe = tally["data_probes"][0]
        self.assertTrue(probe["where"].endswith("data/six.db"))
        self.assertTrue(probe["opens_as_tdb"])
        self.assertEqual(probe["magic"], _database()[:4].hex())


class LooseRefpackTests(unittest.TestCase):
    def test_a_loose_refpack_file_unpacks_and_is_classified(self) -> None:
        ledger, tally = readiness.Ledger(), readiness._new_tally()
        row = readiness.measure_loose_refpack(mapper._refpack_literal(b"MMAP" + bytes(60)),
                                              "/FE/XLAY_FE.BIN", ledger, tally)
        self.assertEqual(row["format"], "MMAP")
        self.assertEqual((tally["loose_refpack"], tally["loose_refpack_unpacked"]), (1, 1))

    def test_the_c0fb_spelling_is_a_refusal_and_not_an_empty_read(self) -> None:
        ledger, tally = readiness.Ledger(), readiness._new_tally()
        row = readiness.measure_loose_refpack(ea_big.C0FB_HEAD + bytes(30),
                                              "/FE/XAFEBG.BIN", ledger, tally)
        self.assertEqual(row["format"], ea_big.FORMAT_UNDECODABLE)
        self.assertEqual(tally["loose_refpack_refused"], 1)
        self.assertIn("RefPack", ledger.as_list()[0]["example"])


class ShpsPassTests(unittest.TestCase):
    def _bank(self, **kwargs):
        ledger, tally = readiness.Ledger(), readiness._new_tally()
        out = readiness._new_shps_row(1, 1)
        readiness._measure_one_shps(readiness._synthetic_shps_bank(**kwargs),
                                    "one.ssh", ledger, tally, out)
        return out, ledger, tally

    def test_every_image_is_decoded_and_the_refusals_are_counted_by_block_code(self) -> None:
        out, _ledger, tally = self._bank()
        self.assertEqual((out["parsed"], out["images"]), (1, 4))
        self.assertEqual((out["decoded"], out["image_refused"]), (2, 2))
        self.assertEqual(dict(tally["shps_refused_codes"]), {"0x0e": 1, "0x01": 1})
        self.assertEqual(sorted(tally["shps_decoded_codes"]), ["0x02", "0x05"])

    def test_the_refusal_keeps_the_readers_own_measurement(self) -> None:
        _out, ledger, _tally = self._bank()
        sentences = " ".join(row["example"] for row in ledger.as_list())
        self.assertIn("does not decode", sentences)
        self.assertIn("byte(s) per pixel", sentences)

    def test_a_big_endian_bank_reads_the_same_way(self) -> None:
        out, _ledger, tally = self._bank(big_endian=True)
        self.assertEqual(out["decoded"], 2)
        self.assertEqual(tally["shps_endians"].get("big"), 1)

    def test_a_bank_that_will_not_open_is_refused_not_counted_as_empty(self) -> None:
        ledger, tally = readiness.Ledger(), readiness._new_tally()
        out = readiness._new_shps_row(1, 1)
        readiness._measure_one_shps(b"SHPS" + bytes(12), "bad.ssh", ledger, tally, out)
        self.assertEqual((out["parsed"], out["refused"]), (0, 1))
        self.assertEqual(ledger.as_list()[0]["reader"], "ea_shps.parse")


class BigDiscTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        path = Path(self._tmp.name) / "wide.iso"
        image, _payloads = mapper.build_synthetic_disc()
        path.write_bytes(image)
        self.record = readiness.measure_disc(path, label="Synthetic wide (USA)",
                                             mmap_sample=None, schl_sample=None)

    def test_the_discs_archives_open_and_their_entries_classify(self) -> None:
        counts = self.record["counts"]
        self.assertGreaterEqual(counts["big"]["total"], 3)
        self.assertEqual(counts["big"]["refused"], 0)
        self.assertGreaterEqual(counts["big"]["nested"], 1)
        self.assertEqual(counts["big_entries"]["refused"], 0)
        self.assertGreaterEqual(counts["refpack"]["works"], 1)

    def test_a_big_endian_size_word_is_named_on_a_padded_file(self) -> None:
        self.assertEqual(self.record["counts"]["big"]["size_fields"].get("big"), 1)

    def test_the_archives_image_banks_are_found_and_measured(self) -> None:
        self.assertGreaterEqual(self.record["counts"]["shps"]["banks"], 4)
        self.assertGreaterEqual(self.record["counts"]["shps"]["banks_parsed"], 4)

    def test_the_page_carries_the_big_family_section(self) -> None:
        page = readiness.render_page(self.record, today="1970-01-01")
        self.assertIn("### The EA BIG family", page)
        self.assertIn("| BIG archives | `ea_big.parse_big` |", page)
        self.assertIn("| RefPack streams | `ea_big.refpack_decompress` |", page)
        self.assertIn("| SHPS images | `ea_shps.decode_rgba` |", page)
        self.assertIn("Where this disc keeps its roster and team data", page)

    def test_no_entry_payload_reaches_the_record(self) -> None:
        blob = json.dumps(self.record)
        self.assertNotIn(mapper.TEXT_MEMBER.decode("ascii")[:32], blob)
        self.assertIn("archives", self.record)


class SummaryColumnTests(unittest.TestCase):
    def _record(self, **counts):
        base = {"containers": {"total": 1, "works": 1, "refused": 0},
                "members": {"total": 2, "works": 2, "refused": 0},
                "tdb": {"total": 0, "works": 0, "refused": 0},
                "crc_sites": {"total": 0, "works": 0, "refused": 0},
                "mmap": {"total": 0, "works": 0, "refused": 0},
                "schl": {"total": 0, "works": 0, "refused": 0},
                "bnkl": {"total": 0, "works": 0, "refused": 0},
                "caches": {"total": 0, "works": 0, "copies": 0, "identical": 0,
                           "differing": 0, "unresolved": 0}}
        base.update(counts)
        return {"label": "Disc (USA)", "identity": {"serial": "SLUS-00000"},
                "seconds": 1.0, "counts": base}

    def test_a_record_without_the_big_rows_says_not_measured_not_absent(self) -> None:
        table = readiness.render_summary([self._record()])
        self.assertIn("| BIG |", table.splitlines()[0].replace("BIG", "BIG"))
        self.assertIn(readiness.NOT_MEASURED, table)
        self.assertIn("measured before that row existed", table)

    def test_a_measured_but_empty_family_renders_an_em_dash(self) -> None:
        table = readiness.render_summary([self._record(
            big={"total": 0, "works": 0, "refused": 0},
            big_entries={"total": 0, "works": 0, "refused": 0},
            refpack={"total": 0, "works": 0, "refused": 0},
            shps={"total": 0, "works": 0, "refused": 0})])
        self.assertNotIn(readiness.NOT_MEASURED, table)
        self.assertIn("—", table)

    def test_the_three_new_columns_are_in_the_header(self) -> None:
        header = readiness.render_summary([self._record()]).splitlines()[0]
        for column in ("BIG", "RefPack", "SHPS"):
            self.assertIn("| %s |" % column, header)


if __name__ == "__main__":
    unittest.main()
