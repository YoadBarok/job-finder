"""Offline tests: python3 -m unittest discover tests"""
import datetime as dt, json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SK = ROOT / "plugins/job-finder/skills/job-finder"
sys.path.insert(0, str(SK / "scripts"))
from poll_boards import classify, is_onsite  # noqa: E402

HOME = ["Portugal", "Lisbon"]
J = lambda loc, text="": {"location": loc, "text": text, "title": "x"}

class Classify(unittest.TestCase):
    def test_home_country(self): self.assertEqual(classify(J("Portugal; Spain"), HOME)[0], "A")
    def test_europe(self): self.assertEqual(classify(J("Remote - Europe"), HOME)[0], "A")
    def test_everify(self): self.assertEqual(classify(J("Remote - US", "We are an E-Verify employer"), HOME)[0], "C")
    def test_clearance(self): self.assertEqual(classify(J("Remote", "active security clearance"), HOME)[0], "C")
    def test_us_timezones(self): self.assertEqual(classify(J("United States", "Mountain, Central, and Eastern time zones"), HOME)[0], "C")
    def test_other_country(self): self.assertEqual(classify(J("Poland; Germany"), HOME)[0], "X")
    def test_soft_us(self): self.assertEqual(classify(J("Remote - US", "Node.js"), HOME)[0], "B")
    def test_city_elsewhere(self): self.assertEqual(classify(J("London", "we are distributed"), HOME)[0], "X")
    def test_us_remote_text_anywhere(self): self.assertEqual(classify(J("US Remote", "work from anywhere"), HOME)[0], "B")
    def test_other_country_code(self): self.assertEqual(classify(J("Remote, KSA"), HOME)[0], "X")
    def test_tz_range(self): self.assertEqual(classify(J("Remote (UTC-3 to UTC+3); Madrid"), HOME, 1)[0], "A")
    def test_global(self): self.assertEqual(classify(J("Remote, Global"), HOME)[0], "A")
    def test_hybrid_dropped(self): self.assertTrue(is_onsite(J("Hybrid - New York City")))
    def test_text_emea(self): self.assertEqual(classify(J("Remote", "hiring anywhere in EMEA"), HOME)[0], "A")

class EndToEnd(unittest.TestCase):
    def test_fixtures(self):
        with tempfile.TemporaryDirectory() as d:
            srch = {"homeCountry": HOME, "homeUtcOffset": 1, "maxAgeDays": 14, "keepGroups": ["A", "B"],
                    "titleRequireAny": ["engineer", "developer"],
                    "titleExclude": ["manager", "director", "intern"],
                    "titleInclude": ["senior", "staff", "platform", "identity", "agent"],
                    "strongKeywords": ["MCP", "agents", "authorization"], "stackKeywords": ["TypeScript", "Node.js"]}
            Path(d, "search.json").write_text(json.dumps(srch))
            Path(d, "companies.json").write_text((ROOT / "tests/companies.test.json").read_text())
            fx = Path(d, "fx"); fx.mkdir()
            now = dt.datetime.now(dt.timezone.utc)
            for f in (ROOT / "tests/fixtures").glob("*.json"):  # fixtures carry relative dates
                t = f.read_text().replace("__NOW__", now.isoformat()).replace("__OLD__", (now - dt.timedelta(days=30)).isoformat())
                t = t.replace('"__MS__"', str(int((now - dt.timedelta(days=1)).timestamp() * 1000)))
                (fx / f.name).write_text(t)
            subprocess.run([sys.executable, str(SK / "scripts/poll_boards.py"), "--data", d, "--fixtures", str(fx)], check=True, capture_output=True)
            out = json.loads(next(Path(d, "candidates").glob("*.json")).read_text())
            self.assertEqual({j["url"] for j in out}, {"https://example.com/ab/2", "https://example.com/gh/1", "https://example.com/lv/1"})

if __name__ == "__main__": unittest.main()
