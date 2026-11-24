#!/usr/bin/env python3
"""One-time setup of this clone. Claude runs it during /setup; you never need to.

  python3 scripts/configure.py --data ~/job-finder-data

- remembers the data folder in job-finder.local.json (git-ignored, this machine only)
- creates the folder from the templates if it doesn't exist (never overwrites)
- writes .claude/settings.local.json so Claude Code may read/write that folder and run the repo's tools
"""
import argparse, json, os, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # skill folder
TEMPLATES = {
    "criteria.md": "templates/criteria.md",
    "search.json": "templates/search.json",
    "forbidden_terms.txt": "templates/forbidden_terms.txt",
    "apply_profile.json": "templates/apply_profile.json",
    "base/cv.base.json": "templates/cv.json",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="private data folder (outside the repo)")
    ap.add_argument("--find", action="store_true", help="list existing data folders on this machine and exit")
    ap.add_argument("--claude-settings", help="Claude Code settings file to grant folder access in, e.g. .claude/settings.local.json")
    a = ap.parse_args()
    os.umask(0o077)  # private data: owner-only files
    sys.path.insert(0, str(ROOT / "scripts"))
    if a.find or not a.data:
        from jf_config import find_data_folders
        print(json.dumps({"existingDataFolders": find_data_folders()}, indent=1))
        return
    data = Path(a.data).expanduser().resolve()
    repo = next((p for p in list(ROOT.parents)[:4] if (p / ".git").exists()), None)  # repo checkout, not plugin cache
    for forbidden in [ROOT] + ([repo] if repo else []):
        if data == forbidden or forbidden in data.parents:
            sys.exit("Refusing: the data folder must be outside the plugin/repo (personal data never goes into git).")

    created = []
    (data / "base").mkdir(parents=True, exist_ok=True)
    (data / "jobs").mkdir(exist_ok=True)
    for dst, src in TEMPLATES.items():
        if not (data / dst).exists():
            shutil.copyfile(ROOT / src, data / dst); created.append(dst)
    if not (data / "tracker.csv").exists():
        (data / "tracker.csv").write_text("company,role,link,score,date_found,source,cost_usd,status,updated,note\n"); created.append("tracker.csv")

    from jf_config import CONFIG
    previous = None
    if CONFIG.exists():
        try: previous = json.loads(CONFIG.read_text()).get("dataDir")
        except ValueError: pass
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"dataDir": str(data)}, indent=2) + "\n")

    if a.claude_settings:  # Claude Code only: let it read/write the folder and run these scripts
        sp = Path(a.claude_settings).expanduser()
        cfg = json.loads(sp.read_text()) if sp.exists() else {}
        perms = cfg.setdefault("permissions", {})
        dirs = perms.setdefault("additionalDirectories", [])
        if previous and previous != str(data) and previous in dirs:
            dirs.remove(previous)  # re-pointing: don't keep access to the old folder
        if str(data) not in dirs:
            dirs.append(str(data))
        allow = perms.setdefault("allow", [])
        for rule in [f"Bash(python3 {ROOT}/scripts/*)", f"Bash(node {ROOT}/scripts/*)", "Bash(pdftotext *)", "Bash(pdftoppm *)"]:
            if rule not in allow:
                allow.append(rule)
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(cfg, indent=2) + "\n")

    print(json.dumps({"dataDir": str(data), "createdFromTemplates": created,
                      "remembered_in": str(CONFIG), "next": f"Claude Code: type /add-dir {data} once. Claude app: connect this folder with Add folder."}, indent=1))


if __name__ == "__main__":
    main()
