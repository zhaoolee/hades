import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from hades_dialogue.parsers import (
    _enclosing_spans,
    parse_lua_candidates,
    parse_sjson,
    parse_subtitle_csv,
)
from hades_dialogue.pipeline import build_records, collect, extract


class ParserTests(unittest.TestCase):
    def test_enclosing_spans_for_many_sibling_tables(self):
        tables = [f'{{ Cue = "/VO/Hero_{i:04d}" }}' for i in range(2000)]
        mask = "Outside = 1\nRoot = {\n" + ",\n".join(tables) + "\n}\n"
        positions = [mask.index("Cue", offset) for offset in self._table_offsets(mask)]

        spans = _enclosing_spans(mask, positions)

        self.assertEqual(len(spans), len(tables))
        for table, position, span in zip(tables, positions, spans):
            self.assertIsNotNone(span)
            self.assertEqual(mask[span[0]:span[1]], table)
            self.assertLessEqual(span[0], position)
            self.assertLess(position, span[1])
        self.assertEqual(_enclosing_spans(mask, [-1, len(mask)]), [None, None])

    @staticmethod
    def _table_offsets(mask):
        offset = 0
        while True:
            offset = mask.find("{ Cue", offset)
            if offset < 0:
                return
            yield offset
            offset += 1

    def test_csv_bom_quotes_and_duplicate_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "Hero.csv"
            p.write_text('\ufeffa,b,c,ID,e,f,g,Line\nq,,,Hero_0001,,, ,"Hello, world"\nq,,,Hero_0001,,,,Different\nq,,,EurydiceSong1_Eurydice_001,,,,Song line\n', encoding="utf-8")
            rows, issues = parse_subtitle_csv(p, "en", Path(td))
            self.assertEqual(rows["Hero_0001"].text, "Hello, world")
            self.assertEqual(rows["EurydiceSong1_Eurydice_001"].text, "Song line")
            self.assertEqual(issues[0]["kind"], "csv_conflict")
            self.assertNotIn(str(Path(td).resolve()), rows["Hero_0001"].source)

    def test_sjson_comments_suffix_and_context(self):
        text = '''{ Texts = [ { /* Event: E1\n Hero: Chosen English */ Id = "Hero_0013a" Speaker = "Hero" DisplayName = "中文\\n台词" } ] }'''
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "_A.zh-CN.sjson"
            p.write_text(text, encoding="utf-8")
            rows, issues = parse_sjson(p, Path(td))
            self.assertFalse(issues)
            self.assertEqual(rows["Hero_0013a"].text, "中文\n台词")
            self.assertIn("Chosen English", rows["Hero_0013a"].comment)

    def test_sjson_uses_only_direct_fields_from_id_object(self):
        text = '''{
  Texts = [ {
    Nested = { DisplayName = "WRONG", Speaker = "WrongSpeaker" },
    Id = "Hero_0001",
    DisplayName = "RIGHT",
    Speaker = "RightSpeaker"
  } ]
}'''
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "_A.zh-CN.sjson"
            p.write_text(text, encoding="utf-8")
            rows, issues = parse_sjson(p, Path(td))
            self.assertFalse(issues)
            self.assertEqual(rows["Hero_0001"].text, "RIGHT")
            self.assertEqual(rows["Hero_0001"].speaker, "RightSpeaker")

    def test_lua_nested_multiline_comments_and_disambiguation(self):
        lua = '''
Data = {
 { Cue = "/VO/Hero_0001", Nested = { a = { 1, 2 } },
   More = true,
   Text = "Wrong candidate" },
 { Cue = "/VO/Hero_0001",
   Nested = { one = { two = true } },
   -- translator note
   Text = "Chosen English" },
 -- { Cue = "/VO/Hero_9999", Text = "commented cue" },
 -- Text before the cue table
 { Cue = "/VO/Hero_0004" },
 { Cue = "/VO/Hero_0002" }, -- Text = "Adjacent line text"
}
--[[ { Cue = "/VO/Hero_0003", Nested = {x=1}, Text = "Block fallback" } ]]
'''
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "A.lua"
            p.write_text(lua, encoding="utf-8")
            got = parse_lua_candidates([p], Path(td))
            self.assertEqual([c.text for c in got["Hero_0001"]], ["Wrong candidate", "Chosen English"])
            self.assertNotIn("Hero_9999", got)
            self.assertEqual(got["Hero_0004"][0].text, "Text before the cue table")
            self.assertEqual(got["Hero_0002"][0].text, "Adjacent line text")
            self.assertTrue(got["Hero_0003"][0].fallback)
            self.assertEqual(got["Hero_0003"][0].text, "Block fallback")

    def test_lua_cue_uses_text_directly_in_same_table(self):
        lua = 'Data = { { Nested={Text="WRONG"}, Cue="/VO/Hero_0001", Text="RIGHT" } }'
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "A.lua"
            p.write_text(lua, encoding="utf-8")
            got = parse_lua_candidates([p], Path(td))
            self.assertEqual([candidate.text for candidate in got["Hero_0001"]], ["RIGHT"])

    def test_same_text_different_ids_are_retained(self):
        csv_rows = {
            "A_0001": {"en": "Same", "zh": "相同"},
            "A_0002": {"en": "Same", "zh": "相同"},
        }
        records, _ = build_records(csv_rows, {}, {})
        self.assertEqual([r["id"] for r in records], ["A_0001", "A_0002"])


class EndToEndTests(unittest.TestCase):
    def make_game(self, root):
        for lang, line in (("en", "Hello"), ("zh-CN", "你好")):
            p = root / "Content" / "Subtitles" / lang / "Hero.csv"
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerows([["a", "b", "c", "ID", "e", "f", "g", "Line"], ["", "", "", "Hero_0001", "", "", "", line]])
        s = root / "Content/Game/Text/zh-CN/_Test.zh-CN.sjson"
        s.parent.mkdir(parents=True, exist_ok=True)
        s.write_text('{ Texts = [ { /* Hero: Current */ Id="Hero_0002" Speaker="Hero" DisplayName="当前" } ] }', encoding="utf-8")
        lua = root / "Content/Scripts/Test.lua"
        lua.parent.mkdir(parents=True, exist_ok=True)
        lua.write_text('X={ { Cue="/VO/Hero_0002", Text="Current" } }', encoding="utf-8")

    def test_deterministic_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            game, out = Path(td) / "game", Path(td) / "out"
            self.make_game(game)
            extract(game, out)
            first = {p.relative_to(out): hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob("*") if p.is_file()}
            extract(game, out)
            second = {p.relative_to(out): hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob("*") if p.is_file()}
            self.assertEqual(first, second)
            data = json.loads((out / "all.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data), 2)
            self.assertTrue((out / "characters/Hero.md").exists())

    def test_csv_cross_file_conflict_prefers_id_prefix_channel_in_both_languages(self):
        with tempfile.TemporaryDirectory() as td:
            game = Path(td) / "game"
            for language in ("en", "zh-CN"):
                subtitle_dir = game / "Content/Subtitles" / language
                subtitle_dir.mkdir(parents=True)
                for channel, line in (("ZagreusField", f"WRONG-{language}"),
                                      ("ZagreusHome", f"RIGHT-{language}")):
                    with (subtitle_dir / f"{channel}.csv").open("w", encoding="utf-8", newline="") as handle:
                        csv.writer(handle).writerows([
                            ["a", "b", "c", "ID", "e", "f", "g", "Line"],
                            ["", "", "", "ZagreusHome_2761", "", "", "", line],
                        ])
            (game / "Content/Game/Text/zh-CN").mkdir(parents=True)
            (game / "Content/Scripts").mkdir(parents=True)

            records, audit = collect(game)

            record = next(row for row in records if row["id"] == "ZagreusHome_2761")
            self.assertEqual(record["en"], "RIGHT-en")
            self.assertEqual(record["zh"], "RIGHT-zh-CN")
            self.assertEqual(record["channel"], "ZagreusHome")
            conflicts = [issue for issue in audit["issues"]
                         if issue["kind"] == "csv_cross_file_conflict"]
            self.assertEqual({issue["language"] for issue in conflicts}, {"en", "zh-CN"})

    def test_extract_rejects_symlinks_in_managed_output_paths(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            game = base / "game"
            self.make_game(game)
            for relative in ("characters", "all.csv", "all.json", "audit.json", "README.md",
                             "characters/Hero.md", "characters/stale.md"):
                with self.subTest(relative=relative):
                    out = base / ("out-" + relative.replace("/", "-"))
                    out.mkdir()
                    victim = base / ("victim-" + relative.replace("/", "-"))
                    if relative == "characters":
                        victim.mkdir()
                    else:
                        victim.write_text("DO NOT TOUCH", encoding="utf-8")
                    link = out / relative
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(victim, target_is_directory=relative == "characters")

                    with self.assertRaises((ValueError, OSError)):
                        extract(game, out)

                    if victim.is_file():
                        self.assertEqual(victim.read_text(encoding="utf-8"), "DO NOT TOUCH")

    def test_extract_rejects_symlink_output_directory(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            game = base / "game"
            self.make_game(game)
            external = base / "external"
            external.mkdir()
            victim = external / "victim.md"
            victim.write_text("DO NOT TOUCH", encoding="utf-8")
            output_link = base / "out"
            output_link.symlink_to(external, target_is_directory=True)

            with self.assertRaises((ValueError, OSError)):
                extract(game, output_link)

            self.assertEqual(victim.read_text(encoding="utf-8"), "DO NOT TOUCH")

    def test_cli_bad_game_path(self):
        proc = subprocess.run([sys.executable, "-m", "hades_dialogue", "audit", "--game-root", "/definitely/missing"], text=True, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("game root", proc.stderr.lower())


class GeneratedDataRegressionTests(unittest.TestCase):
    def test_real_nested_text_and_csv_conflict_regressions(self):
        generated = Path(__file__).resolve().parents[1] / "generated/all.json"
        records = {row["id"]: row for row in json.loads(generated.read_text(encoding="utf-8"))}
        expected_english = {
            "Achilles_0259": "...If, indeed, I've something to be proud of, lad... it's that someone such as you can say a thing like that to me, and mean it.",
            "Achilles_0324": "All right, slow down, I understand. Look... this can get me in a lot of trouble, like you've no idea. And, not just me, so... be careful, and be quick, while he's still out. Take this and go. Don't leave anything there out of place, all right?",
            "Hades_0990": "I consider it an expansion of their responsibilities. Now, go.",
            "Orpheus_0187": "I grieve for you, my friend. But if you've come to ask me for a song, why, I'm afraid I must stand firm about my answer.",
            "Skelly_0370": "You kidding, pal? This is the life! Imagine getting paid to stand around! And being pals with you!",
        }
        for dialogue_id, expected in expected_english.items():
            with self.subTest(dialogue_id=dialogue_id):
                self.assertEqual(records[dialogue_id]["en"], expected)
        self.assertEqual(records["ZagreusHome_2761"]["en_source"],
                         "Content/Subtitles/en/ZagreusHome.csv")
        self.assertEqual(records["ZagreusHome_2761"]["zh_source"],
                         "Content/Subtitles/zh-CN/ZagreusHome.csv")


if __name__ == "__main__":
    unittest.main()
