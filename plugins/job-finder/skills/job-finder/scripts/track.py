#!/usr/bin/env python3
"""The only way to change tracker.csv (so rows stay consistent).

  python3 scripts/track.py add --company ClickUp --role "Senior Backend Engineer, IAM" --link URL \
        --score 84 --source "poll_boards (ashby)" --status cv-ready [--note "..."] [--cost 0]
  python3 scripts/track.py set --link URL --status applied [--note "follow up 2026-12-08"]
  python3 scripts/track.py list [--status applied]

Columns: company,role,link,score,date_found,source,cost_usd,status,updated,note
Status:  found | cv-ready | applied | interviewing | offer | rejected | skipped | withdrawn
Source:  pasted | poll_boards (<board>) | feed (<feed>) | web search | apify (<actor>) | linkedin (pasted) | referral
Older trackers (free-text status, fewer columns) are migrated in place on first write.
"""
import argparse, csv, datetime as dt, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jf_config import data_dir  # noqa: E402

COLS = ["company", "role", "link", "score", "date_found", "source", "cost_usd", "status", "updated", "note"]
STATUSES = ["found", "cv-ready", "applied", "interviewing", "offer", "rejected", "skipped", "withdrawn"]
SOURCE = re.compile(r"^(pasted|web search|referral|linkedin \(pasted\)|"
                    r"poll_boards \((greenhouse|ashby|lever|workable|recruitee|personio)\)|"
                    r"feed \((arbeitnow|jobicy|remoteok|himalayas|remotive)\)|apify \([\w./-]+\))$")


def today():
    return dt.date.today().isoformat()


def load(p: Path):
    if not p.exists():
        return []
    rows = list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    for r in rows:  # migrate free-text statuses like "applied 2026-11-24 (follow up ...)"
        st = (r.get("status") or "").strip()
        m = re.match(r"^([a-z-]+)\b\s*(.*)$", st)
        if m and m.group(1) in STATUSES and m.group(2):
            r["status"], extra = m.group(1), m.group(2).strip(" ()")
            r["note"] = "; ".join(x for x in [r.get("note") or "", extra] if x)
        elif st and st not in STATUSES:
            r["note"] = "; ".join(x for x in [r.get("note") or "", st] if x); r["status"] = "found"
        for c in COLS:
            r.setdefault(c, "")
    return rows


def safe_cell(v):
    """Neutralise spreadsheet formulas: a job title like '=HYPERLINK(...)' must stay text in Excel/Numbers."""
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") and not re.fullmatch(r"-?\d+(\.\d+)?", v) else v


def save(p: Path, rows):
    os.umask(0o077)
    rows = [{k: safe_cell(r.get(k, "")) for k in COLS} for r in rows]
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore"); w.writeheader(); w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["add", "set", "list"])
    ap.add_argument("--data"); ap.add_argument("--company"); ap.add_argument("--role"); ap.add_argument("--link")
    ap.add_argument("--score", type=int); ap.add_argument("--source"); ap.add_argument("--status")
    ap.add_argument("--note"); ap.add_argument("--cost", type=float, default=0.0)
    a = ap.parse_args()
    p = data_dir(a.data) / "tracker.csv"
    rows = load(p)
    if a.status and a.status not in STATUSES:
        sys.exit(f"status must be one of: {', '.join(STATUSES)}")

    if a.cmd == "list":
        for r in rows:
            if not a.status or r["status"] == a.status:
                print(f"{r['status']:<12} {r['score']:>3}  {r['company'][:16]:<16} {r['role'][:50]:<50} {r['note'][:40]}")
        return

    if not a.link:
        sys.exit("--link is required")
    match = [r for r in rows if r["link"] == a.link]

    if a.cmd == "add":
        if a.source and not SOURCE.match(a.source):
            sys.exit("--source must be one of: pasted | web search | referral | linkedin (pasted) | "
                     "poll_boards (greenhouse|ashby|lever|workable|recruitee|personio) | feed (<arbeitnow|jobicy|remoteok|himalayas|remotive>) | apify (<actor>)")
        if match:
            sys.exit(f"already tracked: {a.link} (use `set` to update)")
        if not (a.company and a.role and a.source and a.status):
            sys.exit("add needs --company --role --source --status")
        rows.append({"company": a.company, "role": a.role, "link": a.link, "score": a.score if a.score is not None else "",
                     "date_found": today(), "source": a.source, "cost_usd": f"{a.cost:g}", "status": a.status,
                     "updated": today(), "note": a.note or ""})
    else:  # set
        if not match:
            sys.exit(f"not tracked: {a.link} (use `add`)")
        r = match[0]
        if a.status: r["status"] = a.status
        if a.score is not None: r["score"] = a.score
        if a.note: r["note"] = "; ".join(x for x in [r["note"], a.note] if x)
        r["updated"] = today()
    save(p, rows)
    print(f"tracker updated: {p}")


if __name__ == "__main__":
    main()
