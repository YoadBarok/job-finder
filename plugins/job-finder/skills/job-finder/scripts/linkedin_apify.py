#!/usr/bin/env python3
"""Build the input for an optional, paid LinkedIn job search through an Apify Actor (no login, no cookies).

    python3 linkedin_apify.py --data <DATA> [--max 200]

Prints the Actor name, the exact input JSON and the most it can cost, for the person to approve. Claude then runs it
with the Apify connector (hard cost cap = the printed maximum), saves the dataset items to a file and imports them:

    python3 poll_boards.py --data <DATA> --import <file.json> --no-feeds

The Actor reads LinkedIn's public job search, the one anyone sees without signing in. Never give it (or any tool)
the person's LinkedIn cookies, session or password. LinkedIn's terms forbid automated access; the person decides.
"""
import argparse, json, re, sys
from pathlib import Path

ACTOR = "cheap_scraper/linkedin-job-scraper"
PRICE_PER_JOB = 0.0007   # USD, Apify free tier, checked 2026-11-27 - re-check the Actor's pricing before each run
PRICE_START = 0.005
WORKTYPE = {"remote": "remote", "hybrid": "hybrid", "onsite": "on-site"}


def plain_words(patterns):
    """Regex title patterns -> plain words the Actor understands ('\\bvp\\b' -> 'vp'); drop ones that aren't words."""
    out = []
    for p in patterns or []:
        w = re.sub(r"\\b|\\|[()?*+^$\[\]]", "", p).replace(".", " ").strip()
        if w and re.fullmatch(r"[A-Za-z0-9 #+/-]{2,40}", w) and w.lower() not in out:
            out.append(w.lower())
    return out


def build_input(s: dict, max_items: int = 200) -> dict:
    keywords = s.get("linkedinKeywords") or s.get("feedQueries") or []
    if not keywords:
        keywords = [w for w in plain_words(s.get("titleRequireAny", []) + s.get("titleInclude", []))
                    if w not in ("senior", "staff", "principal", "lead", "sr")]
    home = (s.get("homeCountry") or [""])[0]
    return {
        "keyword": keywords[:5],
        # The person's own country: LinkedIn lists remote roles open to that country there. Region-wide searches
        # ("European Union") mostly return city-tied office roles elsewhere, because LinkedIn ignores the
        # remote filter on them.
        "locations": s.get("linkedinLocations") or ([home] if home else []),
        "publishedAt": "r604800",  # past week
        "workType": [WORKTYPE[w] for w in s.get("workplaces", ["remote"]) if w in WORKTYPE],
        "experienceLevel": s.get("linkedinExperience", ["mid-senior"]),
        "jobTitleExclude": plain_words(s.get("titleExclude", []))[:40],
        "companyExclude": s.get("excludeCompanies", []),
        "maxItems": max_items,
        "saveOnlyUniqueItems": True,
        "enrichCompanyData": False,
    }


def max_cost(max_items: int) -> float:
    return round(max_items * PRICE_PER_JOB + PRICE_START, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    ap.add_argument("--max", type=int, default=200, help="most jobs to collect (sets the cost cap)")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).parent))
    from jf_config import data_dir
    data = data_dir(a.data)
    s = json.loads((data / "search.json").read_text())
    inp = build_input(s, a.max)
    print(json.dumps({"actor": ACTOR, "maxTotalChargeUsd": max_cost(a.max), "input": inp}, indent=1))
    print(f"\nAt most {a.max} jobs, at most USD {max_cost(a.max)} (re-check the Actor's current price first). "
          f"Ask the person before running; log the run in apify-runs.csv.", file=sys.stderr)


if __name__ == "__main__":
    main()
