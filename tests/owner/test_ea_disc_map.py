"""The read-only disc mapper: schema reader, header parsers, container / archive mapping, rendering and the
compare / summary / page modes -- on synthetic bytes only.  Nothing here reads a disc or a retail file."""

from __future__ import annotations

import json
import mmap
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _candidate in (ROOT, ROOT / "tools", ROOT / "tools" / "owner"):   # owner first: the mapper lives in tools/owner
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

import ea_disc_map as mapper  # noqa: E402
import ps2_iso9660 as iso  # noqa: E402
from mod_editor.games._formats import ea_terf  # noqa: E402


class TdbSchemaTests(unittest.TestCase):
    def test_tables_fields_and_preamble(self) -> None:
        db = mapper._synthetic_tdb([("TEAM", [("TGID", 3, 8), ("TDNA", 0, 32)], 3)])
        schema = mapper.tdb_schema(db)
        self.assertEqual([t["name"] for t in schema["tables"]], ["TEAM"])
        self.assertEqual(schema["tables"][0]["fields"][0], {"name": "TGID", "type": "uint", "bit_offset": 0, "bits": 8})
        self.assertEqual(mapper.tdb_schema(b"\x02\x00\x00\x00" + db)["preamble"], 4)
        self.assertEqual(mapper.schema_signature(schema), mapper.schema_signature(mapper.tdb_schema(db)))

    def test_version_word_is_read_from_both_byte_orders(self) -> None:
        db = mapper._synthetic_tdb([("TEAM", [("TGID", 3, 8)], 1)])
        self.assertEqual(db[2:4], b"\x00\x08", "the synthetic database carries the on-disc byte order")
        self.assertEqual((mapper.tdb_schema(db)["version"], mapper.tdb_schema(db)["version_bytes"]), (8, "0008"))
        swapped = db[:2] + b"\x08\x00" + db[4:]
        self.assertEqual((mapper.tdb_schema(swapped)["version"], mapper.tdb_schema(swapped)["version_bytes"]), (8, "0800"))
        self.assertEqual(mapper.identify_head(db[:16]), "TDB")

    def test_not_a_database_is_a_sentence(self) -> None:
        with self.assertRaises(mapper.MapError):
            mapper.tdb_schema(b"TERF" + bytes(64))
        with self.assertRaises(mapper.MapError):
            mapper.tdb_schema(b"DB\x00\x08" + bytes(8))  # shorter than its own header
        with self.assertRaises(mapper.MapError):
            mapper.tdb_schema(b"DB\x00\x08" + bytes(12) + struct.pack("<I", 500) + bytes(4))  # 500 tables in 24 bytes

    def test_big_endian_is_reported_not_parsed(self) -> None:
        head = bytearray(24); head[:2] = b"DB"; struct.pack_into(">I", head, 0x10, 3)
        self.assertEqual(mapper.tdb_schema(bytes(head))["endian"], "big")
        self.assertEqual(mapper.tdb_schema(bytes(head))["tables"], [])


class HeaderParserTests(unittest.TestCase):
    def test_schl_pt_and_gstr_headers(self) -> None:
        pt = mapper.schl_header(mapper._synthetic_schl(platform=5, channels=2, codec=0x08, codec2=0x0A, rate=28000))
        self.assertEqual((pt["platform"], pt["channels"], pt["codec"], pt["codec2"], pt["rate"], pt["version"]), (5, 2, 8, 10, 28000, 3))
        gstr = mapper.schl_header(mapper._synthetic_schl(platform="GSTR", channels=None))
        self.assertEqual((gstr["platform"], gstr["channels"], gstr["rate"]), ("GSTR", None, 22050))
        self.assertIsNone(mapper.schl_header(b"SCHl" + struct.pack("<I", 36) + b"XX" + bytes(30)))
        self.assertIsNone(mapper.schl_header(b"BNKl" + bytes(60)))
        stats = mapper._schl_stats([pt, gstr, None])
        self.assertEqual((stats["parsed"], stats["unparsed"]), (2, 1))
        self.assertEqual(stats["platforms"], {"PS2": 1, "GSTR": 1})
        self.assertEqual(stats["channels"], {"2": 1, "-": 1})

    def test_shps_header(self) -> None:
        bank = mapper._synthetic_shps([(0x02, 64, 32), (0x01, 8, 8)])
        info = mapper.shps_header(bank)
        self.assertEqual((info["images"], info["directory_id"], info["endian"], info["first_image"]), (2, "G354", "little", {"record_id": 2, "width": 64, "height": 32}))
        be = mapper.shps_header(mapper._synthetic_shps([(0x7B, 128, 16)], big_endian=True))
        self.assertEqual((be["images"], be["endian"], be["first_image"]), (1, "big", {"record_id": 0x7B, "width": 128, "height": 16}))
        with self.assertRaises(mapper.MapError):
            mapper.shps_header(b"MMAP" + bytes(32))

    def test_refpack_head_decodes_only_the_head(self) -> None:
        payload = b"SHPS" + bytes(range(200))
        packed = mapper._refpack_literal(payload)
        declared, head = mapper.refpack_head(packed, 32)
        self.assertEqual((declared, head), (len(payload), payload[:32]))
        self.assertIsNone(mapper.refpack_head(b"\x00\x00\x00\x00\x00", 32), "not RefPack")
        self.assertIsNone(mapper.refpack_head(packed[:8], 32), "cut before 32 bytes exist")
        self.assertIsNone(mapper.refpack_head(b"\x10\xfb\x00\x00\x40\x00\x05", 32), "a back-reference into nothing")

    def test_mmap_ids_elf_info_and_qkl(self) -> None:
        self.assertEqual(mapper.mmap_ids(mapper._synthetic_mmap(1, 3, format_id=0x400, pixel_bytes=80)), (2, 0x400, 80))
        from mod_editor.games._formats import ps2_elf
        info = mapper.elf_info(ps2_elf.build_synthetic_elf([0])[:32])
        self.assertEqual((info["class"], info["endian"], info["type"], info["machine"]), (32, "little", "EXEC", 8))
        irx = bytearray(ps2_elf.build_synthetic_elf([0])[:32]); struct.pack_into("<H", irx, 16, 0xFF80)
        self.assertEqual(mapper.elf_info(bytes(irx))["type"], "IRX (SCE IOP relocatable)")
        with self.assertRaises(mapper.MapError):
            mapper.elf_info(b"TERF" + bytes(28))
        q = mapper.map_qkl(mapper._synthetic_qkl(["a.dat", "b.dat"], [(0, 0, 0, 0), (1, 0, 3, 64), (1, 1, 0, 128), (1, 1, 1, 128)]))
        self.assertEqual((q["files"], q["entries"], q["header_copies"], q["member_copies"], q["distinct_offsets"]), (2, 4, 1, 3, 3))
        self.assertEqual(q["copies_per_file"], {"b.dat": 2, "a.dat": 2})
        with self.assertRaises(mapper.MapError):
            mapper.map_qkl(b"TERF" + bytes(32))

    def test_file_kinds(self) -> None:
        self.assertEqual(mapper.magic_kind(b"TERF@\x00\x00\x00"), "TERF")
        self.assertEqual(mapper.magic_kind(b"DB\x00\x08" + bytes(12)), "TDB")
        self.assertTrue(mapper.magic_kind(b"\x00\x01\x02\x03").startswith("other:"))
        self.assertEqual(mapper.identify_head(b"", "/VC_20919/0."), "VC-pack")
        self.assertEqual(mapper.identify_head(b"TERF" + bytes(12), "/VC_20919/DATA/X.DAT"), "TERF", "only the pack files are VC packs")
        self.assertEqual(mapper.identify_head(b""), "empty")
        self.assertEqual(mapper.identify_head(bytes(16)), "zero-head")
        self.assertEqual(mapper.identify_head(b"\x00\x00\x01\x00\x01\x00\x00\x00\x07\x00\x00\x00\x00\x00\x80\x3f"), "PS2-ICO")
        self.assertTrue(mapper.identify_head(b"\x00\x00\x01\x00\x02\x00\x03\x00\x04\x00\x05\x00\x06\x00\x07\x00").startswith("other:"), "a codepage table is not an icon")
        self.assertEqual(mapper.identify_head(b"RESET\x00\x00\x00" + bytes(8)), "IOPRP")
        self.assertEqual(mapper.identify_head(b"PS2D" + bytes(12)), "ICON.SYS")
        self.assertEqual(mapper.identify_head(b"\x00\x00\x01\xb3" + bytes(12)), "MPEG-video")
        self.assertEqual(mapper.identify_head(b"\x03\x12\x3c\x07" + bytes(12)), "EVT")
        self.assertEqual(mapper.identify_head(b"# <Sony DNAS>\r\n"), "TEXT")
        self.assertEqual(mapper.identify_head(b"ShpS" + bytes(12)), "SHPS")
        self.assertEqual(mapper.ext_hint("/DATA/AUDIO/EVENTS.EVT"), "EA audio event table (no magic)")
        self.assertEqual(mapper.ext_hint("/DATA/X.DAT"), "")


class SyntheticDiscTests(unittest.TestCase):
    """One synthetic disc, mapped once, examined many ways."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.image, cls.payloads = mapper.build_synthetic_disc()
        cls.path = Path(cls.tmp.name) / "disc.iso"
        cls.path.write_bytes(cls.image)
        cls.mapped = mapper.map_disc(cls.path, label="Synthetic (USA)")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_container_counts(self) -> None:
        c = self.mapped["containers"]["/DATA/X.DAT"]
        self.assertEqual(c["members"], 8)
        self.assertEqual(c["formats"], {"MMAP": 2, "SCHl": 1, "TDB": 1, "TERF": 1, "TEXT": 1, "empty": 1, "unclassified": 1})
        self.assertEqual((c["nested_terf"], c["nested_depth_max"], c["nested_tdb_members"]), (1, 2, 1))
        self.assertEqual(c["nested_formats"], {"TDB": 1, "TERF": 1, "TEXT": 1})
        self.assertEqual(c["mmap_dimensions"], {"32x32": 1})
        self.assertEqual((c["mmap_format_0x400"], c["mmap_formats"]), (1, {"v2/fmt0x1": 1, "v2/fmt0x400": 1}))
        self.assertEqual(c["unclassified_heads"], {"f8010000": 1})
        self.assertEqual(c["schl"]["platforms"], {"PS2": 1})
        self.assertEqual(c["member_sizes"]["distinct"], len({m.decompressed_size for m in ea_terf.parse_terf(self.payloads["container"]).members}))
        self.assertEqual(c["iso_length"], len(self.payloads["container"]))
        self.assertNotIn("iso_short_by", c)

    def test_archives(self) -> None:
        a = self.mapped["archives"]["/DATA/Z.BIG"]
        self.assertEqual((a["entries"], a["entries_read"], a["size_field"], a["directory_entries"]), (8, 8, "LE", 1))
        self.assertEqual(a["member_kinds"], {"SHPS": 2, "ABKC": 1, "BIGF": 1, "SCHl": 1, "TDB": 1, "TERF": 1, "directory": 1})
        self.assertEqual((a["refpack_members"], a["refpack_declared_bytes"]), (1, len(mapper._synthetic_shps([(0x01, 128, 128)])) + 40))
        self.assertEqual((a["shps_members"], a["shps_images"]), (4, 5))
        self.assertEqual(a["shps_first_record_ids"], {"0x02": 2, "0x01": 1, "0x7b": 1}, "the nested banks are counted too, the big-endian one included")
        self.assertEqual((a["nested_bigf"], a["nested_entries"], a["nested_member_kinds"]), (1, 3, {"SHPS": 2, "ELF": 1}))
        self.assertEqual(a["terf_members"]["data/seven.dat"]["formats"], {"TDB": 1, "TEXT": 1})
        self.assertEqual(a["tdb_members"][0]["tables"], [["TEAM", 3], ["PLAY", 5]] if isinstance(a["tdb_members"][0]["tables"][0], list) else [("TEAM", 3), ("PLAY", 5)])
        self.assertEqual(self.mapped["archives"]["/DATA/W.VIV"]["size_field"], "BE")
        self.assertEqual(self.mapped["archives"]["/DATA/W.VIV"]["member_kinds"], {"other:53544154": 1})

    def test_preloads_executables_databases_kinds(self) -> None:
        q = self.mapped["preloads"]["/DATA/GAME.QKL"]
        self.assertEqual((q["files"], q["entries"], q["header_copies"], q["member_copies"]), (2, 3, 1, 2))
        e = self.mapped["executables"]["/SLUS_000.00"]
        self.assertEqual((e["type"], e["size"], len(e["sha256"])), ("EXEC", len(self.payloads["elf"]), 64))
        self.assertEqual(self.mapped["databases"]["/DATA/STRM.DB"]["schema"], next(iter(self.mapped["schemas"])))
        self.assertEqual(len(self.mapped["schemas"]), 1, "one table/field shape, recorded once across file, member, nested and archive copies")
        kinds = self.mapped["kinds"]
        for kind, count in (("TERF", 2), ("BIGF", 2), ("TDB", 1), ("QL01", 1), ("ELF", 1), ("TEXT", 2), ("ICON.SYS", 1), ("IOPRP", 1), ("MPEG-video", 1), ("zero-head", 1), ("empty", 1), ("other:0102", 1)):
            self.assertEqual(kinds.get(kind), count, kind)
        blank = next(f for f in self.mapped["files"] if f["path"] == "/DATA/BLANK.RGB")
        self.assertEqual(blank["hint"], "raw image (no magic)")
        self.assertEqual(self.mapped["identity"]["serial"], "SLUS-00000")
        self.assertEqual(self.mapped["image"]["sector_size"], 2048)

    def test_totals(self) -> None:
        t = self.mapped["totals"]
        self.assertEqual((t["containers"], t["members"], t["mmap_members"], t["mmap_containers"]), (2, 10, 3, 2))
        self.assertEqual((t["text_members"], t["schl_members"], t["nested_terf"], t["tdb_members"], t["unclassified"]), (1, 1, 1, 2, 1))
        self.assertEqual(t["chains"], {"TERF -> DIR1 -> DATA": 1, "TERF -> DIR1 -> COMP -> DATA": 1})
        self.assertEqual(t["unclassified_magics"], [{"magic": "f8010000", "members": 1, "containers": ["X.DAT"]}])
        self.assertEqual((t["archives"], t["archive_entries"], t["archive_refpack_members"], t["archive_shps_members"]), (2, 9, 1, 4), "top-level entries only; the nested archive is counted in nested_entries")

    def test_json_is_deterministic_and_sorted(self) -> None:
        again = mapper.map_disc(self.path, label="Synthetic (USA)")
        strip = lambda m: {k: v for k, v in m.items() if k not in ("generated_utc", "seconds")}  # noqa: E731
        self.assertEqual(json.dumps(strip(self.mapped), sort_keys=True), json.dumps(strip(again), sort_keys=True))
        text = json.dumps(self.mapped, indent=2, sort_keys=True)
        self.assertEqual(json.loads(text)["totals"], self.mapped["totals"])

    def test_raw_cd_image_maps_identically(self) -> None:
        image, _ = mapper.build_synthetic_disc(sector_size=2352, data_offset=24)
        path = Path(self.tmp.name) / "raw.bin"; path.write_bytes(image)
        raw = mapper.map_disc(path, label="Synthetic (USA)")
        self.assertEqual(raw["image"]["sector_size"], 2352)
        strip = lambda m: {k: v for k, v in m.items() if k not in ("image", "generated_utc", "seconds")}  # noqa: E731
        self.assertEqual(json.dumps(strip(raw), sort_keys=True), json.dumps(strip(self.mapped), sort_keys=True))

    def test_markdown_page_compare_summary(self) -> None:
        md = mapper.render_markdown(self.mapped)
        for needle in ("## Totals", "| MMAP members | 3 across 2 containers |", "## Databases inside containers", "## Archives (EA BIG)",
                       "## Preload copies (QL01)", "## Executables (ELF / IRX)", "TGID:uint8", "`f8010000` | 1 | X.DAT"):
            self.assertIn(needle, md)
        for forbidden in ("payload", "\x00"):
            self.assertNotIn(forbidden, md.lower())
        page = mapper.render_page(self.mapped, today="1970-01-01")
        self.assertIn("| Uniforms & Equipment |", page)
        self.assertIn("| The Crib | — | — | honest empty page |", page)
        self.assertIn("MMAP members: 3 across 2 containers", page)
        self.assertNotIn("→ extract-only", page)
        self.assertIn("Distinct schema shapes: 1.", page)
        compare = mapper.render_compare(self.mapped, self.mapped)
        self.assertIn("added 0, removed 0, changed 0, identical in every mapped count 2", compare)
        summary = mapper.render_summary([self.mapped])
        self.assertIn("| Synthetic (USA) | SLUS-00000 |", summary)

    def test_compare_sees_a_changed_container(self) -> None:
        other = json.loads(json.dumps(self.mapped))
        other["containers"]["/DATA/X.DAT"]["formats"]["MMAP"] = 5
        other["containers"]["/DATA/X.DAT"]["members"] = 11
        del other["containers"]["/DATA/Y.DAT"]
        other["files"] = [f for f in other["files"] if f["path"] != "/DATA/Y.DAT"]
        text = mapper.render_compare(self.mapped, other)
        self.assertIn("removed 1", text)
        self.assertIn("members 8→11", text)
        self.assertIn("formats: MMAP 2→5", text)

    def test_cli_modes_write_files(self) -> None:
        out = Path(self.tmp.name) / "cli"
        code = mapper.main(["--iso", str(self.path), "--out", str(out), "--label", "Synthetic (USA)", "--quiet"])
        self.assertEqual(code, 0)
        json_path = out / "SLUS-00000.Synthetic-USA.map.json"
        self.assertTrue(json_path.is_file() and (out / "SLUS-00000.Synthetic-USA.map.md").is_file())
        self.assertEqual(mapper.main(["--render", str(json_path)]), 0)
        self.assertEqual(mapper.main(["--page", str(json_path)]), 0)
        self.assertTrue((out / "SLUS-00000.Synthetic-USA.page.md").is_file())
        self.assertEqual(mapper.main(["--compare", str(json_path), str(json_path), "--out", str(out / "cmp.md")]), 0)
        self.assertIn("identical in every mapped count 2", (out / "cmp.md").read_text(encoding="utf-8"))
        self.assertEqual(mapper.main(["--summary", str(out), "--out", str(out / "SUMMARY.md")]), 0)
        self.assertIn("SLUS-00000", (out / "SUMMARY.md").read_text(encoding="utf-8"))
        self.assertNotIn("\r\n", (out / "SUMMARY.md").read_bytes().decode("utf-8"))


class DefectToleranceTests(unittest.TestCase):
    """The Deluxe defects, damaged containers and short images end in a sentence, never a traceback."""

    def _record_of(self, image: bytearray, name: bytes) -> int:
        index = image.index(name)
        return index - 33

    def test_iso9660_record_short_of_the_declared_length_is_read_to_the_declared_length(self) -> None:
        image, payloads = mapper.build_synthetic_disc()
        image = bytearray(image)
        record = self._record_of(image, b"X.DAT;1")
        length = struct.unpack_from("<I", image, record + 10)[0]
        self.assertEqual(length, len(payloads["container"]))
        struct.pack_into("<I", image, record + 10, length - 64); struct.pack_into(">I", image, record + 14, length - 64)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.iso"; path.write_bytes(bytes(image))
            mapped = mapper.map_disc(path)
        c = mapped["containers"]["/DATA/X.DAT"]
        self.assertNotIn("error", c)
        self.assertEqual((c["members"], c["iso_short_by"], c["mapped_length"], c["iso_length"]), (8, 64, length, length - 64))
        self.assertEqual(mapped["totals"]["containers_iso_short"], 1)
        self.assertIn("ISO9660 record 64 bytes short", mapper.render_markdown(mapped))

    def test_damaged_container_and_truncated_image_are_sentences(self) -> None:
        damaged = ea_terf.build_terf([b"x" * 40], chunk="DATA")
        damaged = damaged[:64] + b"ZZZZ" + damaged[68:]   # the DIR1 tag becomes ZZZZ
        image = iso.build_synthetic_iso(files=[(b"SYSTEM.CNF;1", b"BOOT2 = cdrom0:\\SLUS_000.00;1\r\n"), (b"SLUS_000.00;1", b"\x7fELF" + bytes(60))],
                                        sub_files=[(b"BAD.DAT;1", damaged), (b"GOOD.DAT;1", ea_terf.build_terf([b"TEXT " * 20], chunk="DATA")),
                                                   (b"LAST.DAT;1", ea_terf.build_terf([bytes(6000)], chunk="DATA"))])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "damaged.iso"; path.write_bytes(image[:-4096])   # the image ends 4 KiB early
            mapped = mapper.map_disc(path)
            self.assertIn("error", mapped["containers"]["/DATA/BAD.DAT"])
            self.assertIn("DIR1", mapped["containers"]["/DATA/BAD.DAT"]["error"])
            self.assertEqual(mapped["containers"]["/DATA/GOOD.DAT"]["formats"], {"TEXT": 1})
            self.assertIn("error", mapped["containers"]["/DATA/LAST.DAT"], "the extent runs past the end of the image")
            self.assertEqual(mapped["totals"]["containers_refused"], ["/DATA/BAD.DAT", "/DATA/LAST.DAT"])
            with open(path, "rb+") as handle:
                handle.write(b"\x00")   # nothing left mapped or exported: the file can be written again
        self.assertIn("refused:", mapper.render_markdown(mapped))

    def test_view_math_under_a_64k_allocation_granularity(self) -> None:
        image, payloads = mapper.build_synthetic_disc()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "disc.iso"; path.write_bytes(image)
            volume = iso.open_image(path); entry = iso.find(volume, "/DATA/X.DAT")
            original = mmap.ALLOCATIONGRANULARITY
            try:
                mmap.ALLOCATIONGRANULARITY = 65536   # Windows; a multiple of every POSIX page size, so the mapping still succeeds here
                with open(path, "rb") as handle:
                    extent = mapper._Extent(handle, volume, entry)
                    with extent.view() as view:
                        self.assertEqual(bytes(view.data), payloads["container"])
                    self.assertEqual(extent.read(4, 8), payloads["container"][4:12])
            finally:
                mmap.ALLOCATIONGRANULARITY = original

    def test_render_accepts_a_v1_map(self) -> None:
        old = {"schema": "ea_disc_map/v1", "label": "Old", "generated_utc": "1970-01-01T00:00:00Z", "seconds": 0.0,
               "image": {"name": "old.iso", "size": 2048, "files": 1, "directories": 1, "sector_size": 2048},
               "identity": {"serial": "SLUS-00000", "boot_file": "SLUS_000.00", "boot_sha256": "0" * 64, "boot_size": 16, "pcsx2_crc": "00000000", "image_sha256": None},
               "kinds": {"TERF": 1}, "files": [{"path": "/DATA/X.DAT", "size": 1, "lba": 100, "kind": "TERF"}],
               "containers": {"/DATA/X.DAT": {"chain": "TERF -> DIR1 -> DATA", "alignment": 64, "members": 1, "declared_length": 1, "size_mismatch": 0,
                                              "codecs": {"NONE (stored)": 1}, "formats": {"MMAP": 1}, "layout_violations": [], "mmap_dimensions": {"32x32": 1},
                                              "text_members": 0, "text_bytes": 0, "tdb_members": []}},
               "archives": {}, "databases": {}, "schemas": {}}
        self.assertIn("| MMAP members | 1 across 1 containers |", mapper.render_markdown(old))
        self.assertIn("| All Textures |", mapper.render_page(old, today="1970-01-01"))
        self.assertIn("| Old |", mapper.render_summary([old]))


class MidwayAndAnd1Tests(unittest.TestCase):
    """The non-EA readers, on synthetic bytes: each identity the reader claims, and each refusal."""

    def test_mwo3_overlay_sizes_account_for_the_file(self) -> None:
        blob = mapper._synthetic_mwo3(index=2, load=0x0079E600, segment1=512, segment2=128, name=b"NETDVD.OVL")
        head = mapper.mwo3_header(blob[:mapper.MWO3_HEADER_BYTES], len(blob))
        self.assertEqual((head["index"], head["load_address"], head["name"]), (2, 0x0079E600, "NETDVD.OVL"))
        self.assertTrue(head["segments_account_for_file"])
        self.assertTrue(head["address1_is_load_plus_size"] and head["address2_equals_address1"])
        self.assertEqual(mapper.MWO3_HEADER_BYTES + head["segment1_bytes"] + head["segment2_bytes"], len(blob))

    def test_mwo3_reports_a_size_field_that_does_not_add_up(self) -> None:
        blob = bytearray(mapper._synthetic_mwo3(segment1=256, segment2=64))
        struct.pack_into("<I", blob, 16, 999)          # segment 2 now lies
        head = mapper.mwo3_header(bytes(blob[:64]), len(blob))
        self.assertFalse(head["segments_account_for_file"], "a wrong size field must not read as measured")
        with self.assertRaises(mapper.MapError):
            mapper.mwo3_header(b"MWo2" + bytes(60))

    def test_zih_index_in_both_shapes_points_into_its_zip(self) -> None:
        members = [("art/one.rtd", b"\x16\x00\x00\x00" + bytes(40)), ("b/two.ini", b"key = value\r\n"), ("c/three.dff", bytes(96))]
        blob = mapper._synthetic_zip(members)
        rows = mapper._zip_data_offsets(blob, members)
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "z.bin"; zip_path.write_bytes(blob)
            with open(zip_path, "rb") as handle:
                extent = mapper._Extent(handle, None, None, offset=0, size=len(blob))
                for variant in ("inline", "table"):
                    index = mapper.zih_index(mapper._synthetic_zih(rows, variant=variant))
                    self.assertEqual((index["variant"], index["entries"], index["entries_read"]), (variant, 3, 3))
                    check = mapper.zih_versus_zip(index, extent)
                    self.assertEqual(check["landed_on_a_local_file_header"], 3)
                    self.assertEqual(check["names_match"], 3)
                    self.assertEqual(check["missed"], 0)
                    if variant == "inline":
                        self.assertEqual(check["crc_matches"], check["crc_entries_checked"])
                        self.assertEqual(check["crc_entries_checked"], 3)

    def test_a_zih_offset_that_points_nowhere_is_counted_as_a_miss(self) -> None:
        members = [("one.bin", bytes(64))]
        blob = mapper._synthetic_zip(members)
        rows = [(name, size, offset + 7, crc) for name, size, offset, crc in mapper._zip_data_offsets(blob, members)]
        index = mapper.zih_index(mapper._synthetic_zih(rows))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "z.bin"; path.write_bytes(blob)
            with open(path, "rb") as handle:
                check = mapper.zih_versus_zip(index, mapper._Extent(handle, None, None, offset=0, size=len(blob)))
        self.assertEqual((check["landed_on_a_local_file_header"], check["missed"]), (0, 1))

    def test_zih_refuses_a_header_whose_own_length_word_is_wrong(self) -> None:
        with self.assertRaises(mapper.MapError):
            mapper.zih_index(struct.pack("<II", 3, 999) + bytes(64))
        with self.assertRaises(mapper.MapError):
            mapper.zih_index(b"\x00" * 8)

    def test_midway_metadata_checks_its_name_hash_against_the_path(self) -> None:
        blob = mapper._synthetic_midway_meta([(0xC36737C2, "databases", "objects\\c36737c2.of"),
                                              (0x0FD26C79, "playbooks", "objects\\fd26c79.of")])
        parsed = mapper.midway_meta(lambda o, n: blob[o:o + n], len(blob))
        self.assertEqual(parsed["records"], 2)
        self.assertEqual(parsed["region_bytes"], 8 + 2 * mapper.MIDWAY_META_SLOT)
        self.assertTrue(parsed["region_ends_at_file_end"])
        self.assertEqual(parsed["name_hash_matches_path_stem"], 2)
        self.assertEqual(parsed["name_hash_mismatches"], 0)
        self.assertEqual(sorted(parsed["categories"]), ["databases", "playbooks"])

    def test_midway_metadata_reports_a_hash_that_disagrees_with_its_path(self) -> None:
        blob = mapper._synthetic_midway_meta([(0xDEADBEEF, "misc", "objects\\c36737c2.of")])
        parsed = mapper.midway_meta(lambda o, n: blob[o:o + n], len(blob))
        self.assertEqual((parsed["name_hash_matches_path_stem"], parsed["name_hash_mismatches"]), (0, 1))
        with self.assertRaises(mapper.MapError):
            mapper.midway_meta(lambda o, n: (b"\x11\x11\x11\x11" + struct.pack("<I", 4) + bytes(64))[o:o + n], 72)

    def test_midway_sound_bank_records_and_name_table(self) -> None:
        blob = mapper._synthetic_ms2([(1, bytes(64)), (0x20000002, bytes(96)), (3, b"")], names=["943.mst", "945.mst"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.ms2"; path.write_bytes(blob)
            with open(path, "rb") as handle:
                bank = mapper.map_midway_sound(mapper._Extent(handle, None, None, offset=0, size=len(blob)))
        self.assertTrue(bank["total_field_is_file_size"])
        self.assertEqual(bank["records_read"], 3)
        self.assertEqual(bank["empty_slots"], 1)
        self.assertTrue(bank["offsets_ascending"] and bank["last_member_ends_at_eof"])
        self.assertEqual(bank["name_table_extensions"], {"mst": 2})

    def test_midway_sound_bank_refuses_a_header_whose_total_is_not_the_file(self) -> None:
        blob = bytearray(mapper._synthetic_ms2([(1, bytes(32))]))
        struct.pack_into("<I", blob, 16, 123456)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "b.ms2"; path.write_bytes(bytes(blob))
            with open(path, "rb") as handle:
                with self.assertRaises(mapper.MapError):
                    mapper.map_midway_sound(mapper._Extent(handle, None, None, offset=0, size=len(blob)))

    def test_obf_option_tree_walks_to_the_last_byte(self) -> None:
        tree = mapper.obf_tree(mapper._synthetic_obf([("Blitz.Video.Ball", "In Hand Scale", 2, 0x3F99999A),
                                                      ("Blitz.GameOptions.Plays", "Force Plays", 1, 0)]))
        self.assertTrue(tree["consumed_whole_file"])
        self.assertEqual((tree["sections"], tree["settings"]), (2, 2))
        self.assertEqual(tree["value_types"], {"float": 1, "int": 1})
        self.assertEqual(tree["top_level_names"], {"Blitz": 4})

    def test_obf_stops_at_a_tag_it_does_not_know_and_says_how_far_it_got(self) -> None:
        blob = mapper._synthetic_obf([("A", "B", 1, 0)]) + b"\x7f\x01Z"
        tree = mapper.obf_tree(blob)
        self.assertFalse(tree["consumed_whole_file"])
        self.assertEqual(tree["consumed_bytes"], len(blob) - 3)
        with self.assertRaises(mapper.MapError):
            mapper.obf_tree(b"\x02\xf0" + bytes(8))

    def test_efs_archive_directory_and_one_level_of_nesting(self) -> None:
        inner = mapper._synthetic_efs([("LEAF.PPD", b".HDR" + bytes(28))])
        blob = mapper._synthetic_efs([("ATLANTA.BIN", bytes(32)),
                                      ("COMMON.DIM", mapper._synthetic_hdr(["pause_bg", "ball"])),
                                      ("ANIM_INNER.EFS", inner)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.efs"; path.write_bytes(blob)
            with open(path, "rb") as handle:
                archive = mapper.map_efs(mapper._Extent(handle, None, None, offset=0, size=len(blob)))
        self.assertEqual(archive["entries"], 3)
        self.assertTrue(archive["directory_fits_before_data"])
        self.assertTrue(archive["last_member_ends_at_eof"])
        self.assertEqual((archive["members_inside_file"], archive["sizes_agree"]), (3, 3))
        self.assertEqual((archive["nested_efs"], archive["nested_entries"]), (1, 1))
        self.assertEqual((archive["hdr_directories"], archive["hdr_directories_checked"]), (1, 1))
        self.assertEqual(archive["extensions"], {"BIN": 1, "DIM": 1, "EFS": 1})

    def test_efs_refuses_a_directory_that_does_not_fit(self) -> None:
        with self.assertRaises(mapper.MapError):
            mapper.map_efs(_BytesExtent(b"EFS " + struct.pack("<3I", 64, 5000, 0xFFFFFFFF) + bytes(48)))
        with self.assertRaises(mapper.MapError):
            mapper.map_efs(_BytesExtent(b"EFT " + bytes(60)))

    def test_hdr_directory_uses_the_offset_the_header_gives(self) -> None:
        for table_offset in (mapper.HDR_DIR_HEADER_BYTES, 20):
            directory = mapper.hdr_dir(mapper._synthetic_hdr(["pause_bg", "ball", "allscore"], table_offset=table_offset))
            self.assertEqual(directory["entry_table_offset"], table_offset)
            self.assertTrue(directory["table_ends_at_first_member"])
            self.assertEqual(directory["names_sample"], ["pause_bg", "ball", "allscore"])
        with self.assertRaises(mapper.MapError):
            mapper.hdr_dir(b".HDX" + bytes(28))

    def test_renderware_label_is_earned_by_the_section_length(self) -> None:
        self.assertEqual(mapper.renderware_section(struct.pack("<3I", 0x16, 52, 0x1803FFFF), 64), 0x16)
        self.assertIsNone(mapper.renderware_section(struct.pack("<3I", 0x10, 40, 0x1803FFFF), 64))
        self.assertIsNone(mapper.renderware_section(b"\x16\x00", 64))

    def test_vagp_header_accounts_for_the_file(self) -> None:
        stream = mapper._synthetic_vagp(rate=22050, data_bytes=160, name=b"Idle1b")
        head = mapper.vagp_header(stream[:mapper.VAGP_HEADER_BYTES], len(stream))
        self.assertEqual((head["sample_rate"], head["data_bytes"], head["name"], head["version"]), (22050, 160, "Idle1b", 0x20))
        self.assertTrue(head["data_plus_header_is_file"])
        self.assertFalse(mapper.vagp_header(stream[:mapper.VAGP_HEADER_BYTES], len(stream) + 1)["data_plus_header_is_file"])
        with self.assertRaises(mapper.MapError):
            mapper.vagp_header(b"VAGq" + bytes(44))

    def test_a_name_never_reaches_a_document_as_a_raw_control_byte(self) -> None:
        self.assertEqual(mapper._printable(b"ok\x01\x7f"), "ok\\x01\\x7f")
        self.assertEqual(mapper._printable(b"caf\xe9"), "caf\\xe9")


class _BytesExtent:
    """The two methods the container readers use, over a bytes object -- no file, no disc."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.size = len(data)

    def read(self, start: int, length: int, limit=None) -> bytes:
        return self.data[start:start + length]


class SelftestTests(unittest.TestCase):
    def test_the_selftest_passes_as_a_subprocess(self) -> None:
        completed = subprocess.run([sys.executable, str(ROOT / "tools" / "owner" / "ea_disc_map.py"), "--selftest"],
                                   capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("EA_DISC_MAP_SELFTEST_PASS", completed.stdout)


if __name__ == "__main__":
    unittest.main()
