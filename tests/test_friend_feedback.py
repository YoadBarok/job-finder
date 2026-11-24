"""Regression tests from a creative-director user's test run (synthetic data only)."""
import sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins/job-finder/skills/job-finder/scripts"))
from poll_boards import classify, workplace_ok  # noqa: E402

J = lambda loc, text="", workplace=None, remote=None: {"location": loc, "text": text, "title": "x", "workplace": workplace, "remote_flag": remote}
HOME, AUTH = ["Portugal", "Lisbon"], ["EU"]


class Cities(unittest.TestCase):
    def test_eu_city_without_country_is_a(self):
        for city in ("Berlin", "Budapest", "Amsterdam", "Warsaw", "Prague"):
            self.assertEqual(classify(J(city), HOME, 0, AUTH)[0], "A", city)
    def test_city_with_country(self): self.assertEqual(classify(J("Madrid, Spain"), HOME, 0, AUTH)[0], "A")
    def test_non_eu_city_is_x(self): self.assertEqual(classify(J("Tokyo"), HOME, 0, AUTH)[0], "X")
    def test_us_city_is_b(self): self.assertEqual(classify(J("San Francisco"), HOME, 0, AUTH)[0], "B")
    def test_hybrid_prefix(self): self.assertEqual(classify(J("Hybrid - Berlin"), HOME, 0, AUTH)[0], "A")


class Workplaces(unittest.TestCase):
    REMOTE_ONLY = {"workplaces": ["remote"]}
    HYBRID_PRAGUE_BERLIN = {"workplaces": ["remote", "hybrid", "onsite"], "commuteCities": ["Prague", "Berlin"]}
    def test_remote_only_drops_hybrid(self):
        self.assertFalse(workplace_ok(J("Hybrid - Berlin"), self.REMOTE_ONLY)[0])
    def test_hybrid_in_commute_city_kept(self):
        self.assertTrue(workplace_ok(J("Berlin", workplace="Hybrid"), self.HYBRID_PRAGUE_BERLIN)[0])
    def test_onsite_elsewhere_dropped(self):
        self.assertFalse(workplace_ok(J("Paris", workplace="OnSite"), self.HYBRID_PRAGUE_BERLIN)[0])
    def test_onsite_prague_kept(self):
        ok, mode = workplace_ok(J("Prague, Czechia", workplace="OnSite"), self.HYBRID_PRAGUE_BERLIN)
        self.assertTrue(ok); self.assertEqual(mode, "onsite")
    def test_remote_always_kept(self):
        self.assertTrue(workplace_ok(J("Remote - Europe"), self.REMOTE_ONLY)[0])
    def test_unknown_kept(self):
        self.assertTrue(workplace_ok(J("Berlin"), self.REMOTE_ONLY)[0])


if __name__ == "__main__": unittest.main()


class Discovery(unittest.TestCase):
    def test_parse_known_boards(self):
        from add_boards import parse
        cases = {
            "https://job-boards.greenhouse.io/deel/jobs/123": ("greenhouse", "deel"),
            "https://boards.greenhouse.io/embed/job_board?for=mollie": ("greenhouse", "mollie"),
            "https://jobs.ashbyhq.com/n8n/abc-123/application": ("ashby", "n8n"),
            "https://jobs.eu.lever.co/acme/1": ("lever", "acme"),
            "https://apply.workable.com/virtuos/j/ABC/": ("workable", "virtuos"),
            "https://jobs.smartrecruiters.com/Visa/7440": ("smartrecruiters", "Visa"),
            "https://bunq.recruitee.com/o/designer": ("recruitee", "bunq"),
            "https://studio.jobs.personio.de/job/1": ("personio", "studio"),
            "https://brandco.teamtailor.com/jobs/9": ("teamtailor", "brandco"),
        }
        for u, want in cases.items():
            self.assertEqual(parse(u), want, u)
        for bad in ["https://www.linkedin.com/jobs/view/1", "javascript:alert(1)", "https://example.com/careers"]:
            self.assertIsNone(parse(bad), bad)

    def test_add_dedupes_and_marks_unpolled(self):
        import json, subprocess, tempfile
        sk = ROOT / "plugins/job-finder/skills/job-finder/scripts/add_boards.py"
        with tempfile.TemporaryDirectory() as d:
            Path(d, "companies.json").write_text(json.dumps([{"name": "Deel", "ats": "ashby", "slug": "deel"}]))
            urls = ["https://jobs.ashbyhq.com/deel/1", "https://jobs.ashbyhq.com/Deel/2", "https://apply.workable.com/virtuos/j/1", "https://jobs.smartrecruiters.com/Acme/123-x"]
            out = json.loads(subprocess.run([sys.executable, str(sk), "--data", d, *urls], check=True, capture_output=True, text=True).stdout)
            self.assertEqual(out["added"], ["workable/virtuos", "smartrecruiters/Acme"])
            cs = json.loads(Path(d, "companies.json").read_text())
            self.assertEqual(len(cs), 3); self.assertNotIn("polled", cs[1]); self.assertIs(cs[2]["polled"], False)
