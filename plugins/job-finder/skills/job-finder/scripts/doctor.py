#!/usr/bin/env python3
"""Readiness check: is this machine and data folder ready for the job-finder agent?

  python3 <skill>/scripts/doctor.py            # human-readable checklist
  python3 <skill>/scripts/doctor.py --json     # for Claude: machine-readable

Each check is REQUIRED (the agent can't work without it), RECOMMENDED (works, but worse), or
OPTIONAL (an integration you may add). Every failed check comes with the exact fix.
Exit code 1 if any REQUIRED check fails.
"""
import json, os, re, shutil, subprocess, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # skill folder
SCRIPTS = ROOT / "scripts"
CFG = f"python3 \"{SCRIPTS}/configure.py\""
results = []


def check(level, name, ok, fix="", detail=""):
    results.append({"level": level, "name": name, "ok": bool(ok), "fix": fix, "detail": detail})


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20, cwd=ROOT).returncode == 0
    except Exception:
        return False


def main():
    as_json = "--json" in sys.argv
    mac = sys.platform == "darwin"

    # ---- data folder ----
    sys.path.insert(0, str(SCRIPTS))
    from jf_config import data_dir, configured
    data = data_dir()
    if configured():
        check("REQUIRED", "Data folder chosen", True, detail=str(data))
    else:
        from jf_config import find_data_folders
        found = find_data_folders()
        if found:
            fix = ("CLAUDE: found existing job-finder data at: " + "; ".join(found) + ". Ask the user to confirm which "
                   "one is theirs (or that they want a new one), then run `" + CFG + " --data <path>` and "
                   "ask them to type `/add-dir <path>` once")
        else:
            fix = ("CLAUDE: no existing data folder found. Ask: 'Have you used job-finder before, e.g. on another machine? "
                   "Where is that data?' If not, suggest ~/job-finder-data (or an iCloud/Dropbox folder to share across "
                   "machines), then run `" + CFG + " --data <path>` and ask them to type `/add-dir <path>` once")
        check("REQUIRED", "Data folder chosen", False, fix, detail="; ".join(found))
    if configured():
        check("REQUIRED", "Data folder exists", data.is_dir(), f"CLAUDE: run `{CFG} --data {data}`")
        if ROOT in data.resolve().parents:
            check("REQUIRED", "Data folder is outside the repo", False, "Move it out; personal data must never be in git")
        files = {
            "criteria.md": "the user's rules",
            "search.json": "poller filters",
            "base/cv.base.json": "the approved base CV",
            "apply_profile.json": "form answers",
        }
        missing = [f for f in files if not (data / f).exists()]
        check("REQUIRED", "Data files present", not missing,
              f"CLAUDE: run `{CFG} --data {data}` (adds missing templates, never overwrites)",
              detail=", ".join(missing))
        tmpl = []
        if (data / "base/cv.base.json").exists() and "ALEX EXAMPLE" in (data / "base/cv.base.json").read_text():
            tmpl.append("base/cv.base.json")
        if (data / "apply_profile.json").exists() and '"Alex"' in (data / "apply_profile.json").read_text():
            tmpl.append("apply_profile.json")
        if (data / "search.json").exists() and "Your Country" in (data / "search.json").read_text():
            tmpl.append("search.json")
        if (data / "criteria.md").exists():
            ct = (data / "criteria.md").read_text()
            if "(template" in ct or re.search(r"\bTBD\b", ct):
                tmpl.append("criteria.md (template or TBD answers)")
        check("REQUIRED", "Data filled in (not templates)", not tmpl,
              "CLAUDE: run the setup interview (skill section 0) to fill: " + ", ".join(tmpl), detail=", ".join(tmpl))
        check("RECOMMENDED", "forbidden_terms.txt lists real internal names",
              (data / "forbidden_terms.txt").exists() and any(l.strip() and not l.startswith("#") and l.strip() not in ("internal-service-name", "TEAM-123")
                                                            for l in (data / "forbidden_terms.txt").read_text().splitlines()),
              "CLAUDE: ask for the employers' internal names (services, teams, ticket prefixes) and write them, one per line")
        check("RECOMMENDED", "base/base.pdf present", (data / "base/base.pdf").exists(),
              "CLAUDE: copy the user's current CV PDF to base/base.pdf")
        copies = sorted({str(c.parents[1]) for pat in ("*/tools/poll_boards.py", "*/*/*/*/scripts/poll_boards.py")
                         for c in data.glob(pat)})
        check("RECOMMENDED", "No stale job-finder copies inside the data folder", not copies,
              "CLAUDE: old copy of the code inside the data folder (" + ", ".join(copies) + "); suggest the user deletes it "
              "(it won't get updates)", detail=", ".join(copies))
        sl = Path.cwd() / ".claude" / "settings.local.json"
        if (Path.cwd() / ".claude").is_dir():  # Claude Code in a project folder
            check("RECOMMENDED", "Claude Code allowed to use the data folder", sl.exists() and str(data) in sl.read_text(),
                  f"CLAUDE: run `{CFG} --data {data} --claude-settings .claude/settings.local.json`, then ask the user to "
                  f"type `/add-dir {data}`")

    # ---- machine ----
    check("REQUIRED", "Python 3.10+", sys.version_info >= (3, 10), "USER must install: Python 3.10+ (macOS: brew install python). CLAUDE may run it after asking")
    check("REQUIRED", "Node.js 18+", shutil.which("node") and run(["node", "-e", "process.exit(Number(+process.versions.node.split('.')[0] < 18))"]),
          "USER must install: Node.js 18+ (macOS: brew install node). CLAUDE may run it after asking")
    check("REQUIRED", "CV builder library (docx for Node)", run(["node", str(SCRIPTS / "build_cv.js"), "--check"]),
          "CLAUDE: run `npm install --prefix ~/.cache/job-finder docx` (ask first; installs one library into a cache folder)")
    check("REQUIRED", "LibreOffice (PDF export)", shutil.which("soffice") or (mac and Path("/Applications/LibreOffice.app").exists()),
          "CLAUDE: offer to run `brew install --cask libreoffice` (macOS); if `soffice` is still not on PATH: "
          "`ln -s /Applications/LibreOffice.app/Contents/MacOS/soffice /usr/local/bin/soffice`")
    check("REQUIRED", "Poppler (pdftotext, pdftoppm)", shutil.which("pdftotext") and shutil.which("pdftoppm"),
          "CLAUDE: offer to run `brew install poppler` (macOS)")

    # ---- network ----
    try:
        urllib.request.urlopen(urllib.request.Request("https://boards-api.greenhouse.io/v1/boards/gitlab/jobs?per_page=1",
                                                      headers={"User-Agent": "job-finder-doctor"}), timeout=10)
        net = True
    except Exception:
        net = False
    check("RECOMMENDED", "Network: public job boards reachable", net,
          "The poller needs HTTPS to boards-api.greenhouse.io, api.ashbyhq.com, api.lever.co. Without it, "
          "Claude falls back to web fetch (slower)")

    # ---- optional integrations (Claude-side; the shell can only hint) ----
    apify_hint = bool(os.environ.get("APIFY_TOKEN")) or any(
        "apify" in p.name.lower() for p in (Path.home() / ".claude/plugins").rglob("*") if p.is_dir()) if (Path.home() / ".claude/plugins").exists() else bool(os.environ.get("APIFY_TOKEN"))
    check("OPTIONAL", "Apify (paid Actors for extra job sources)", apify_hint,
          "In Claude Code: /plugin install apify, then /mcp, then plugin:apify:apify, then Enable and Authenticate. "
          "See docs/PREREQUISITES.md. Only worth it once the free poller isn't enough")
    check("OPTIONAL", "LinkedIn", True, detail="Nothing to install. LinkedIn forbids automated access; paste job links "
          "or descriptions instead. Browser automation of your account stays off unless you decide otherwise in criteria.md")

    if as_json:
        print(json.dumps({"ok": all(r["ok"] for r in results if r["level"] == "REQUIRED"), "checks": results}, indent=1))
    else:
        icon = {True: "OK  ", False: {"REQUIRED": "FAIL", "RECOMMENDED": "WARN", "OPTIONAL": "--  "}}
        for lvl in ("REQUIRED", "RECOMMENDED", "OPTIONAL"):
            print(f"\n{lvl}")
            for r in (r for r in results if r["level"] == lvl):
                mark = icon[True] if r["ok"] else icon[False][lvl]
                print(f"  [{mark}] {r['name']}" + (f"  ({r['detail']})" if r["detail"] and r["ok"] else ""))
                if not r["ok"] and r["fix"]:
                    print(f"         fix: {r['fix']}")
        bad = [r for r in results if r["level"] == "REQUIRED" and not r["ok"]]
        print("\nReady." if not bad else f"\nNot ready: {len(bad)} required item(s) to fix.")
    return 0 if all(r["ok"] for r in results if r["level"] == "REQUIRED") else 1


if __name__ == "__main__":
    sys.exit(main())
