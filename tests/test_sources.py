"""1.2.0: Workable / Recruitee / Personio boards and the free aggregator feeds."""
import datetime as dt, json, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SK = ROOT / "plugins/job-finder/skills/job-finder"
sys.path.insert(0, str(SK / "scripts"))
from poll_boards import norm_feed, norm_personio, norm_recruitee, norm_workable, feed_queries, parse_date  # noqa: E402

NOW = dt.datetime.now(dt.timezone.utc)
D = lambda days: (NOW - dt.timedelta(days=days))

WORKABLE = {"name": "Acme", "jobs": [
    {"title": "Senior Designer", "shortcode": "AB12", "telecommuting": True, "department": "Design",
     "url": "https://apply.workable.com/j/AB12", "published_on": D(2).date().isoformat(),
     "locations": [{"country": "Czechia", "countryCode": "CZ", "city": "Prague", "region": "", "hidden": False}]},
    {"title": "Office Manager", "shortcode": "ZZ99", "telecommuting": False, "url": "https://apply.workable.com/j/ZZ99",
     "published_on": D(1).date().isoformat(), "city": "Austin", "state": "Texas", "country": "United States"}]}

RECRUITEE = {"offers": [
    {"id": 7, "title": "Art Director", "status": "published", "location": "Amsterdam, Noord-Holland, Netherlands",
     "hybrid": True, "remote": False, "on_site": False, "careers_url": "https://acme.recruitee.com/o/art-director",
     "published_at": D(3).strftime("%Y-%m-%d %H:%M:%S UTC"), "description": "<p>Lead <b>brand</b> work</p>",
     "requirements": "<p>Figma</p>", "salary": {"min": 60000, "max": 80000, "period": "year", "currency": "EUR"}}]}

PERSONIO = f"""<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs><position><id>123</id><name>Creative Director</name><office>Prague</office>
<additionalOffices><additionalOffice>Berlin</additionalOffice></additionalOffices><department>Brand</department>
<createdAt>{D(4).isoformat()}</createdAt><jobDescriptions><jobDescription><name>Your role</name>
<value>&lt;p&gt;Own the brand&lt;/p&gt;</value></jobDescription></jobDescriptions></position></workzag-jobs>"""

FEEDS = {
    "arbeitnow": {"data": [{"slug": "designer-berlin-1", "company_name": "Beta", "title": "Senior Product Designer",
                            "description": "&lt;p&gt;Design&lt;/p&gt;", "remote": True, "url": "https://www.arbeitnow.com/jobs/x",
                            "tags": ["Design"], "location": "Berlin", "created_at": int(D(1).timestamp())}]},
    "jobicy": {"friendlyNotice": "credit", "jobs": [{"id": 9, "url": "https://jobicy.com/jobs/9", "jobTitle": "Brand Designer",
                                                     "companyName": "Gamma", "jobGeo": "Europe", "pubDate": D(2).isoformat(),
                                                     "jobDescription": "<p>Brand</p>"}]},
    "remoteok": [{"legal": "Please link back"}, {"id": "55", "company": "Delta", "position": "Designer", "location": "",
                                                 "epoch": int(D(1).timestamp()), "url": "https://remoteok.com/remote-jobs/55",
                                                 "apply_url": "https://remoteok.com/l/55", "description": "Figma", "tags": ["design"]}],
    "himalayas": {"jobs": [
        {"title": "Visual Designer", "companyName": "Eps", "guid": "h1", "applicationLink": "https://himalayas.app/apply/h1",
         "locationRestrictions": [], "pubDate": int(D(1).timestamp()), "expiryDate": int((NOW + dt.timedelta(days=20)).timestamp()),
         "description": "<p>Design</p>", "minSalary": 70000, "maxSalary": 90000, "currency": "EUR"},
        {"title": "Old Designer", "companyName": "Eps", "guid": "h2", "applicationLink": "https://himalayas.app/apply/h2",
         "pubDate": int(D(1).timestamp()), "expiryDate": int(D(1).timestamp()), "description": "expired"}]},
    "remotive": {"jobs": [{"id": 3, "company_name": "Zeta", "title": "UX Designer", "url": "https://remotive.com/remote-jobs/3",
                           "candidate_required_location": "USA only", "publication_date": D(1).isoformat(), "description": ""}]},
}


class Boards(unittest.TestCase):
    def test_workable(self):
        js = list(norm_workable("Acme", WORKABLE))
        self.assertEqual(js[0]["location"], "Prague, Czechia")
        self.assertEqual(js[0]["workplace"], "remote")
        self.assertTrue(js[0]["needs_description"])
        self.assertEqual(js[1]["location"], "Austin, Texas, United States")

    def test_recruitee(self):
        j = next(norm_recruitee("Acme", RECRUITEE))
        self.assertEqual(j["workplace"], "hybrid")
        self.assertIn("brand", j["text"]); self.assertIn("EUR 60000-80000", j["salary"])
        self.assertIsNotNone(parse_date(j["posted"]))

    def test_personio(self):
        j = next(norm_personio("Acme", PERSONIO, "acme"))
        self.assertEqual(j["url"], "https://acme.jobs.personio.de/job/123")
        self.assertEqual(j["location"], "Prague; Berlin")
        self.assertIn("Own the brand", j["text"])

    def test_personio_bad_xml(self):
        self.assertEqual(list(norm_personio("Acme", "<not xml", "acme")), [])


class Feeds(unittest.TestCase):
    def test_every_feed_credits_source(self):
        for f, data in FEEDS.items():
            js = list(norm_feed(f, data, NOW))
            self.assertTrue(js, f)
            for j in js:
                self.assertTrue(j["source"] and j["source_url"].startswith("https://"), f)

    def test_remoteok_skips_legal_and_uses_apply_url(self):
        js = list(norm_feed("remoteok", FEEDS["remoteok"], NOW))
        self.assertEqual(len(js), 1)
        self.assertEqual(js[0]["url"], "https://remoteok.com/l/55")
        self.assertEqual(js[0]["source_url"], "https://remoteok.com/remote-jobs/55")

    def test_himalayas_drops_expired_uses_application_link(self):
        js = list(norm_feed("himalayas", FEEDS["himalayas"], NOW))
        self.assertEqual([j["id"] for j in js], ["h1"])
        self.assertEqual(js[0]["url"], "https://himalayas.app/apply/h1")
        self.assertEqual(js[0]["location"], "Anywhere")

    def test_queries_from_titles(self):
        self.assertEqual(feed_queries({"titleRequireAny": [r"\bdesigner\b", "art director"], "titleInclude": ["senior"]}),
                         ["designer", "art director"])
        self.assertEqual(feed_queries({"feedQueries": ["creative director"]}), ["creative director"])


class EndToEnd(unittest.TestCase):
    def run_poll(self, srch, companies, extra=()):
        d = tempfile.mkdtemp()
        Path(d, "search.json").write_text(json.dumps(srch))
        Path(d, "companies.json").write_text(json.dumps(companies))
        fx = Path(d, "fx"); fx.mkdir()
        (fx / "workable-acme.json").write_text(json.dumps(WORKABLE))
        (fx / "recruitee-acme.json").write_text(json.dumps(RECRUITEE))
        (fx / "personio-acme.xml").write_text(PERSONIO)
        for f, data in FEEDS.items():
            (fx / f"feed-{f}.json").write_text(json.dumps(data))
        r = subprocess.run([sys.executable, str(SK / "scripts/poll_boards.py"), "--data", d, "--fixtures", str(fx), *extra],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(next(Path(d, "candidates").glob("*.json")).read_text()), r.stdout

    def test_designer_in_prague(self):
        srch = {"homeCountry": ["Czechia", "Prague"], "authorized": ["EU"], "contractorOK": False,
                "workplaces": ["remote", "hybrid", "onsite"], "commuteCities": ["Prague"],
                "titleRequireAny": ["designer", "director"], "titleExclude": ["office manager"], "maxAgeDays": 14}
        cos = [{"name": "Acme", "ats": a, "slug": "acme"} for a in ("workable", "recruitee", "personio")]
        out, stdout = self.run_poll(srch, cos)
        titles = {j["title"] for j in out}
        self.assertIn("Senior Designer", titles)          # Workable, remote, Prague
        self.assertIn("Creative Director", titles)        # Personio, office in Prague
        self.assertNotIn("Art Director", titles)          # Recruitee hybrid in Amsterdam: not a commute city
        self.assertIn("Senior Product Designer", titles)  # Arbeitnow remote, Berlin (EU)
        self.assertIn("Brand Designer", titles)           # Jobicy, Europe
        self.assertIn("Visual Designer", titles)          # Himalayas, worldwide
        self.assertNotIn("Old Designer", titles)          # expired
        self.assertNotIn("UX Designer", titles)           # USA only, no contractor route
        self.assertIn("credit them", stdout)
        for j in out:
            if j["ats"] in ("arbeitnow", "jobicy", "remoteok", "himalayas", "remotive"):
                self.assertTrue(j["source"])

    def test_feeds_can_be_turned_off(self):
        out, _ = self.run_poll({"homeCountry": ["Czechia"], "feeds": []}, [])
        self.assertEqual(out, [])
        out, _ = self.run_poll({"homeCountry": ["Czechia"]}, [], ["--no-feeds"])
        self.assertEqual(out, [])

    def test_duplicate_across_sources(self):
        dup = json.loads(json.dumps(FEEDS["jobicy"]))
        dup["jobs"][0]["companyName"] = "Beta"; dup["jobs"][0]["jobTitle"] = "Senior Product Designer"
        FEEDS_SAVE = FEEDS["jobicy"]; FEEDS["jobicy"] = dup
        try:
            out, _ = self.run_poll({"homeCountry": ["Czechia"], "authorized": ["EU"], "feeds": ["arbeitnow", "jobicy"]}, [])
        finally:
            FEEDS["jobicy"] = FEEDS_SAVE
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()


class TrackerSources(unittest.TestCase):
    def test_new_sources_accepted(self):
        import track
        for ok in ["feed (jobicy)", "feed (remotive)", "poll_boards (workable)", "poll_boards (personio)", "apify (a/b-c)"]:
            self.assertTrue(track.SOURCE.match(ok), ok)
        for bad in ["feed (evil)", "poll_boards (x)", "apify (a b)"]:
            self.assertFalse(track.SOURCE.match(bad), bad)


class Discovery(unittest.TestCase):
    def test_slug_candidates(self):
        from poll_boards import slug_candidates
        self.assertEqual(slug_candidates("Acme Labs, Inc."), ["acmelabsinc", "acme-labs-inc", "acme"])
        self.assertIn("trigger", slug_candidates("Trigger"))

    def test_discover_adds_only_boards_with_matching_jobs(self):
        from poll_boards import discover_boards
        boards = {"https://api.ashbyhq.com/posting-api/job-board/acme?includeCompensation=true":
                  {"jobs": [{"id": "1", "title": "Senior Software Engineer", "jobUrl": "https://jobs.ashbyhq.com/acme/1",
                             "publishedAt": "2026-11-20T00:00:00Z", "location": "Remote"}]},
                  "https://boards-api.greenhouse.io/v1/boards/salesonly/jobs?content=true":
                  {"jobs": [{"id": 2, "title": "Account Executive", "absolute_url": "https://x/2",
                             "updated_at": "2026-11-20T00:00:00Z", "location": {"name": "Remote"}}]}}

        def fake(url):
            if url in boards:
                return boards[url]
            raise OSError("404")
        known = {"ashby:already"}
        got = discover_boards(["Acme", "SalesOnly", "Already", "Nope"], known, lambda t: "engineer" in t.lower(),
                              fetch=fake, delay=0)
        self.assertEqual([(g["ats"], g["slug"]) for g in got], [("ashby", "acme")])
        self.assertIn("greenhouse:salesonly", known)  # remembered, not added (no matching jobs)

    def test_excluded_company_dropped(self):
        out, _ = EndToEnd().run_poll({"homeCountry": ["Czechia"], "authorized": ["EU"], "feeds": ["jobicy"],
                                      "excludeCompanies": ["Gamma"]}, [])
        self.assertEqual(out, [])


class LinkedInViaApify(unittest.TestCase):
    ITEMS = [{"jobId": "1", "jobTitle": "Senior Backend Engineer", "companyName": "Acme", "location": "Prague, Czechia",
              "publishedAt": D(2).isoformat(), "jobDescription": "Fully remote within Czechia. TypeScript, Node.js.",
              "jobUrl": "https://cz.linkedin.com/jobs/view/1", "applyUrl": "https://jobs.ashbyhq.com/acme/1",
              "workType": "", "salaryInfo": []},
             {"jobId": "2", "jobTitle": "Senior Backend Engineer", "companyName": "Make", "location": "Prague, Czechia",
              "publishedAt": D(2).isoformat(), "jobDescription": "x", "jobUrl": "https://cz.linkedin.com/jobs/view/2"}]

    def test_input_builder(self):
        sys.path.insert(0, str(SK / "scripts"))
        from linkedin_apify import build_input, max_cost
        inp = build_input({"homeCountry": ["Czechia", "Prague"], "titleRequireAny": ["engineer", "developer"],
                           "titleExclude": ["manager", "\\bvp\\b", "c\\+\\+"], "workplaces": ["remote", "hybrid"],
                           "excludeCompanies": ["Make"]}, 100)
        self.assertEqual(inp["locations"], ["Czechia"])
        self.assertEqual(inp["keyword"], ["engineer", "developer"])
        self.assertEqual(inp["workType"], ["remote", "hybrid"])
        self.assertIn("vp", inp["jobTitleExclude"]); self.assertIn("manager", inp["jobTitleExclude"])
        self.assertEqual(inp["companyExclude"], ["Make"])
        self.assertAlmostEqual(max_cost(100), 0.075)

    def test_import_wrapper_and_pipeline(self):
        d = tempfile.mkdtemp()
        f = Path(d, "li.json")
        f.write_text(json.dumps([{"type": "text", "text": json.dumps({"items": self.ITEMS})}]))  # connector wrapper
        Path(d, "search.json").write_text(json.dumps({"homeCountry": ["Czechia", "Prague"], "authorized": ["EU"],
                                                      "excludeCompanies": ["Make"], "feeds": []}))
        Path(d, "companies.json").write_text(json.dumps([{"name": "x", "ats": "ashby", "slug": "x", "disabled": True}]))
        r = subprocess.run([sys.executable, str(SK / "scripts/poll_boards.py"), "--data", d, "--import", str(f),
                            "--no-save"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(next(Path(d, "candidates").glob("*.json")).read_text())
        self.assertEqual([j["company"] for j in out], ["Acme"])            # Make excluded
        self.assertEqual(out[0]["url"], "https://jobs.ashbyhq.com/acme/1")  # employer link preferred
        self.assertTrue(out[0]["source"].startswith("LinkedIn"))
        self.assertIn("LinkedIn via Apify", r.stdout)


class Eligibility(unittest.TestCase):
    def cls(self, loc, text=""):
        from poll_boards import classify
        return classify({"location": loc, "text": text}, ["Czechia", "Prague"], 1, ["EU"], True)

    def test_country_locked_eu_remote_flagged(self):
        g, why = self.cls("Portugal", "Fully remote anywhere in Portugal.")
        self.assertEqual(g, "A"); self.assertIn("usually means living there", why[0])

    def test_region_wide_not_flagged(self):
        self.assertNotIn("living there", self.cls("EMEA - Remote")[1][0])
        self.assertNotIn("living there", self.cls("Germany", "We hire remotely anywhere in Europe.")[1][0])
        self.assertNotIn("living there", self.cls("Prague, Czechia")[1][0])

    def test_us_state_not_european_city(self):
        g, _ = self.cls("Dublin, OH")
        self.assertEqual(g, "B")

    def test_country_locked_scores_lower(self):
        from poll_boards import score
        s = {"titleRequireAny": ["engineer"]}
        j = {"title": "Senior Engineer", "text": "", "age_days": 3, "salary": None,
             "eligibility": ["listed for Portugal only: usually means living there - check before applying"]}
        k = dict(j, eligibility=["location fits"])
        self.assertEqual(score(k, s)[0] - score(j, s)[0], 20)
