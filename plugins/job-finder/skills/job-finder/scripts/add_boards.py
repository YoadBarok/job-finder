#!/usr/bin/env python3
"""Grow the person's company list from job-posting URLs (found by web search or pasted).

  python3 add_boards.py --data <DATA> URL [URL ...]
  python3 add_boards.py --data <DATA> --from-file urls.txt

Recognises the employer's own job-board systems and adds each new board to DATA/companies.json:
  Greenhouse  boards.greenhouse.io/<slug>, job-boards.greenhouse.io/<slug>, boards-api.greenhouse.io/v1/boards/<slug>
  Ashby       jobs.ashbyhq.com/<slug>
  Lever       jobs.lever.co/<slug>  (also jobs.eu.lever.co)
  Workable    apply.workable.com/<slug>
  SmartRecruiters  jobs.smartrecruiters.com/<slug>, careers.smartrecruiters.com/<slug>
  Recruitee   <slug>.recruitee.com
  Personio    <slug>.jobs.personio.de / .com
  Teamtailor  <slug>.teamtailor.com
Greenhouse, Ashby, Lever, Workable, Recruitee and Personio are polled automatically; SmartRecruiters and
Teamtailor are stored for the agent to read with web fetch ("polled": false). Nothing is fetched by this script.
"""
import argparse, json, os, re, sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jf_config import data_dir  # noqa: E402

POLLED = {"greenhouse", "ashby", "lever", "workable", "recruitee", "personio"}
SLUG = r"([A-Za-z0-9][A-Za-z0-9._-]{0,79})"
PATTERNS = [
    ("greenhouse", re.compile(rf"^(?:job-)?boards(?:\.eu)?\.greenhouse\.io$"), re.compile(rf"^/{SLUG}(?:/|$)")),
    ("greenhouse", re.compile(r"^boards-api\.greenhouse\.io$"), re.compile(rf"^/v1/boards/{SLUG}(?:/|$)")),
    ("ashby", re.compile(r"^jobs\.ashbyhq\.com$"), re.compile(rf"^/{SLUG}(?:/|$)")),
    ("lever", re.compile(r"^jobs(?:\.eu)?\.lever\.co$"), re.compile(rf"^/{SLUG}(?:/|$)")),
    ("workable", re.compile(r"^apply\.workable\.com$"), re.compile(rf"^/{SLUG}(?:/|$)")),
    ("smartrecruiters", re.compile(r"^(?:jobs|careers)\.smartrecruiters\.com$"), re.compile(rf"^/{SLUG}(?:/|$)")),
]
SUBDOMAIN = [
    ("recruitee", re.compile(rf"^{SLUG}\.recruitee\.com$")),
    ("personio", re.compile(rf"^{SLUG}\.jobs\.personio\.(?:de|com)$")),
    ("teamtailor", re.compile(rf"^{SLUG}\.teamtailor\.com$")),
]
NOT_SLUGS = {"embed", "api", "jobs", "job", "v1", "boards", "careers", "en", "de", "j", "o", "p"}


def parse(url: str):
    """URL -> (ats, slug) or None."""
    try:
        sp = urlsplit(url.strip())
    except ValueError:
        return None
    if sp.scheme not in ("http", "https"):
        return None
    host = (sp.hostname or "").lower()
    for ats, hrx, prx in PATTERNS:
        if hrx.match(host):
            m = prx.match(sp.path or "/")
            if m and m.group(1).lower() not in NOT_SLUGS:
                return ats, m.group(1)
            if ats == "greenhouse" and "for=" in (sp.query or ""):  # boards.greenhouse.io/embed/job_board?for=<slug>
                q = re.search(rf"(?:^|&)for={SLUG}", sp.query)
                if q:
                    return ats, q.group(1)
            return None
    for ats, hrx in SUBDOMAIN:
        m = hrx.match(host)
        if m and m.group(1).lower() not in ("www", "careers", "jobs"):
            return ats, m.group(1)
    return None


def main():
    os.umask(0o077)
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*"); ap.add_argument("--from-file"); ap.add_argument("--data")
    ap.add_argument("--why", default="discovered from a job posting")
    a = ap.parse_args()
    urls = list(a.urls)
    if a.from_file:
        urls += [l.strip() for l in Path(a.from_file).read_text().splitlines() if l.strip()]
    data = data_dir(a.data)
    path = data / "companies.json"
    cur = json.loads(path.read_text()) if path.exists() else []
    if isinstance(cur, dict):
        cur = cur.get("companies", [])
    if not cur:  # first time: start from the starter list so it isn't lost
        starter = json.loads((Path(__file__).resolve().parent.parent / "config/companies.json").read_text())
        cur = starter.get("companies", starter) if isinstance(starter, dict) else starter
    have = {(c["ats"], c["slug"].lower()) for c in cur}
    added, skipped = [], []
    for u in urls:
        r = parse(u)
        if not r:
            skipped.append(u); continue
        ats, slug = r
        if (ats, slug.lower()) in have:
            continue
        have.add((ats, slug.lower()))
        entry = {"name": slug.replace("-", " ").replace("_", " ").title(), "ats": ats, "slug": slug,
                 "why": a.why, "verified": False}
        if ats not in POLLED:
            entry["polled"] = False
        cur.append(entry); added.append(f"{ats}/{slug}")
    path.write_text(json.dumps(cur, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({"added": added, "not_recognised": skipped, "total": len(cur)}, indent=1))


if __name__ == "__main__":
    main()
