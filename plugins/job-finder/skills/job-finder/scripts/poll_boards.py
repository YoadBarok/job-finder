#!/usr/bin/env python3
"""Poll companies' public job boards and free job aggregators for fresh roles.

Boards (per company in companies.json): Greenhouse, Ashby, Lever, Workable, Recruitee, Personio.
Aggregators (search.json "feeds"; default all): Arbeitnow, Jobicy, RemoteOK, Himalayas, Remotive.
Free: these are public APIs/feeds the sites publish for exactly this use. No login, no scraping.
Aggregator rules we follow: polite intervals (feeds_state.json), credit + link back to the source on
every candidate ("source", "source_url"), Himalayas/RemoteOK apply links used as given, nothing republished.

Usage:
  python3 scripts/poll_boards.py --data ~/job-finder-data            # live
  python3 scripts/poll_boards.py --data DIR --fixtures tests/fixtures  # offline test

Reads   DATA/search.json           (filters; see examples/search.example.json)
        DATA/companies.json        (optional; overrides config/companies.json)
        DATA/seen.json             (job keys already reported; updated unless --no-save)
        DATA/tracker.csv           (links already in the tracker are skipped)
Writes  DATA/candidates/<date>.json and prints a short table.

Every candidate gets an eligibility group for someone working from DATA/search.json "homeCountry":
  A  open to Europe/EMEA/anywhere or names the home country
  B  "Remote"/"Remote (US)" with no hard limits found -> apply + mention contractor setup
  C  hard US-only signals (must reside in US, E-Verify, clearance, US citizen/person, ITAR)
  X  locked to other countries that do not include the home country
It is a heuristic pre-filter: a human (or Claude) still reads the posting before tailoring a CV.
"""
from __future__ import annotations

import argparse, csv, datetime as dt, html, json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import country_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent  # skill folder
UA = "job-finder/1.0 (personal job search; polite polling)"

ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{slug}",
    "recruitee": "https://{slug}.recruitee.com/api/offers/",
    "personio": "https://{slug}.jobs.personio.de/xml?language=en",
}
NOT_POLLABLE = ("smartrecruiters", "teamtailor")  # robots.txt / no public feed: checked by hand

# ---------- helpers ----------

def strip_html(s: str | None) -> str:
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def normalize_url(u: str) -> str:
    """Drop duplicated query params (some Greenhouse boards emit ?gh_jid=1&gh_jid=1) and fragments."""
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    if not u:
        return u
    sp = urlsplit(u)
    seen, q = set(), []
    for k, v in parse_qsl(sp.query, keep_blank_values=True):
        if (k, v) not in seen:
            seen.add((k, v)); q.append((k, v))
    return urlunsplit((sp.scheme, sp.netloc, sp.path, urlencode(q), ""))


def parse_date(v) -> dt.datetime | None:
    if v is None:
        return None
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):  # epoch ms (Lever) or s (feeds)
        v = float(v)
        return dt.datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=dt.timezone.utc)
    v = str(v).strip().replace("Z", "+00:00")
    v = re.sub(r" UTC$", "+00:00", v)  # Recruitee: "2026-11-18 16:23:32 UTC"
    try:
        d = dt.datetime.fromisoformat(v)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def fetch_json(url: str, retries: int = 2, raw: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, application/xml"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read(20_000_000)
                return body.decode("utf-8", "replace") if raw else json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                raise LookupError(f"board not found ({e.code}) - check the slug")
            if e.code == 429 and attempt < retries:
                time.sleep(5 * (attempt + 1)); continue
            raise
        except urllib.error.URLError:
            if attempt < retries:
                time.sleep(2); continue
            raise

# ---------- normalisers: one record shape for all three ATSs ----------

def norm_greenhouse(company, data):
    for j in data.get("jobs", []):
        yield {
            "company": company, "ats": "greenhouse", "id": str(j.get("id")),
            "title": j.get("title", ""), "location": (j.get("location") or {}).get("name", ""),
            "posted": j.get("first_published") or j.get("updated_at"),
            "url": j.get("absolute_url", ""), "text": strip_html(j.get("content")),
            "salary": None, "remote_flag": None,
        }


def norm_ashby(company, data):
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [(s or {}).get("location", "") for s in j.get("secondaryLocations") or []]
        comp = (j.get("compensation") or {})
        yield {
            "company": company, "ats": "ashby", "id": str(j.get("id")),
            "title": j.get("title", ""), "location": "; ".join(l for l in locs if l),
            "posted": j.get("publishedAt"), "url": j.get("jobUrl", ""),
            "text": j.get("descriptionPlain") or strip_html(j.get("descriptionHtml")),
            "salary": comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary"),
            "remote_flag": j.get("isRemote"), "workplace": j.get("workplaceType"),
        }


def norm_lever(company, data):
    for j in data if isinstance(data, list) else []:
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or [cat.get("location") or ""]
        sr = j.get("salaryRange") or {}
        salary = f"{sr.get('currency','')} {sr.get('min')}-{sr.get('max')} {sr.get('interval','')}".strip() if sr else None
        extra = " ".join(f"{l.get('text','')} {strip_html(l.get('content'))}" for l in j.get("lists") or [])
        yield {
            "company": company, "ats": "lever", "id": str(j.get("id")),
            "title": j.get("text", ""), "location": "; ".join(l for l in locs if l),
            "posted": j.get("createdAt"), "url": j.get("hostedUrl", ""),
            "text": " ".join([j.get("descriptionPlain") or "", extra, j.get("additionalPlain") or ""]).strip(),
            "salary": salary, "remote_flag": None, "workplace": j.get("workplaceType"),
        }


def norm_workable(company, data):
    """Widget feed has no description: Claude fetches the posting before scoring (text is empty)."""
    for j in data.get("jobs", []) if isinstance(data, dict) else []:
        locs = [", ".join(x for x in (l.get("city"), l.get("region"), l.get("country")) if x)
                for l in j.get("locations") or [] if not l.get("hidden")]
        if not locs:
            locs = [", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)]
        yield {
            "company": company, "ats": "workable", "id": str(j.get("shortcode") or j.get("code") or j.get("url")),
            "title": j.get("title", ""), "location": "; ".join(l for l in locs if l),
            "posted": j.get("published_on") or j.get("created_at"), "url": j.get("url") or j.get("shortlink", ""),
            "text": " ".join(x for x in (j.get("department"), j.get("function"), j.get("employment_type")) if x),
            "salary": None, "remote_flag": bool(j.get("telecommuting")), "workplace": "remote" if j.get("telecommuting") else None,
            "needs_description": True,
        }


def norm_recruitee(company, data):
    for j in data.get("offers", []) if isinstance(data, dict) else []:
        if j.get("status") not in (None, "published"):
            continue
        sal = j.get("salary") or {}
        salary = (f"{sal.get('currency','')} {sal.get('min')}-{sal.get('max')} {sal.get('period','')}".strip()
                  if sal.get("min") or sal.get("max") else None)
        wp = "hybrid" if j.get("hybrid") else "remote" if j.get("remote") else "onsite" if j.get("on_site") else None
        yield {
            "company": company, "ats": "recruitee", "id": str(j.get("id")),
            "title": j.get("title", ""), "location": j.get("location") or ", ".join(x for x in (j.get("city"), j.get("country")) if x),
            "posted": j.get("published_at") or j.get("created_at"), "url": j.get("careers_url", ""),
            "text": strip_html((j.get("description") or "") + " " + (j.get("requirements") or "")),
            "salary": salary, "remote_flag": bool(j.get("remote")), "workplace": wp,
        }


def norm_personio(company, data, slug=""):
    """Personio publishes XML; the posting URL is built from the board slug and position id."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(data) if isinstance(data, str) else None
    except ET.ParseError:
        root = None
    if root is None:
        return
    for p in root.iter("position"):
        g = lambda t: (p.findtext(t) or "").strip()
        offices = [g("office")] + [(o.text or "").strip() for o in p.iter("additionalOffice")]
        desc = " ".join(strip_html((d.findtext("name") or "") + " " + (d.findtext("value") or ""))
                        for d in p.iter("jobDescription"))
        pid = g("id")
        yield {
            "company": company, "ats": "personio", "id": pid, "title": g("name"),
            "location": "; ".join(o for o in offices if o), "posted": g("createdAt"),
            "url": f"https://{slug}.jobs.personio.de/job/{pid}" if slug and pid.isdigit() else "",
            "text": " ".join(x for x in (g("department"), g("seniority"), g("schedule"), desc) if x),
            "salary": None, "remote_flag": None, "workplace": None,
        }


NORMALISERS = {"greenhouse": norm_greenhouse, "ashby": norm_ashby, "lever": norm_lever,
               "workable": norm_workable, "recruitee": norm_recruitee, "personio": norm_personio}
RAW_TEXT = {"personio"}  # XML, not JSON

# ---------- free aggregators (public APIs; each asks for credit + a link back) ----------

FEEDS = {
    #  name: (url, min hours between fetches, credit shown to the person)
    "arbeitnow": ("https://www.arbeitnow.com/api/job-board-api", 3, "Arbeitnow (arbeitnow.com)"),
    "jobicy": ("https://jobicy.com/api/v2/remote-jobs?count=100", 6, "Jobicy (jobicy.com)"),
    "remoteok": ("https://remoteok.com/api", 3, "Remote OK (remoteok.com)"),
    "himalayas": ("https://himalayas.app/jobs/api/search?q={q}&sort=recent", 24, "Himalayas (himalayas.app)"),
    "remotive": ("https://remotive.com/api/remote-jobs?search={q}&limit=100", 6, "Remotive (remotive.com)"),
}


def _feed_job(feed, id_, company, title, location, posted, url, text, salary=None, workplace="remote",
              source_url=None):
    return {"company": company or "?", "ats": feed, "id": str(id_), "title": title or "", "location": location or "",
            "posted": posted, "url": url or "", "text": text or "", "salary": salary,
            "remote_flag": workplace == "remote", "workplace": workplace,
            "source": FEEDS[feed][2], "source_url": source_url or url or ""}


def norm_feed(feed, data, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if feed == "arbeitnow":
        for j in (data or {}).get("data", []):
            yield _feed_job(feed, j.get("slug"), j.get("company_name"), j.get("title"), j.get("location"),
                            j.get("created_at"), j.get("url"), strip_html(j.get("description")) + " " + " ".join(j.get("tags") or []),
                            workplace="remote" if j.get("remote") else "onsite")
    elif feed == "jobicy":
        for j in (data or {}).get("jobs", []):
            sal = (f"{j.get('salaryCurrency','')} {j.get('annualSalaryMin')}-{j.get('annualSalaryMax')} year".strip()
                   if j.get("annualSalaryMin") else None)
            yield _feed_job(feed, j.get("id"), j.get("companyName"), j.get("jobTitle"), j.get("jobGeo"), j.get("pubDate"),
                            j.get("url"), strip_html(j.get("jobDescription") or j.get("jobExcerpt")), sal)
    elif feed == "remoteok":
        for j in data if isinstance(data, list) else []:
            if not isinstance(j, dict) or "legal" in j or not j.get("position"):
                continue
            sal = f"USD {j['salary_min']}-{j['salary_max']} year" if j.get("salary_min") else None
            yield _feed_job(feed, j.get("id"), j.get("company"), j.get("position"), j.get("location") or "Remote",
                            j.get("epoch") or j.get("date"), j.get("apply_url") or j.get("url"),
                            strip_html(j.get("description")) + " " + " ".join(j.get("tags") or []), sal,
                            source_url=j.get("url"))
    elif feed == "himalayas":
        for j in (data or {}).get("jobs", []):
            exp = parse_date(j.get("expiryDate"))
            if exp and exp < now:
                continue  # Himalayas asks API users to drop expired jobs
            locs = j.get("locationRestrictions") or []
            loc = ", ".join(l if isinstance(l, str) else (l or {}).get("name", "") for l in locs) or "Anywhere"
            sal = (f"{j.get('currency','')} {j.get('minSalary')}-{j.get('maxSalary')} {j.get('salaryPeriod') or 'annual'}".strip()
                   if j.get("minSalary") else None)
            yield _feed_job(feed, j.get("guid") or j.get("applicationLink"), j.get("companyName"), j.get("title"), loc,
                            j.get("pubDate"), j.get("applicationLink"),  # terms: Apply must use applicationLink
                            strip_html(j.get("description") or j.get("excerpt")), sal)
    elif feed == "remotive":
        for j in (data or {}).get("jobs", []):
            yield _feed_job(feed, j.get("id"), j.get("company_name"), j.get("title"),
                            j.get("candidate_required_location") or "Anywhere", j.get("publication_date"), j.get("url"),
                            strip_html(j.get("description")) + " " + " ".join(j.get("tags") or []), j.get("salary") or None)


def feed_queries(s) -> list[str]:
    """Search words for the feeds that take a query: the person's own role words, at most 3."""
    qs = s.get("feedQueries") or []
    if not qs:
        for p in s.get("titleRequireAny", []) + s.get("titleInclude", []):
            w = re.sub(r"\\[a-z]|[^A-Za-z0-9 +#.-]", " ", p).strip()
            if len(w) > 2 and w.lower() not in ("senior", "staff", "principal", "lead", "sr") and w not in qs:
                qs.append(w)
    return qs[:3]

# ---------- eligibility & scoring ----------

HARD_US = [
    r"must (?:reside|live|be (?:located|based)) in the (?:u\.?s\.?|united states)",
    r"\be-?verify\b", r"security clearance", r"\bclearance (?:is )?required\b",
    r"\bu\.?s\.? citizen", r"\bu\.?s\.? person", r"\bitar\b", r"\bfedramp\b",
    r"authori[sz]ed to work in the (?:u\.?s\.?|united states)(?! or)",
    r"(?:eastern|central|mountain|pacific) time zones?",
]
OPEN = [r"\banywhere\b", r"\bworldwide\b", r"\bglobal(?:ly)?\b", r"\bemea\b", r"\beurope\b", r"\beu\b",
        r"\bcet\b", r"\bcest\b", r"\bdistributed\b"]
US_PART = re.compile(r"(?<![a-z])(?:u\.?s\.?a?|united states|usa|americas?|north america)(?![a-z])", re.I)
CA_PART = re.compile(r"(?<![a-z])canada(?![a-z])", re.I)
GENERIC = re.compile(r"^(?:remote|fully remote|remote[- ]first|distributed|home[- ]based|work from home|anywhere)?$", re.I)
ONSITE = re.compile(r"\b(?:hybrid|on-?site|in[- ]office|office[- ]based)\b", re.I)
TZ_RANGE = re.compile(r"(?:utc|gmt)\s*([+\-−]\s*\d{1,2})?\s*(?:to|-|–)\s*(?:utc|gmt)\s*([+\-−]\s*\d{1,2})", re.I)


def _off(x):
    return int(x.replace("−", "-").replace(" ", "")) if x else 0


def split_location(loc: str) -> list[str]:
    """'Remote - Europe, Americas; London' -> ['europe', 'americas', 'london'] (generic 'remote' parts become '')."""
    parts = []
    for p in re.split(r"[;|/]|,(?![^()]*\))", loc):
        p = re.sub(r"\((?:remote|r)\)|\b(?:remote|fully|based)\b|[-–()]", " ", p, flags=re.I)
        parts.append(re.sub(r"\s+", " ", p).strip().lower())
    return parts or [""]


def work_mode(job) -> str:
    """remote | hybrid | onsite | unknown (from the ATS field first, then the location text)."""
    w = str(job.get("workplace") or "").lower().replace("_", "").replace("-", "")
    loc = job["location"].lower()
    if "hybrid" in w or re.search(r"\bhybrid\b", loc):
        return "hybrid"
    if w in ("onsite", "inoffice", "office") or re.search(r"\b(?:on-?site|in[- ]office|office[- ]based)\b", loc):
        return "remote" if job.get("remote_flag") else "onsite"
    if w == "remote" or job.get("remote_flag") or re.search(r"\b(remote|anywhere|distributed|home[- ]based|work from home)\b", loc):
        return "remote"
    return "unknown"


def workplace_ok(job, s) -> tuple[bool, str]:
    """search.json: "workplaces": ["remote", "hybrid", "onsite"], "commuteCities": ["Prague", "Berlin"].
    Hybrid/on-site roles are kept only if allowed AND located in one of the commute cities."""
    allowed = [w.lower() for w in s.get("workplaces", ["remote"])]
    mode = work_mode(job)
    if mode in ("remote", "unknown"):
        return True, mode
    if mode not in allowed:
        return False, mode
    cities = [c.lower() for c in s.get("commuteCities", [])]
    loc = job["location"].lower()
    return (any(c in loc for c in cities) if cities else False), mode


def is_onsite(job) -> bool:  # kept for older callers: True if not remote under remote-only settings
    return not workplace_ok(job, {"workplaces": ["remote"]})[0]


EU = ["austria", "belgium", "bulgaria", "croatia", "cyprus", "czechia", "czech republic", "denmark", "estonia",
      "finland", "france", "germany", "greece", "hungary", "ireland", "italy", "latvia", "lithuania", "luxembourg",
      "malta", "netherlands", "poland", "portugal", "romania", "slovakia", "slovenia", "spain", "sweden"]
EEA_EXTRA = ["norway", "iceland", "liechtenstein", "switzerland"]


def expand_authorized(auth: list[str]) -> list[str]:
    out = []
    for a in auth:
        a = a.lower().strip()
        if a in ("eu", "european union", "eea", "europe"):
            out += EU + (EEA_EXTRA if a != "eu" and a != "european union" else [])
        elif a in ("us", "usa", "u.s.", "united states"):
            out += ["united states"]
        else:
            out.append(a)
    return out


def classify(job, home: list[str], home_utc: float | None = None, authorized: list[str] | None = None,
             contractor_ok: bool = True) -> tuple[str, list[str]]:
    """Location fields decide first; description text only refines a generic 'Remote'.
    home       = names of where the person lives (country, city)
    authorized = countries/regions where they may be EMPLOYED directly ("EU", "United States", "Brazil", ...)
    A open to them · B foreign remote, no hard limits (contractor/EOR) · C hard limits · X locked elsewhere"""
    loc, text = job["location"], job["text"].lower()
    home_l = [h.lower() for h in home]
    auth = expand_authorized(authorized if authorized is not None else home)
    us_ok = "united states" in auth
    ca_ok = "canada" in auth
    hard = [] if us_ok else [p for p in HARD_US if re.search(p, text) or re.search(p, loc.lower())]
    tz = TZ_RANGE.search(loc) or TZ_RANGE.search(text)
    if tz and home_utc is not None and _off(tz.group(1)) <= home_utc <= _off(tz.group(2)):
        return "A", [f"time-zone range {tz.group(0)} includes home (UTC{home_utc:+g})"]
    parts = split_location(loc)
    kinds = []
    for p in parts:
        if any(h in p for h in home_l): kinds.append("home")
        elif any(re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", p) for a in auth): kinds.append("auth")
        elif any(re.search(o, p) for o in OPEN): kinds.append("open")
        elif GENERIC.match(p): kinds.append("generic")
        elif US_PART.search(p): kinds.append("auth" if us_ok else "us")
        elif CA_PART.search(p): kinds.append("auth" if ca_ok else "ca")
        else:
            c = country_of(p)
            if c and c in auth: kinds.append("auth")
            elif c == "united states": kinds.append("us")
            elif c == "canada": kinds.append("ca")
            else: kinds.append("other")
    if "home" in kinds or "auth" in kinds:
        return "A", [f"location fits where you can work ({loc})"]
    if "open" in kinds:
        return "A", [f"location: {loc}"]
    if hard and ("us" in kinds or set(kinds) <= {"generic"}):
        return "C", ["hard US signal: " + re.sub(r"\\[a-z]|[()?:]", "", hard[0])]
    if "us" in kinds and set(kinds) <= {"us", "ca", "generic"}:
        return ("B", [f"US-listed remote ({loc}), no hard limits found"]) if contractor_ok else ("X", [f"US-only ({loc})"])
    if "other" in kinds or "ca" in kinds:
        return "X", [f"limited to {loc}"]
    open_text = [o for o in OPEN if re.search(o, text)]
    if open_text:
        return "A", ["generic 'Remote'; description mentions " + open_text[0].replace("\\b", "")]
    return "B", [f"generic '{loc}' - check posting"]


def score(job, s) -> tuple[int, list[str]]:
    t, text = job["title"].lower(), job["text"].lower()
    pts, why = 0, []
    SENIORITY = re.compile(r"\b(senior|sr\.?|staff|principal|lead)\b", re.I)
    inc = [p for p in s.get("titleInclude", []) + s.get("titleRequireAny", []) if re.search(p, t, re.I)]
    role_hits = [p for p in inc if p.lower() not in ("senior", "staff", "principal", "lead")]
    if role_hits:
        pts += 20; why.append("role title match")
    if SENIORITY.search(t):
        pts += 10
    hits = [k for k in s.get("strongKeywords", []) if re.search(rf"\b{re.escape(k.lower())}\b", text + " " + t)]
    pts += min(40, 8 * len(hits))
    if hits: why.append("keywords: " + ", ".join(hits[:6]))
    stack = [k for k in s.get("stackKeywords", []) if re.search(rf"\b{re.escape(k.lower())}\b", text)]
    pts += min(20, 5 * len(stack))
    if stack: why.append("stack: " + ", ".join(stack[:5]))
    if job.get("salary"):
        pts += 5; why.append(f"pay: {job['salary']}")
    if job["age_days"] is not None and job["age_days"] <= 7:
        pts += 5; why.append("posted this week")
    gap = language_gap(job["text"], s.get("languages"))
    if gap:
        job["language_gap"] = gap
        pts -= 25; why.append("requires " + ", ".join(gap) + " (not in your languages)")
    return max(0, min(pts, 100)), why


LANGS = {"german": r"german|deutsch", "french": r"french|fran[cç]ais", "dutch": r"dutch|nederlands", "spanish": r"spanish|espa[nñ]ol",
         "italian": r"italian|italiano", "portuguese": r"portuguese|portugu[eê]s", "polish": r"polish|polski",
         "czech": r"czech|[cč]e[sš]tina", "swedish": r"swedish|svenska", "danish": r"danish|dansk", "norwegian": r"norwegian|norsk",
         "finnish": r"finnish|suomi", "hungarian": r"hungarian|magyar", "romanian": r"romanian", "greek": r"greek",
         "japanese": r"japanese", "mandarin": r"mandarin|chinese", "korean": r"korean", "arabic": r"arabic",
         "hebrew": r"hebrew", "russian": r"russian", "ukrainian": r"ukrainian", "turkish": r"turkish", "english": r"english"}
_NEED = r"(?:fluent|fluency|native|mother tongue|business[- ]level|professional[- ]level|proficien\w*|excellent|strong|perfect|written and spoken|spoken and written|\bc1\b|\bc2\b|required|requirement|must|essential|mandatory|flie(?:ß|ss)end|verhandlungssicher)"
_SOFT = re.compile(r"\b(?:plus|nice[- ]to[- ]have|bonus|advantage|advantageous|preferred|desirable|beneficial|helpful|ideally)\b", re.I)


def language_gap(text: str, languages) -> list[str]:
    """Languages a posting REQUIRES that the person didn't list (search.json "languages"). Only when the
    sentence says fluent/native/C1/required etc. and not 'a plus'/'nice to have'. Unset -> no check."""
    if not languages:
        return []
    have = {l.lower().strip() for l in languages}
    gaps = []
    for sent in re.split(r"(?<=[.!?;•\n])\s+|\s[-–•]\s", text or ""):
        if _SOFT.search(sent) or not re.search(_NEED, sent, re.I):
            continue
        for lang, pat in LANGS.items():
            if lang not in have and lang not in gaps and re.search(rf"\b(?:{pat})\b", sent, re.I):
                gaps.append(lang.title())
    return gaps

# ---------- main ----------

def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


_SUFFIX = re.compile(r"\b(inc|llc|ltd|limited|gmbh|ag|sa|s\.a\.|bv|b\.v\.|plc|co|corp|corporation|technologies|technology|labs|hq|io|ai|app)\b\.?", re.I)


def slug_candidates(company: str) -> list[str]:
    """Likely board slugs for a company name: 'Acme Labs, Inc.' -> ['acmelabs', 'acme-labs', 'acme']."""
    base = re.sub(r"[^a-z0-9 ]+", " ", company.lower()).split()
    core = re.sub(r"[^a-z0-9 ]+", " ", _SUFFIX.sub(" ", company.lower())).split()
    out = []
    for words in (base, core):
        for v in ("".join(words), "-".join(words)):
            if v and len(v) >= 2 and v not in out:
                out.append(v)
    return out[:4]


def discover_boards(names, known, title_ok, fetch=None, limit=30, delay=0.5):
    """Probe Ashby/Greenhouse/Lever for companies seen in the job feeds. Returns new board entries whose board
    currently lists at least one title-matching job. Only public board endpoints are touched."""
    fetch = fetch or fetch_json
    found, probed = [], 0
    for name in names:
        if probed >= limit:
            break
        probed += 1
        for slug in slug_candidates(name):
            hit = None
            for ats in ("ashby", "greenhouse", "lever"):
                if f"{ats}:{slug}" in known:
                    hit = "known"; break
                try:
                    raw = fetch(ENDPOINTS[ats].format(slug=slug))
                except Exception:
                    continue
                titles = [j["title"] for j in NORMALISERS[ats](name, raw)]
                if titles:
                    hit = (ats, sum(1 for t in titles if title_ok(t)))
                    break
                if delay:
                    time.sleep(delay)
            if hit == "known":
                break
            if hit:
                ats, n = hit
                if n:
                    found.append({"name": name, "ats": ats, "slug": slug, "added": dt.date.today().isoformat(),
                                  "via": "discover"})
                known.add(f"{ats}:{slug}")
                break
    return found


def main():
    os.umask(0o077)  # everything written into the private data folder is owner-only
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="data folder (default: configured one)")
    ap.add_argument("--fixtures", help="read <ats>-<slug>.json files from this dir instead of the network")
    ap.add_argument("--no-save", action="store_true", help="don't update seen.json")
    ap.add_argument("--all", action="store_true", help="include jobs already seen")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between companies (be polite)")
    ap.add_argument("--no-feeds", action="store_true", help="skip the free aggregators this run")
    ap.add_argument("--discover", action="store_true",
                    help="probe job boards of companies seen in the feeds and add matching ones to companies.json")
    ap.add_argument("--discover-max", type=int, default=30, help="max companies to probe per run")
    ap.add_argument("--quiet-days", type=int, default=60,
                    help="report boards with no title-matching posting for this many days")
    a = ap.parse_args()

    from jf_config import data_dir
    data = data_dir(a.data)
    s = load_json(data / "search.json", None) or load_json(ROOT / "templates/search.json", {})
    companies = load_json(data / "companies.json", None) or load_json(ROOT / "config/companies.json", [])
    if isinstance(companies, dict):
        companies = companies.get("companies", [])
    board_state_p = data / "board_state.json"
    board_state = load_json(board_state_p, {})
    feed_companies = {}  # company name -> count of title-matching feed jobs (for --discover)
    seen = set(load_json(data / "seen.json", []))
    tracked = set()
    if (data / "tracker.csv").exists():
        with open(data / "tracker.csv", newline="") as f:
            tracked = {r.get("link", "") for r in csv.DictReader(f)}

    now = dt.datetime.now(dt.timezone.utc)
    max_age = s.get("maxAgeDays", 14)
    exclude = [re.compile(p, re.I) for p in s.get("titleExclude", [])]
    require = [re.compile(p, re.I) for p in s.get("titleRequireAny", [])]
    home = s.get("homeCountry", [])
    keep_groups = set(s.get("keepGroups", ["A", "B"]))

    out, errors, not_polled, feed_notes, counts = [], [], [], [], {"jobs": 0, "fresh": 0}
    dedupe = set() if a.all else {normalize_url(u) for u in tracked if u}

    excl_cos = [e.lower() for e in s.get("excludeCompanies", [])]

    def title_ok(t):
        return not any(p.search(t) for p in exclude) and (not require or any(p.search(t) for p in require))

    def consider(j, key):
        """One filter pipeline for boards and feeds: age, title, workplace, seen, eligibility, score."""
        counts["jobs"] += 1
        if excl_cos and any(e == j["company"].lower().strip() for e in excl_cos):
            return
        j["url"] = normalize_url(j["url"])
        if not j["url"].startswith("https://"):
            return
        posted = parse_date(j["posted"])
        j["age_days"] = (now - posted).days if posted else None
        j["posted"] = posted.date().isoformat() if posted else None
        if j["age_days"] is None or j["age_days"] > max_age:
            return
        if any(p.search(j["title"]) for p in exclude):
            return
        if require and not any(p.search(j["title"]) for p in require):
            return
        ok_wp, j["work_mode"] = workplace_ok(j, s)
        if not ok_wp:
            return
        counts["fresh"] += 1
        same = (j["company"].lower().strip(), re.sub(r"\W+", " ", j["title"].lower()).strip())
        if j["url"] in dedupe or same in dedupe:  # same job from a board and a feed, or two feeds
            return
        if not a.all and key in seen:
            return
        j["group"], j["eligibility"] = classify(j, home, s.get("homeUtcOffset"), s.get("authorized"),
                                             s.get("contractorOK", True))
        if j["group"] not in keep_groups:
            return
        j["prescore"], j["why"] = score(j, s)
        j["key"] = key
        dedupe.update({j["url"], same})
        # keep the full description: it is what Claude scores and tailors from (career pages often need JS)
        out.append(j)

    for c in companies:
        if c.get("disabled"):
            continue
        name, ats, slug = c["name"], c["ats"], c["slug"]
        if ats in NOT_POLLABLE or (c.get("polled") is False and ats not in ENDPOINTS):
            not_polled.append(f"{name} ({ats})"); continue
        if ats not in ENDPOINTS or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", str(slug)):
            errors.append(f"{name} ({ats}/{slug}): invalid board type or slug - skipped"); continue
        try:
            if a.fixtures:
                fp = Path(a.fixtures) / f"{ats}-{slug}.{'xml' if ats in RAW_TEXT else 'json'}"
                raw = fp.read_text() if ats in RAW_TEXT else json.loads(fp.read_text())
            else:
                raw = fetch_json(ENDPOINTS[ats].format(slug=slug), raw=ats in RAW_TEXT)
                time.sleep(a.delay)
        except Exception as e:  # report, never crash the whole run
            errors.append(f"{name} ({ats}/{slug}): {e}"); continue
        jobs = list(NORMALISERS[ats](name, raw, slug) if ats == "personio" else NORMALISERS[ats](name, raw))
        st = board_state.setdefault(f"{ats}:{slug}", {})
        st["checked"] = now.date().isoformat()
        latest = max((d for d in (parse_date(j["posted"]) for j in jobs if title_ok(j["title"])) if d), default=None)
        if latest and latest.date().isoformat() > st.get("last_match", ""):
            st["last_match"] = latest.date().isoformat()
        for j in jobs:
            consider(j, f"{ats}:{slug}:{j['id']}")

    # ---- free aggregators: once per run, polite intervals, credit kept on every job ----
    feeds = [f for f in (s.get("feeds") if "feeds" in s else list(FEEDS)) if f in FEEDS] if not a.no_feeds else []
    state_p = data / "feeds_state.json"
    state = load_json(state_p, {})
    for f in feeds:
        url, min_h, credit = FEEDS[f]
        last = parse_date(state.get(f))
        if not a.fixtures and last and (now - last).total_seconds() < min_h * 3600:
            feed_notes.append(f"{credit}: skipped (fetched under {min_h}h ago - be polite)"); continue
        try:
            if a.fixtures:
                fp = Path(a.fixtures) / f"feed-{f}.json"
                if not fp.exists():
                    continue
                payloads = [json.loads(fp.read_text())]
            else:
                qs = feed_queries(s) if "{q}" in url else [""]
                from urllib.parse import quote
                payloads = []
                for q in qs or [""]:
                    payloads.append(fetch_json(url.format(q=quote(q))))
                    time.sleep(a.delay)
                state[f] = now.isoformat()
        except Exception as e:
            errors.append(f"{credit}: {e}"); continue
        n_before = len(out)
        for raw in payloads:
            for j in norm_feed(f, raw, now):
                if title_ok(j["title"]) and j["company"] not in ("", "?"):
                    feed_companies[j["company"]] = feed_companies.get(j["company"], 0) + 1
                consider(j, f"{f}:{j['id']}")
        feed_notes.append(f"{credit}: {len(out) - n_before} new")
    if feeds and not a.fixtures:
        state_p.write_text(json.dumps(state, indent=1))

    # ---- grow the list: boards of companies that showed up in the feeds ----
    discovered = []
    if a.discover and not a.fixtures and feed_companies:
        known = {f"{c.get('ats')}:{c.get('slug')}" for c in companies}
        known_names = {c.get("name", "").lower() for c in companies}
        excluded = [e.lower() for e in s.get("excludeCompanies", [])]
        names = [n for n, _ in sorted(feed_companies.items(), key=lambda x: -x[1])
                 if n.lower() not in known_names and not any(e in n.lower() for e in excluded)]
        discovered = discover_boards(names, known, title_ok, limit=a.discover_max, delay=a.delay / 2)
        if discovered:
            cp = data / "companies.json"
            cur = load_json(cp, None)
            if cur is None:  # first time: start from the list we polled
                cur = {"companies": companies}
            lst = cur["companies"] if isinstance(cur, dict) else cur
            lst.extend(discovered)
            cp.write_text(json.dumps(cur, indent=1, ensure_ascii=False))
    if not a.fixtures:
        board_state_p.write_text(json.dumps(board_state, indent=1, sort_keys=True))
    cutoff = (now - dt.timedelta(days=a.quiet_days)).date().isoformat()
    quiet = [f"{c['name']} ({c['ats']})" for c in companies if not c.get("disabled")
             and board_state.get(f"{c['ats']}:{c['slug']}", {}).get("checked")
             and board_state.get(f"{c['ats']}:{c['slug']}", {}).get("last_match", "") < cutoff]

    out.sort(key=lambda j: (-j["prescore"], j["age_days"] or 99))
    (data / "candidates").mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y-%m-%d")
    (data / "candidates" / f"{stamp}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    if not a.no_save and not a.fixtures:
        (data / "seen.json").write_text(json.dumps(sorted(seen | {j["key"] for j in out}), indent=0))

    print(f"{len(companies)} companies + {len(feeds)} job feeds, {counts['jobs']} jobs, {counts['fresh']} fresh & title-matched, {len(out)} new candidates")
    shown = [j for j in out if j["prescore"] >= s.get("minPrescore", 0)]
    print(f"showing {len(shown)} with prescore >= {s.get('minPrescore', 0)} (all {len(out)} are in the saved file)")
    for j in shown[:40]:
        via = f"  [via {j['source'].split(' (')[0]}]" if j.get("source") else ""
        print(f"{j['prescore']:>3}  {j['group']}  {j['posted']}  {j['company'][:18]:<18} {j['title'][:60]:<60} {j['location'][:35]}{via}")
    if feed_notes:
        print("\nJob feeds (credit them, with a link, when you show these jobs): " + "; ".join(feed_notes))
    if errors:
        print("\nBoards that failed (fix slug or remove):", *errors, sep="\n  ")
    if not_polled:
        print(f"\nNot polled automatically ({len(not_polled)}; check their career pages with web fetch): " + ", ".join(not_polled[:15]))
    if discovered:
        print(f"\nNew boards added to companies.json ({len(discovered)}): "
              + ", ".join(f"{d['name']} ({d['ats']})" for d in discovered) + " - they're polled from the next run")
    if quiet:
        print(f"\nQuiet boards (no matching posting in {a.quiet_days} days; consider \"disabled\": true): "
              + ", ".join(quiet[:25]) + (" ..." if len(quiet) > 25 else ""))
    print(f"\nSaved: {data / 'candidates' / (stamp + '.json')}")


if __name__ == "__main__":
    sys.exit(main())
