#!/usr/bin/env python3
"""Write a one-click "apply kit" into a job folder.

  python3 scripts/apply_kit.py <job folder> --job-url URL [--apply-url URL] [--data DATA]

Creates in the folder:
  Apply.webloc  double-click on macOS -> opens the application form
  Apply.url     the same for Windows
  APPLY.md      the 3-step checklist + copy-paste answers for common form fields
                (taken from DATA/apply_profile.json) + the cover note from notes.md

The apply URL is derived from the job URL when not given:
  Ashby      .../<id>            -> .../<id>/application
  Lever      .../<id>            -> .../<id>/apply
  Greenhouse .../jobs/<id>       -> same page, #app (form is on the page)
Nothing is submitted: the person opens the form, attaches the CV and submits.
"""
import argparse, json, os, re, sys
from pathlib import Path
from xml.sax.saxutils import escape


def derive_apply_url(job_url: str) -> str:
    u = job_url.split("?")[0].rstrip("/")
    if "jobs.ashbyhq.com" in u and not u.endswith("/application"):
        return u + "/application"
    if "jobs.lever.co" in u and not u.endswith("/apply"):
        return u + "/apply"
    if "greenhouse.io" in u and "#" not in job_url:
        return job_url + "#app"
    return job_url


def cover_note(notes: Path) -> str:
    if not notes.exists():
        return ""
    m = re.search(r"## Cover note draft[^\n]*\n+(.*?)(?:\n## |\Z)", notes.read_text(), re.S)
    if not m:
        return ""
    return "\n".join(l[2:] if l.startswith("> ") else l for l in m.group(1).strip().splitlines()).strip()


def main():
    os.umask(0o077)  # private data: owner-only files
    ap = argparse.ArgumentParser()
    ap.add_argument("folder"); ap.add_argument("--job-url", required=True); ap.add_argument("--apply-url")
    ap.add_argument("--data", default=None, help="data folder holding apply_profile.json")
    ap.add_argument("--extra", action="append", default=[], help="extra checklist line (repeatable)")
    a = ap.parse_args()
    for u in (a.job_url, a.apply_url):
        if u is not None and (not re.match(r"^https://[^\s]+$", u) or any(c in u for c in "\r\n\t\"<>")):
            sys.exit(f"Refusing unsafe or non-https URL: {u!r}")
    folder = Path(a.folder); apply_url = a.apply_url or derive_apply_url(a.job_url)

    (folder / "Apply.webloc").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0">\n<dict>\n'
        f'\t<key>URL</key>\n\t<string>{escape(apply_url)}</string>\n</dict>\n</plist>\n')
    (folder / "Apply.url").write_text(f"[InternetShortcut]\r\nURL={apply_url}\r\n")

    from jf_config import data_dir
    prof_path = data_dir(a.data) / "apply_profile.json"
    prof = json.loads(prof_path.read_text()) if prof_path.exists() else {}
    cv = next(iter(sorted(folder.glob("* CV.pdf"))), None)
    lines = [f"# Apply: {folder.name}", "",
             f"1. Open **Apply.webloc** (or {apply_url})",
             f"2. Attach **{cv.name if cv else '<Name> CV.pdf'}** from this folder",
             "3. Fill the form with the answers below, review, submit.", ""]
    lines += [f"- [ ] {x}" for x in a.extra]
    if a.extra: lines.append("")
    lines += [f"Job posting: {a.job_url}", f"Application form: {apply_url}", ""]
    if prof:
        lines += ["## Copy-paste answers", ""]
        lines += [f"- **{k}:** {v}" for k, v in prof.items()]
        lines.append("")
    note = cover_note(folder / "notes.md")
    if note:
        lines += ["## Cover note (edit before pasting)", "", note, ""]
    lines += ["_Fields you fill yourself: legal name, mailing address, salary expectation, anything you're unsure of._"]
    (folder / "APPLY.md").write_text("\n".join(lines) + "\n")
    print(f"apply kit written: {folder}  ->  {apply_url}")


if __name__ == "__main__":
    sys.exit(main())
