"""Where is the private data folder? One answer for every script.

Order: --data argument > $JOB_FINDER_DATA > ~/.config/job-finder/config.json {"dataDir": ...}
       > (legacy) ./job-finder.local.json > ~/job-finder-data
"""
import json, os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent      # .../skills/job-finder
ROOT = SKILL_DIR                                        # kept for older imports
SCRIPTS = SKILL_DIR / "scripts"
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "job-finder" / "config.json"
LEGACY = Path.cwd() / "job-finder.local.json"
DEFAULT = Path.home() / "job-finder-data"


def _from(p: Path):
    try:
        return json.loads(p.read_text()).get("dataDir") if p.exists() else None
    except (OSError, ValueError):
        return None


def data_dir(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    if os.environ.get("JOB_FINDER_DATA"):
        return Path(os.environ["JOB_FINDER_DATA"]).expanduser()
    for p in (CONFIG, LEGACY):
        d = _from(p)
        if d:
            return Path(d).expanduser()
    return DEFAULT


def configured() -> bool:
    return bool(os.environ.get("JOB_FINDER_DATA")) or bool(_from(CONFIG)) or bool(_from(LEGACY))


MARKER = "# Job search criteria"
SEARCH_ROOTS = ["~/job-finder-data", "~/Documents", "~/Library/Mobile Documents/com~apple~CloudDocs",
                "~/Dropbox", "~/OneDrive", "~/Google Drive", "~/Desktop", "~/Projects", "~"]
SKIP = {"node_modules", ".git", "Library", ".Trash", "Applications", "Pictures", "Movies", "Music", ".cache", ".npm", ".nvm"}


def find_data_folders(roots=None, max_depth: int = 4, limit: int = 10) -> list[str]:
    """Existing data folders = directories holding a criteria.md that starts with the template heading.
    Reads only the first line of files named criteria.md; never anything else."""
    found = []
    for r in roots or SEARCH_ROOTS:
        base = Path(r).expanduser()
        if not base.is_dir():
            continue
        start = len(base.parts)
        for dirpath, dirnames, filenames in os.walk(base):
            depth = len(Path(dirpath).parts) - start
            dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith(".")] if depth < max_depth else []
            if "criteria.md" in filenames:
                try:
                    with open(Path(dirpath) / "criteria.md", encoding="utf-8", errors="ignore") as f:
                        if f.readline().startswith(MARKER):
                            d = str(Path(dirpath).resolve())
                            if d not in found:
                                found.append(d)
                except OSError:
                    pass
            if len(found) >= limit:
                return found
    return found
