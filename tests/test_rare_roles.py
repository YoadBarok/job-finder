"""1.2.1: rare-role searches (from a creative-director test run): title-only settings must still score,
and postings that require a language the person doesn't speak are marked down, not hidden."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins/job-finder/skills/job-finder/scripts"))
from poll_boards import language_gap, score  # noqa: E402

S = {"titleRequireAny": ["creative director", "head of creative"], "strongKeywords": ["brand"], "languages": ["English"]}
J = lambda title, text="": {"title": title, "text": text, "age_days": 20, "salary": None}


class TitleOnlySettings(unittest.TestCase):
    def test_require_any_counts_as_role_match(self):
        pts, why = score(J("Creative Director"), S)
        self.assertGreaterEqual(pts, 20); self.assertIn("role title match", why)


class Languages(unittest.TestCase):
    def test_required(self):
        self.assertEqual(language_gap("Fluent German (C1) is required.", ["English"]), ["German"])
        self.assertEqual(language_gap("Fließend Deutsch und Englisch.", ["English"]), ["German"])
        self.assertEqual(language_gap("Native-level French and English.", ["English"]), ["French"])

    def test_nice_to_have_and_mentions_ignored(self):
        for t in ["French is a plus.", "German would be nice to have.", "Our office is in Germany. Strong portfolio required.",
                  "Excellent English; Dutch is an advantage."]:
            self.assertEqual(language_gap(t, ["English"]), [], t)

    def test_spoken_language_ok_and_unset_skips(self):
        self.assertEqual(language_gap("Fluent German required.", ["English", "German"]), [])
        self.assertEqual(language_gap("Fluent German required.", None), [])

    def test_penalty_and_flag(self):
        j = J("Creative Director", "Brand work. Fluent German is required.")
        pts, why = score(j, S)
        self.assertEqual(j["language_gap"], ["German"])
        self.assertLess(pts, score(J("Creative Director", "Brand work."), S)[0])
        self.assertTrue(any("German" in w for w in why))


if __name__ == "__main__":
    unittest.main()
