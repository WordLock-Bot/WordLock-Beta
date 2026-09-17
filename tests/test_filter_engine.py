"""Unit tests for the WordLock filter engine.

Run with:  python -m unittest tests.test_filter_engine
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.filter_engine import AhoCorasick, FilterEngine, WordEntry, normalize


class NormalizeTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(normalize("Idiot"), "idiot")

    def test_separators(self):
        self.assertEqual(normalize("id.iot"), "idiot")
        self.assertEqual(normalize("i d i o t"), "idiot")
        self.assertEqual(normalize("i-d-i-o-t"), "idiot")
        self.assertEqual(normalize("i_d_i_o_t"), "idiot")

    def test_leet(self):
        self.assertEqual(normalize("1di0t"), "idiot")
        self.assertEqual(normalize("1d10t"), "idiot")
        self.assertEqual(normalize("idi0t"), "idiot")
        self.assertEqual(normalize("fµck"), "fuck")

    def test_repeats(self):
        self.assertEqual(normalize("idiottttt"), "idiot")
        self.assertEqual(normalize("idiot!!!"), "idiot")
        self.assertEqual(normalize("fuckk"), "fuck")

    def test_homoglyphs(self):
        self.assertEqual(normalize("sсheisse"), "scheise")  # cyrillic с + е

    def test_accented(self):
        self.assertEqual(normalize("scheiße"), "scheise")


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = FilterEngine(default_languages=("de", "en"))

    def test_standard_list_loaded(self):
        self.assertGreater(len(self.engine.entries), 100)

    def test_evasions_caught(self):
        for text in ("id.iot", "1di0t", "i d i o t", "idiot!!!", "1d10t", "idi0t"):
            with self.subTest(text=text):
                result = self.engine.check(text)
                self.assertIsNotNone(result, f"should match: {text}")
                self.assertEqual(result[0], "idiot")

    def test_clean_text_passes(self):
        for text in (
            "Hallo, wie geht es dir?",
            "hello world",
            "good morning everyone",
            "i have many skills in this game",
            "she is very successful",
            "the grapes were delicious",
        ):
            with self.subTest(text=text):
                self.assertIsNone(self.engine.check(text))

    def test_cross_token_evasion(self):
        self.assertIsNotNone(self.engine.check("i d i o t"))
        self.assertIsNotNone(self.engine.check("f u c k"))
        self.assertIsNotNone(self.engine.check("i . d . i . o . t"))

    def test_custom_words(self):
        custom = [
            WordEntry("zorbax", category="custom", severity=4, custom=True, action="warn")
        ]
        self.engine.reload(custom_entries=custom)
        result = self.engine.check("you are a zorbax today")
        self.assertIsNotNone(result)
        self.assertTrue(result[3].custom)
        self.assertEqual(result[3].action, "warn")

    def test_check_all_dedupes(self):
        results = self.engine.check_all("fuck this shit")
        words = {r[0] for r in results}
        self.assertIn("fuck", words)
        self.assertIn("shit", words)


class AhoCorasickTests(unittest.TestCase):
    def test_basic_matches(self):
        ac = AhoCorasick(["he", "she", "his", "hers"])
        matches = ac.find("ushers")
        found = {m[0] for m in matches}
        self.assertIn("she", found)
        self.assertIn("hers", found)
        self.assertIn("he", found)

    def test_no_matches(self):
        ac = AhoCorasick(["xyz", "abc"])
        self.assertEqual(ac.find("nothing here"), [])


if __name__ == "__main__":
    unittest.main()
