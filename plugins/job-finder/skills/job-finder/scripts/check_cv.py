#!/usr/bin/env python3
"""Check a tailored CV before it goes out.

  python3 scripts/check_cv.py "jobs/<folder>/<Name> CV.pdf" --data DATA [--keywords "MCP,policy,Go"]

Checks: file name, 1 page, zero hyperlinks (PDF + DOCX), forbidden employer-internal terms
(DATA/forbidden_terms.txt, one per line), text extracts in reading order (ATS), length vs base,
keyword coverage. Exit code 1 if a hard rule fails.
"""
import argparse, json, re, subprocess, sys, zipfile
from pathlib import Path

def keyword_present(k: str, low: str) -> bool:
    """Whole-word, plural-aware: 'permissions' matches 'permission' and vice versa."""
    k = k.lower().strip()
    stem = k[:-2] if k.endswith("es") and len(k) > 4 else k[:-1] if k.endswith("s") and len(k) > 3 else k
    for cand in {k, stem}:
        if re.search(rf"(?<![a-z0-9]){re.escape(cand)}(?:s|es)?(?![a-z0-9])", low):
            return True
    return False


def pdf_text(p):
    try:
        return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True, check=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        from pypdf import PdfReader  # fallback
        return "\n".join(pg.extract_text() or "" for pg in PdfReader(str(p)).pages)

def pdf_pages(p):
    raw = Path(p).read_bytes()
    return len(re.findall(rb"/Type\s*/Page[^s]", raw))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("--data", default=None, help="data folder (default: configured one)")
    ap.add_argument("--keywords", default="", help="comma-separated job keywords to check coverage")
    ap.add_argument("--name", default=None, help="expected file stem; default: '<Name> CV' from DATA/base/cv.base.json")
    a = ap.parse_args()
    from jf_config import data_dir
    pdf, data = Path(a.pdf), data_dir(a.data)
    if not a.name:
        basecv = data / "base" / "cv.base.json"
        full = json.loads(basecv.read_text())["name"] if basecv.exists() else ""
        parts = full.title().split()
        a.name = (f"{parts[0]} {parts[-1]} CV" if len(parts) > 1 else f"{full.title()} CV").strip()
    fails, notes = [], []

    if pdf.stem != a.name: fails.append(f"file name is '{pdf.name}', must be '{a.name}.pdf'")
    n = pdf_pages(pdf)
    if n != 1: fails.append(f"{n} pages (must be 1)")
    raw = pdf.read_bytes()
    links = len(re.findall(rb"/URI\s*\(", raw)) + len(re.findall(rb"/Subtype\s*/Link", raw))
    if links: fails.append(f"PDF has {links} link annotation(s) - CVs must have none")
    docx = pdf.with_suffix(".docx")
    if docx.exists():
        xml = zipfile.ZipFile(docx).read("word/document.xml").decode("utf8", "ignore")
        if "<w:hyperlink" in xml or "HYPERLINK" in xml: fails.append("DOCX contains hyperlinks")
    else:
        notes.append("no .docx next to the PDF")

    text = pdf_text(pdf); low = text.lower()
    basecv = data / "base" / "cv.base.json"
    if not basecv.exists() or "ALEX EXAMPLE" in basecv.read_text():
        fails.append("no approved base CV (base/cv.base.json missing or still the template) - run /setup")
    if "alex example" in low or "example corp" in low:
        fails.append("CV contains template text")
    ft = data / "forbidden_terms.txt"
    if ft.exists():
        terms = [t.strip() for t in ft.read_text().splitlines() if t.strip() and not t.startswith("#")]
        def found(t):  # whole-word; ALL-CAPS terms (ticket prefixes, acronyms) are case-sensitive
            caps = t.upper() == t and any(c.isalpha() for c in t)
            pat = rf"(?<![A-Za-z0-9]){re.escape(t)}" + ("" if t.endswith("-") else r"(?![A-Za-z0-9])")
            return re.search(pat, text if caps else text, 0 if caps else re.I)
        hits = [t for t in terms if found(t)]
        if hits: fails.append("employer-internal terms found: " + ", ".join(hits))
    else:
        notes.append("no forbidden_terms.txt in data dir - confidentiality not checked")

    words = len(text.split())
    base = data / "base" / "base.pdf"
    if base.exists():
        bw = len(pdf_text(base).split()); notes.append(f"words: {words} (base {bw}, {words - bw:+d})")
    else:
        notes.append(f"words: {words}")
    first = [l.strip() for l in text.splitlines() if l.strip()][:3]
    notes.append("ATS first lines: " + " / ".join(first))

    if a.keywords:
        kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
        have = [k for k in kws if keyword_present(k, low)]
        miss = [k for k in kws if k not in have]
        notes.append(f"keywords present: {', '.join(have) or '-'}")
        notes.append(f"keywords missing (gaps - do NOT add unless true): {', '.join(miss) or '-'}")

    for f in fails: print("FAIL ", f)
    for x in notes: print("info ", x)
    print("OK" if not fails else f"{len(fails)} hard rule(s) failed")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
