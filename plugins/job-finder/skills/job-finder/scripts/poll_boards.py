#!/usr/bin/env python3
"""Poll companies' public job boards (Greenhouse, Ashby, Lever) for fresh remote roles.

Free: these are the public JSON endpoints the career pages themselves use. No login, no scraping.

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

ROOT = Path(__file__).resolve().parent.parent  # skill folder
UA = "job-finder/1.0 (personal job search; polite polling)"

ENDPOINTS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json",
}

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
    if isinstance(v, (int, float)):  # Lever: epoch ms
        return dt.datetime.fromtimestamp(v / 1000, tz=dt.timezone.utc)
    try:
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_json(url: str, retries: int = 2):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
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


NORMALISERS = {"greenhouse": norm_greenhouse, "ashby": norm_ashby, "lever": norm_lever}

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


def is_onsite(job) -> bool:
    if ONSITE.search(job["location"]):
        return True
    w = str(job.get("workplace") or "").lower()
    return w in ("onsite", "on-site", "hybrid") and not job.get("remote_flag")


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
    inc = [p for p in s.get("titleInclude", []) if re.search(p, t)]
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
    return min(pts, 100), why

# ---------- main ----------

def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def main():
    os.umask(0o077)  # everything written into the private data folder is owner-only
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="data folder (default: configured one)")
    ap.add_argument("--fixtures", help="read <ats>-<slug>.json files from this dir instead of the network")
    ap.add_argument("--no-save", action="store_true", help="don't update seen.json")
    ap.add_argument("--all", action="store_true", help="include jobs already seen")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between companies (be polite)")
    a = ap.parse_args()

    from jf_config import data_dir
    data = data_dir(a.data)
    s = load_json(data / "search.json", None) or load_json(ROOT / "templates/search.json", {})
    companies = load_json(data / "companies.json", None) or load_json(ROOT / "config/companies.json", [])
    if isinstance(companies, dict):
        companies = companies.get("companies", [])
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

    out, errors, counts = [], [], {"jobs": 0, "fresh": 0}
    for c in companies:
        if c.get("disabled"):
            continue
        name, ats, slug = c["name"], c["ats"], c["slug"]
        if ats not in ENDPOINTS or not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", str(slug)):
            errors.append(f"{name} ({ats}/{slug}): invalid board type or slug - skipped"); continue
        try:
            if a.fixtures:
                fp = Path(a.fixtures) / f"{ats}-{slug}.json"
                raw = json.loads(fp.read_text())
            else:
                raw = fetch_json(ENDPOINTS[ats].format(slug=slug))
                time.sleep(a.delay)
        except Exception as e:  # report, never crash the whole run
            errors.append(f"{name} ({ats}/{slug}): {e}"); continue
        for j in NORMALISERS[ats](name, raw):
            counts["jobs"] += 1
            j["url"] = normalize_url(j["url"])
            posted = parse_date(j["posted"])
            j["age_days"] = (now - posted).days if posted else None
            j["posted"] = posted.date().isoformat() if posted else None
            if j["age_days"] is None or j["age_days"] > max_age:
                continue
            if any(p.search(j["title"]) for p in exclude):
                continue
            if require and not any(p.search(j["title"]) for p in require):
                continue
            if is_onsite(j):
                continue
            counts["fresh"] += 1
            key = f"{ats}:{slug}:{j['id']}"
            if not a.all and (key in seen or j["url"] in tracked):
                continue
            j["group"], j["eligibility"] = classify(j, home, s.get("homeUtcOffset"), s.get("authorized"),
                                                 s.get("contractorOK", True))
            if j["group"] not in keep_groups:
                continue
            j["prescore"], j["why"] = score(j, s)
            j["key"] = key
            # keep the full description: it is what Claude scores and tailors from (career pages often need JS)
            out.append(j)

    out.sort(key=lambda j: (-j["prescore"], j["age_days"] or 99))
    (data / "candidates").mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y-%m-%d")
    (data / "candidates" / f"{stamp}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    if not a.no_save and not a.fixtures:
        (data / "seen.json").write_text(json.dumps(sorted(seen | {j["key"] for j in out}), indent=0))

    print(f"{len(companies)} companies, {counts['jobs']} jobs, {counts['fresh']} fresh & title-matched, {len(out)} new candidates")
    shown = [j for j in out if j["prescore"] >= s.get("minPrescore", 0)]
    print(f"showing {len(shown)} with prescore >= {s.get('minPrescore', 0)} (all {len(out)} are in the saved file)")
    for j in shown[:40]:
        print(f"{j['prescore']:>3}  {j['group']}  {j['posted']}  {j['company'][:18]:<18} {j['title'][:60]:<60} {j['location'][:35]}")
    if errors:
        print("\nBoards that failed (fix slug or remove):", *errors, sep="\n  ")
    print(f"\nSaved: {data / 'candidates' / (stamp + '.json')}")


if __name__ == "__main__":
    sys.exit(main())
