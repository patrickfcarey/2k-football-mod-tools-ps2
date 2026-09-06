"""The one-disc-index PROTOTYPE: its identifier, its walk and its regeneration.

On synthetic bytes only.  Nothing here reads a disc, a retail file or a dump.
The two misidentifications the specification is built around -- ``CPTH`` read
as ``HTPC``, and multi-section RenderWare refused by a single-section rule --
each get a test that fails if the fix regresses.
"""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.owner.prototypes.disc_index import identify, map_md, regen, walk  # noqa: E402


def rw_section(section_id: int, body: bytes, version: int = 0x0401FFFF) -> bytes:
    return struct.pack("<3I", section_id, len(body), version) + body


class TagTextTests(unittest.TestCase):
    """Correction 1: a four-byte tag is text, forward, never a hex word."""

    def test_a_printable_tag_reads_forward(self) -> None:
        self.assertEqual(identify.tag_text(b"CPTH...."), "CPTH")
        self.assertEqual(identify.tag_text(b"EKAB"), "EKAB")

    def test_the_hex_of_the_same_bytes_spells_the_tag_backwards_as_a_word(self) -> None:
        head = b"CPTH"
        self.assertEqual(head.hex(), "43505448")
        as_a_little_endian_word = struct.unpack("<I", head)[0]
        self.assertEqual(as_a_little_endian_word.to_bytes(4, "big"), b"HTPC",
                         "this is exactly the reading that put HTPC in the scoping study")
        self.assertEqual(identify.tag_text(head), "CPTH")

    def test_an_unprintable_head_has_no_tag_but_still_has_a_magic(self) -> None:
        found = identify.identify(b"\x10\x00\x00\x00" + bytes(60), 64)
        self.assertIsNone(found.tag)
        self.assertEqual(found.magic, "10000000")


class CpthTests(unittest.TestCase):
    def _member(self, records: int, word1: int = 7) -> bytes:
        return struct.pack("<4sIII", b"CPTH", word1, records, 0) + bytes(records * 32)

    def test_the_arithmetic_earns_the_identity_and_is_recorded(self) -> None:
        payload = self._member(3)
        found = identify.identify(payload[:identify.HEAD_BYTES], len(payload))
        self.assertEqual((found.format, found.tag), ("CPTH", "CPTH"))
        self.assertEqual(found.rule, "16 + records * 32 == the member")
        self.assertEqual(found.shape["records"], 3)
        self.assertEqual(found.shape["header_word1"], 7)

    def test_a_tag_whose_arithmetic_fails_is_a_question_not_a_claim(self) -> None:
        payload = self._member(3)[:-1]
        found = identify.identify(payload[:identify.HEAD_BYTES], len(payload))
        self.assertEqual(found.format, "CPTH?")
        self.assertIn("!=", found.rule)


class RenderWareWalkTests(unittest.TestCase):
    """Correction 2: a stream is one *or more* top-level sections."""

    def test_one_section_is_accepted_as_it_always_was(self) -> None:
        payload = rw_section(identify.RW_TEXTURE_DICTIONARY, bytes(32))
        found = identify.identify(payload[:identify.HEAD_BYTES], len(payload))
        self.assertEqual(found.format, "RW-TXD")
        self.assertTrue(found.shape["one_section_accounts_for_the_file"])

    def test_clump_then_extension_is_accepted_where_the_old_rule_refused(self) -> None:
        payload = (rw_section(identify.RW_CLUMP, bytes(48))
                   + rw_section(identify.RW_EXTENSION, bytes(16)))

        def read(offset: int, length: int) -> bytes:
            return payload[offset:offset + length]

        one_section_rule = struct.unpack_from("<I", payload, 4)[0] + 12 == len(payload)
        self.assertFalse(one_section_rule, "the mapper's rule is the thing under test")
        found = identify.identify(payload[:identify.HEAD_BYTES], len(payload), read=read)
        self.assertEqual(found.format, "RW-CLUMP")
        self.assertEqual(found.shape["top_level_sequence"], "0x10 0x3")
        self.assertTrue(found.shape["walk_consumes_the_member"])
        self.assertEqual(found.rule, "top-level section walk consumes the member exactly")

    def test_a_renderware_id_whose_walk_does_not_consume_is_marked_with_a_question(self) -> None:
        payload = rw_section(identify.RW_CLUMP, bytes(48)) + bytes(7)

        def read(offset: int, length: int) -> bytes:
            return payload[offset:offset + length]

        found = identify.identify(payload[:identify.HEAD_BYTES], len(payload), read=read)
        self.assertEqual(found.format, "RW-CLUMP?")
        self.assertFalse(found.shape["walk_consumes_the_member"])

    def test_the_walk_stops_where_rw_txd_walk_stops(self) -> None:
        """A section whose declared body runs past the end is not counted."""
        payload = rw_section(identify.RW_CLUMP, bytes(16)) + struct.pack("<3I", 3, 9999, 0)
        found = identify.renderware_walk(payload[:12], len(payload),
                                         lambda o, n: payload[o:o + n])
        self.assertEqual(found["top_level_sequence"], "0x10")
        self.assertFalse(found["walk_consumes_the_member"])


class ReversedMagicTests(unittest.TestCase):
    def test_a_tag_stored_as_a_word_is_named_once_with_its_spelling(self) -> None:
        found = identify.identify(b" KAP" + bytes(60), 64)
        self.assertEqual(found.format, "MidwayPAK")
        self.assertIn("spells 'PAK '", found.rule)


class BoundedReadTests(unittest.TestCase):
    def test_the_identifier_never_asks_for_more_than_a_head_and_section_headers(self) -> None:
        payload = (rw_section(identify.RW_CLUMP, bytes(4096))
                   + rw_section(identify.RW_EXTENSION, bytes(4096)))
        asked = []

        def read(offset: int, length: int) -> bytes:
            asked.append(length)
            return payload[offset:offset + length]

        identify.identify(payload[:identify.HEAD_BYTES], len(payload), read=read)
        self.assertEqual(set(asked), {identify.RW_SECTION_HEADER},
                         "a section header is 12 bytes; nothing else may be read")
        self.assertLessEqual(sum(asked), 4 * identify.RW_SECTION_HEADER)


class MmapAndSchlShapeTests(unittest.TestCase):
    def test_mmap_dimensions_come_from_the_offsets_the_readers_use(self) -> None:
        head = bytearray(0x40)
        head[0:4] = b"MMAP"
        struct.pack_into("<I", head, 0x04, 2)
        struct.pack_into("<HH", head, 0x28, 128, 64)
        struct.pack_into("<H", head, 0x2C, 1)
        found = identify.identify(bytes(head), 0x400)
        self.assertEqual(found.format, "MMAP")
        self.assertEqual((found.shape["version"], found.shape["width"],
                          found.shape["height"], found.shape["format_id"]),
                         (2, 128, 64, "0x1"))

    def test_schl_platform_is_named_not_numbered(self) -> None:
        head = b"SCHl" + struct.pack("<I", 24) + b"PT" + struct.pack("<H", 5) \
            + bytes([0x83, 1, 0x04, 0xFF]) + bytes(8)
        found = identify.identify(head, 4096)
        self.assertEqual(found.format, "SCHl")
        self.assertEqual(found.shape["platform"], "PS2")
        self.assertEqual(found.shape["codec"], 0x04)


class RetailFreeTests(unittest.TestCase):
    def test_a_clean_index_has_no_violations(self) -> None:
        rows = [
            {"row": "disc", "serial": "SLUS-00000", "label": "Synthetic", "image_bytes": 1},
            {"row": "file", "path": "/DATA/X.DAT", "bytes": 64, "format": "CPTH",
             "tag": "CPTH", "magic": "43505448"},
            {"row": "member", "key": "/DATA/X.DAT!0", "container": "/DATA/X.DAT",
             "name": "a.dff", "index": 0, "offset": 0, "size": 64, "format": "RW-CLUMP",
             "stored_sha256": "00" * 32},
        ]
        self.assertEqual(regen.retail_free_violations(rows), [])

    def test_a_payload_sample_that_escaped_is_named(self) -> None:
        rows = [{"row": "member", "key": "/X!0", "sample": "deadbeefdeadbeef00"}]
        found = regen.retail_free_violations(rows)
        self.assertEqual(len(found), 1)
        self.assertIn("hex run", found[0])

    def test_a_long_string_that_is_not_a_name_is_named(self) -> None:
        rows = [{"row": "member", "key": "/X!0", "text": "Q" * 200}]
        self.assertEqual(len(regen.retail_free_violations(rows)), 1)


class ProjectionTests(unittest.TestCase):
    """The index names more than the mapper does; the mapper's answer is a projection."""

    def test_a_file_the_mapper_cannot_name_projects_back_to_its_hex(self) -> None:
        row = {"row": "file", "format": "unknown", "magic": "796b8e70"}
        self.assertEqual(regen.as_mapper_names_a_file(row), "other:796b8e70")

    def test_a_speculative_renderware_id_projects_back_too(self) -> None:
        row = {"row": "file", "format": "RW-STRUCT?", "magic": "01000000"}
        self.assertEqual(regen.as_mapper_names_a_file(row), "other:01000000")

    def test_a_member_the_mapper_cannot_name_is_unclassified_not_a_hex_word(self) -> None:
        for fmt in ("unknown", "PS2-ICO", "zero-head", "RW-CLUMP?"):
            self.assertEqual(regen.as_mapper_names_a_member({"format": fmt}), "unclassified")
        self.assertEqual(regen.as_mapper_names_a_member({"format": "MMAP"}), "MMAP")


class DiffTests(unittest.TestCase):
    def test_a_key_only_one_side_has_is_reported_with_which_side(self) -> None:
        found = regen.diff({"a": 1, "b": 2}, {"a": 1, "c": 3})
        self.assertEqual(sorted(row["at"] for row in found), ["b", "c"])
        self.assertEqual([row for row in found if row["at"] == "c"][0]["published"], 3)

    def test_identical_documents_diff_to_nothing(self) -> None:
        self.assertEqual(regen.diff({"a": {"b": [1, 2]}}, {"a": {"b": [1, 2]}}), [])


class MapPageParserTests(unittest.TestCase):
    PAGE = "\n".join([
        "# Disc map - Synthetic (SLUS-00000)", "",
        "## File kinds", "", "| kind | files |", "|---|---:|",
        "| TERF | 85 |", "| ELF | 50 |", "",
        "## Totals (the numbers a page quotes)", "", "| measure | value |", "|---|---|",
        "| TERF containers | 85 (0 refused; 0 recorded short) |",
        "| members (level 1) | 30,391 |",
        "| codecs | NONE (stored) 22801, LZH1 7157, RLE1 433 |",
        "| TDB members | 581 (0 not the v8 layout); bare TDB files 1; distinct schema shapes 13 |",
        "| MMAP dimensions (top 10, format 0x400 excluded) | 128x128 x2968, 64x64 x891 |".replace("x2968", "×2968").replace("x891", "×891"),
        "",
    ])

    def test_it_reads_the_two_tables_and_nothing_else(self) -> None:
        with tempfile.TemporaryDirectory() as room:
            page = Path(room) / "SLUS-00000.Synthetic.map.md"
            page.write_text(self.PAGE, encoding="utf-8")
            found = map_md.parse(page)
        self.assertEqual(found["file_kinds"], {"TERF": 85, "ELF": 50})
        self.assertEqual(found["terf_containers"], 85)
        self.assertEqual(found["members_level_1"], 30391)
        self.assertEqual(found["codecs"]["NONE (stored)"], 22801)
        self.assertEqual(found["mmap_dimensions_top10"], {"128x128": 2968, "64x64": 891})

    def test_the_v8_in_the_tdb_row_is_not_read_as_a_count(self) -> None:
        with tempfile.TemporaryDirectory() as room:
            page = Path(room) / "SLUS-00000.Synthetic.map.md"
            page.write_text(self.PAGE, encoding="utf-8")
            found = map_md.parse(page)
        self.assertEqual((found["tdb_members"], found["bare_tdb_files"],
                          found["distinct_tdb_schemas"]), (581, 1, 13))


class IndexShapeTests(unittest.TestCase):
    def test_every_row_says_what_kind_of_row_it_is(self) -> None:
        rows = [{"row": "disc"}, {"row": "file"}, {"row": "container"}, {"row": "member"}]
        for kind in ("disc", "file", "container", "member"):
            self.assertEqual(len(regen.rows_of(rows, kind)), 1)

    def test_the_prototype_is_marked_as_one(self) -> None:
        from tools.owner.prototypes import disc_index
        self.assertTrue(disc_index.PROTOTYPE)
        for module in (identify, walk, regen, map_md):
            self.assertIn("PROTOTYPE", (module.__doc__ or ""),
                          "%s must say it is a prototype" % module.__name__)


if __name__ == "__main__":
    unittest.main(verbosity=2)
