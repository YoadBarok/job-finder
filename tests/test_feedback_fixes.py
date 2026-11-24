"""Regression tests for the first-run feedback (synthetic data only)."""
import csv, json, os, re, stat, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SK = ROOT / "plugins/job-finder/skills/job-finder"
sys.path.insert(0, str(SK / "scripts"))
from poll_boards import classify, normalize_url, score  # noqa: E402
from check_cv import keyword_present  # noqa: E402
import jf_config  # noqa: E402

HOME = ["Portugal", "Lisbon"]
J = lambda loc, text="", title="x": {"location": loc, "text": text, "title": title, "salary": None, "age_days": 10}
PY = sys.executable


class Canada(unittest.TestCase):
    def test_canada_only_is_x(self): self.assertEqual(classify(J("Canada"), HOME)[0], "X")
    def test_remote_canada_is_x(self): self.assertEqual(classify(J("Remote - Canada"), HOME)[0], "X")
    def test_us_and_canada_is_b(self): self.assertEqual(classify(J("Canada; United States"), HOME)[0], "B")
    def test_north_america_is_b(self): self.assertEqual(classify(J("Remote - North America"), HOME)[0], "B")


class Prescore(unittest.TestCase):
    S = {"titleInclude": ["senior", "staff", "platform", "identity"], "strongKeywords": [], "stackKeywords": []}
    def test_seniority_alone_is_weak(self):
        self.assertLessEqual(score(J("Remote", title="Senior Account Executive"), self.S)[0], 10)
    def test_role_match_counts_more(self):
        a = score(J("Remote", title="Senior Platform Engineer"), self.S)[0]
        b = score(J("Remote", title="Senior Account Executive"), self.S)[0]
        self.assertGreater(a, b)


class Urls(unittest.TestCase):
    def test_duplicate_query_params(self):
        self.assertEqual(normalize_url("https://x.io/jobs?gh_jid=8066493&gh_jid=8066493"), "https://x.io/jobs?gh_jid=8066493")
    def test_fragment_dropped(self):
        self.assertEqual(normalize_url("https://x.io/a#app"), "https://x.io/a")


class Keywords(unittest.TestCase):
    def test_plural_matches_singular(self): self.assertTrue(keyword_present("permissions", "fine-grained permission model"))
    def test_singular_matches_plural(self): self.assertTrue(keyword_present("permission", "permissions and roles"))
    def test_no_substring_false_positive(self): self.assertFalse(keyword_present("go", "google cloud"))


class Discovery(unittest.TestCase):
    def test_finds_existing_data_folder(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d, "Documents", "personal", "jobsearch"); real.mkdir(parents=True)
            (real / "criteria.md").write_text("# Job search criteria (agreed 2026-01-01)\n")
            other = Path(d, "Documents", "notes"); other.mkdir(parents=True)
            (other / "criteria.md").write_text("# Something else\n")
            self.assertEqual(jf_config.find_data_folders([d]), [str(real.resolve())])


class Configure(unittest.TestCase):
    def test_repoint_and_private_files(self):
        import shutil
        with tempfile.TemporaryDirectory() as d:
            skill = Path(d, "plugin", "skills", "job-finder"); shutil.copytree(SK, skill, ignore=shutil.ignore_patterns("__pycache__"))
            env = dict(os.environ, XDG_CONFIG_HOME=str(Path(d, "cfg")), HOME=str(Path(d, "home")))
            a, b, sl = Path(d, "dataA"), Path(d, "dataB"), Path(d, "proj", ".claude", "settings.local.json")
            for data in (a, b):
                subprocess.run([PY, str(skill / "scripts/configure.py"), "--data", str(data), "--claude-settings", str(sl)],
                               check=True, capture_output=True, text=True, env=env, cwd=d)
            dirs = json.loads(sl.read_text())["permissions"]["additionalDirectories"]
            self.assertEqual(dirs, [str(b.resolve())])
            self.assertEqual(json.loads(Path(d, "cfg", "job-finder", "config.json").read_text())["dataDir"], str(b.resolve()))
            mode = stat.S_IMODE(os.stat(b / "criteria.md").st_mode)
            self.assertEqual(mode & 0o077, 0, oct(mode))
            self.assertTrue((b / "base" / "cv.base.json").exists())


class Eligibility(unittest.TestCase):
    def test_eu_citizen_elsewhere_in_eu(self):
        self.assertEqual(classify(J("Remote - Germany"), ["Portugal", "Lisbon"], 0, ["EU"])[0], "A")
    def test_us_citizen_us_remote_is_a(self):
        self.assertEqual(classify(J("Remote - US", "E-Verify employer"), ["United States", "Austin"], -6, ["United States"])[0], "A")
    def test_no_contractor_us_is_x(self):
        self.assertEqual(classify(J("Remote - US"), ["Brazil"], -3, ["Brazil"], contractor_ok=False)[0], "X")
    def test_second_citizenship_country(self):
        self.assertEqual(classify(J("Sao Paulo, Brazil"), ["Portugal", "Lisbon"], 0, ["EU", "Brazil"])[0], "A")


class Builder(unittest.TestCase):
    def test_designer_cv_with_sections(self):
        if subprocess.run(["node", str(SK / "scripts/build_cv.js"), "--check"]).returncode != 0:
            self.skipTest("docx library not installed")
        with tempfile.TemporaryDirectory() as d:
            cv = {"name": "SAM TEST", "headline": "PRODUCT DESIGNER", "contact": [{"t": "Lisbon"}],
                  "jobs": [{"title": "Designer, Testco", "meta": "2020 – Present", "bullets": ["Did things."]}],
                  "sections": [{"title": "Education", "items": ["BA Design, 2015"]}]}
            Path(d, "cv.json").write_text(json.dumps(cv))
            subprocess.run(["node", str(SK / "scripts/build_cv.js"), str(Path(d, "cv.json")), str(Path(d, "Sam Test CV.docx"))], check=True)
            self.assertTrue(Path(d, "Sam Test CV.docx").stat().st_size > 1000)
    def test_template_refused(self):
        if subprocess.run(["node", str(SK / "scripts/build_cv.js"), "--check"]).returncode != 0:
            self.skipTest("docx library not installed")
        r = subprocess.run(["node", str(SK / "scripts/build_cv.js"), str(SK / "templates/cv.json"), "/tmp/x.docx"], capture_output=True)
        self.assertNotEqual(r.returncode, 0)


class Plugin(unittest.TestCase):
    def test_manifests(self):
        m = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        p = json.loads((ROOT / "plugins/job-finder/.claude-plugin/plugin.json").read_text())
        self.assertEqual(m["plugins"][0]["name"], p["name"])
        for s in ("job-finder", "setup", "find", "tailor", "digest"):
            self.assertTrue((ROOT / "plugins/job-finder/skills" / s / "SKILL.md").exists(), s)
    def test_no_contact_data_in_repo(self):
        """Generic guard: no real-looking emails or phone numbers anywhere in tracked text files."""
        email = re.compile(r"[\w.+-]+@(?!(?:example\.com|mail\.test|users\.noreply\.github\.com|anthropic\.com)\b)[\w-]+\.[\w.]+")
        phone = re.compile(r"\+\d[\d ]{8,}\d")
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        for f in files:
            pth = ROOT / f
            if pth.is_file() and pth.suffix in (".md", ".json", ".py", ".js", ".txt", ".csv"):
                t = pth.read_text(errors="ignore")
                self.assertIsNone(email.search(t), f"email-like string in {f}")
                self.assertIsNone(phone.search(t), f"phone-like string in {f}")


class Track(unittest.TestCase):
    def test_add_set_and_migrate(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "tracker.csv").write_text("company,role,link,score,date_found,source,cost_usd,status\n"
                                              "Acme,Eng,https://a/1,80,2026-01-01,poller (ashby),0,applied 2026-01-02 (follow up 2026-01-16)\n")
            t = [PY, str(SK / "scripts/track.py")]
            subprocess.run(t + ["add", "--data", d, "--company", "Beta", "--role", "SWE", "--link", "https://b/2",
                                "--score", "75", "--source", "poll_boards (lever)", "--status", "cv-ready"], check=True, capture_output=True)
            subprocess.run(t + ["set", "--data", d, "--link", "https://b/2", "--status", "applied", "--note", "follow up"], check=True, capture_output=True)
            bad = subprocess.run(t + ["add", "--data", d, "--company", "C", "--role", "R", "--link", "https://c/3",
                                      "--source", "my head", "--status", "cv-ready"], capture_output=True)
            self.assertNotEqual(bad.returncode, 0)
            rows = list(csv.DictReader(open(Path(d, "tracker.csv"))))
            self.assertEqual([r["status"] for r in rows], ["applied", "applied"])
            self.assertIn("follow up 2026-01-16", rows[0]["note"])



class Hardening(unittest.TestCase):
    def test_csv_formula_neutralised(self):
        from track import safe_cell
        self.assertEqual(safe_cell("=HYPERLINK(1)"), "'=HYPERLINK(1)")
        self.assertEqual(safe_cell("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(safe_cell("-5"), "-5")
        self.assertEqual(safe_cell("Senior Designer"), "Senior Designer")
    def test_apply_kit_rejects_unsafe_url(self):
        with tempfile.TemporaryDirectory() as d:
            for bad in ["https://x.io/a\r\nURL=file:///etc", "javascript:alert(1)", "http://plain.io/x"]:
                r = subprocess.run([PY, str(SK / "scripts/apply_kit.py"), d, "--job-url", bad, "--data", d], capture_output=True)
                self.assertNotEqual(r.returncode, 0, bad)
            ok = subprocess.run([PY, str(SK / "scripts/apply_kit.py"), d, "--job-url", "https://jobs.lever.co/acme/1", "--data", d], capture_output=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)
    def test_bad_slug_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "search.json").write_text(json.dumps({"homeCountry": ["Portugal"]}))
            Path(d, "companies.json").write_text(json.dumps([{"name": "Evil", "ats": "lever", "slug": "../../x?y"}]))
            r = subprocess.run([PY, str(SK / "scripts/poll_boards.py"), "--data", d, "--fixtures", d], capture_output=True, text=True)
            self.assertIn("invalid board type or slug", r.stdout)


class SkillZip(unittest.TestCase):
    def test_zip_is_current(self):
        import zipfile
        z = zipfile.ZipFile(ROOT / "dist/job-finder-skill.zip")
        names = {n for n in z.namelist()}
        want = {"job-finder/" + str(p.relative_to(SK)) for p in SK.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"}
        self.assertEqual(names, want, "run: python3 dev/build_skill_zip.py")
        for n in want:
            self.assertEqual(z.read(n), (SK / n.split("/", 1)[1]).read_bytes(), f"{n} changed; run: python3 dev/build_skill_zip.py")


if __name__ == "__main__": unittest.main()
