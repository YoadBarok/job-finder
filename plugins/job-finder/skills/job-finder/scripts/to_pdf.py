#!/usr/bin/env python3
"""Convert a CV .docx to .pdf next to it, owner-only permissions.

  python3 scripts/to_pdf.py "<job folder>/<Name> CV.docx"
"""
import os, shutil, subprocess, sys
from pathlib import Path


def main():
    os.umask(0o077)
    src = Path(sys.argv[1]).expanduser().resolve()
    soffice = shutil.which("soffice") or "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(src.parent), str(src)],
                   check=True, capture_output=True)
    out = src.with_suffix(".pdf")
    os.chmod(out, 0o600)
    print(out)


if __name__ == "__main__":
    main()
