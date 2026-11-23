#!/usr/bin/env python3
"""Turn a brief (PDF, DOCX, Google Doc export, MD or TXT) into plain text Codex can read line by line.

  python3 extract_brief.py brief/brief.pdf            # writes renders/_work/brief.txt
  python3 extract_brief.py brief/brief.docx --out renders/_work/brief.txt

PDF: uses pdftotext (poppler) when installed, else pypdf (pip install pypdf).
DOCX: standard library only (reads the XML inside the file), keeps paragraph and table cell order.
Google Docs: File > Download > .docx, then run this on the file.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def from_pdf(path):
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("Install poppler (brew install poppler) or pypdf (pip install pypdf) to read PDF briefs.")
    return "\n\n".join(p.extract_text() or "" for p in PdfReader(path).pages)


def from_docx(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    lines = []
    body = root.find(f"{W}body")
    for block in body:
        if block.tag == f"{W}p":
            lines.append("".join(t.text or "" for t in block.iter(f"{W}t")))
        elif block.tag == f"{W}tbl":
            for row in block.iter(f"{W}tr"):
                cells = ["".join(t.text or "" for t in c.iter(f"{W}t")).strip() for c in row.iter(f"{W}tc")]
                lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brief")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ext = os.path.splitext(a.brief)[1].lower()
    if ext == ".pdf":
        text = from_pdf(a.brief)
    elif ext == ".docx":
        text = from_docx(a.brief)
    elif ext in (".md", ".txt", ".markdown"):
        text = open(a.brief, encoding="utf-8").read()
    else:
        sys.exit(f"Unsupported brief type: {ext}. Use PDF, DOCX, MD or TXT.")
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    out = a.out or os.path.join("renders", "_work", "brief.txt")   # the brief itself is never changed
    if os.path.abspath(out) == os.path.abspath(a.brief):
        sys.exit("The output would overwrite the brief. Pick another --out.")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    numbered = text.splitlines()
    print(f"{a.brief} -> {out} ({len(numbered)} lines, {len(text.split())} words)")


if __name__ == "__main__":
    main()
