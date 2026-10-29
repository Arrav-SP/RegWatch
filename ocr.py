"""Day 5: OCR the scanned SEC PDFs (no text layer) and append their agenda items to data/items.jsonl.

Usage: python ocr.py        (needs Tesseract: winget install UB-Mannheim.TesseractOCR)
Appends only, so existing keys ("<pdf_id>-<line index>") and the gold labels never shift.
If segment.py is ever re-run, run ocr.py again afterwards (same order -> same keys).
"""
import csv, hashlib, json, os, re
from multiprocessing import Pool
from pathlib import Path

import pymupdf

ROOT = Path(__file__).parent / "data"
TESSDATA = os.environ.get("TESSDATA_PREFIX", r"C:\Program Files\Tesseract-OCR\tessdata")
NUM = re.compile(r"^\s*(\d{1,3})\s*[.)]?\s*$")


def split_items(pdf_id, text):
    """Scanned tables lose their columns, so items are cut at lines holding just the next item number."""
    items, cur, want = [], None, 1
    for line in text.splitlines():
        m = NUM.match(line)
        if m and int(m.group(1)) in (want, 1):  # next number, or numbering restarts in a new table
            cur = {"pdf_id": pdf_id, "item_no": m.group(1), "division": "", "cells": [], "ocr": True}
            items.append(cur); want = int(m.group(1)) + 1
        elif cur is not None and line.strip():
            cur["cells"].append(" ".join(line.split()))
    for it in items:
        it["text"] = " ".join(it["cells"]); it["cells"] = [it["text"]]
    return [it for it in items if len(it["text"]) >= 40]  # drop stray numbers (strengths, page numbers)


def ocr(pdf_id):
    try:
        with pymupdf.open(ROOT / "pdfs" / f"{pdf_id}.pdf") as doc:
            pages = []
            for page in doc:
                pdf = pymupdf.open("pdf", page.get_pixmap(dpi=250).pdfocr_tobytes(language="eng", tessdata=TESSDATA))
                pages.append(pdf[0].get_text())
    except Exception as e:
        return pdf_id, "", str(e)[:80]
    return pdf_id, "\n".join(pages), ""


def _selfcheck():
    t = "Minutes header\n1\nCT/1/19 DrugA | M/s X | recommended for grant of permission\n500\n2.\nCT/2/19 DrugB M/s Y not recommended for waiver of trial"
    it = split_items(7, t)
    assert [i["item_no"] for i in it] == ["1", "2"], it
    assert "500" in it[0]["text"] and it[1]["text"].startswith("CT/2/19"), it


if __name__ == "__main__":
    _selfcheck()
    items_path = ROOT / "items.jsonl"
    before = items_path.read_bytes()
    lines = before.decode("utf-8").splitlines()
    assert not any('"ocr": true' in l for l in lines[-50:]), "OCR items already appended; re-run segment.py first"
    ids = sorted(int(r["id"]) for r in csv.DictReader(open(ROOT / "stats.csv", encoding="utf-8")) if r["scanned"] == "True")
    new, report = [], []
    with Pool() as pool:
        for pid, text, err in pool.imap(ocr, ids):  # ordered, so the appended keys are reproducible
            if text: (ROOT / "text" / f"{pid}.txt").write_text(text, encoding="utf-8")
            its = split_items(pid, text)
            new += its; report.append((pid, len(its), err))
            print(f"  {pid}: {len(its)} items {err}", flush=True)
    with open(items_path, "a", encoding="utf-8") as f:
        for it in new: f.write(json.dumps(it, ensure_ascii=False) + "\n")
    after = items_path.read_bytes()
    assert after[:len(before)] == before, "existing items changed"  # keys of earlier items must not move
    print(f"OCR: {len(new)} items from {sum(n > 0 for _, n, _ in report)}/{len(ids)} PDFs; "
          f"items.jsonl {len(lines)} -> {len(lines) + len(new)} lines; prefix sha1 {hashlib.sha1(before).hexdigest()[:10]} unchanged")
