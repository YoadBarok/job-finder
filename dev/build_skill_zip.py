#!/usr/bin/env python3
"""Build dist/job-finder-skill.zip: the main skill as a standalone upload for Claude
(Customize > Skills > + > Upload a skill). Run after changing anything in the plugin; tests check it's current."""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins/job-finder/skills/job-finder"
OUT = ROOT / "dist/job-finder-skill.zip"


def files():
    return sorted(p for p in SKILL.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store")


def build():
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files():
            info = zipfile.ZipInfo(str(Path("job-finder") / p.relative_to(SKILL)), date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = (0o755 if p.suffix in (".py", ".js") else 0o644) << 16
            z.writestr(info, p.read_bytes(), zipfile.ZIP_DEFLATED)
    print(f"built {OUT} ({OUT.stat().st_size // 1024} KB, {len(files())} files)")


if __name__ == "__main__":
    build()
