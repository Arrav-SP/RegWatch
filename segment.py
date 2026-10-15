"""Day 2a: split each SEC PDF into agenda items using its table rows.

Usage: python segment.py
Reads data/pdfs + data/index.csv + data/stats.csv; writes data/items.jsonl, one item per line:
  {"pdf_id", "item_no", "division", "cells": [...], "text"}
Columns are unreliable (merged/split cells vary by year), so cells are kept in order and the
LLM step assigns fields.
"""
import csv, json, re
from multiprocessing import Pool
from pathlib import Path

import pymupdf

ROOT = Path(__file__).parent / "data"
ITEM_NO = re.compile(r"^\s*(\d{1,3})\s*\.?\s*$")
HEADER = re.compile(r"^(s\.?\s*no|agen|file name|firm|recommend|no$|da$|strength)", re.I)


def rows_to_items(pdf_id, rows):
    items, division, cur = [], "", None
    for row in rows:
        cells = [" ".join(c.split()) for c in row if c and c.strip()]
        cells = list(dict.fromkeys(cells))  # merged cells repeat their text across columns
        if not cells or HEADER.match(cells[0]):
            continue
        m = ITEM_NO.match(cells[0])
        if m and (cur is None or m.group(1) != cur["item_no"]):
            cur = {"pdf_id": pdf_id, "item_no": m.group(1), "division": division, "cells": cells[1:]}
            items.append(cur)
        elif len(cells) == 1 and len(cells[0]) < 60 and re.search(r"division|remarks|section", cells[0], re.I):
            division = cells[0]  # section heading row, e.g. "GCT Division"
        elif cur is not None:  # continuation row (page break or split cell)
            if m: cells = cells[1:]
            cur["cells"] += cells
    for it in items:
        it["text"] = " | ".join(it["cells"])
    return items


def segment(pdf_id):
    try:
        with pymupdf.open(ROOT / "pdfs" / f"{pdf_id}.pdf") as doc:
            rows = [r for p in doc for t in p.find_tables().tables for r in t.extract()]
    except Exception as e:
        return pdf_id, [], str(e)[:80]
    return pdf_id, rows_to_items(pdf_id, rows), ""


def _selfcheck():
    rows = [["S. No", "File Name", "Firm", "Recommendations"], ["GCT Division", "", "", ""],
            ["1.", "CT/1/24 DrugA", "M/s. X", "Approved"], ["", "", "", "subject to PMS"],
            ["2", "CT/2/24 DrugB", "M/s. Y", "Rejected"]]
    it = rows_to_items(1, rows)
    assert [i["item_no"] for i in it] == ["1", "2"] and it[0]["division"] == "GCT Division", it
    assert it[0]["text"] == "CT/1/24 DrugA | M/s. X | Approved | subject to PMS", it[0]["text"]


if __name__ == "__main__":
    _selfcheck()
    stats = {r["id"]: r for r in csv.DictReader(open(ROOT / "stats.csv", encoding="utf-8"))}
    ids = sorted(int(i) for i, s in stats.items() if s["scanned"] == "False")
    empty, n = [], 0
    with Pool() as pool, open(ROOT / "items.jsonl", "w", encoding="utf-8") as out:
        # ordered imap: extract.py keys depend on line order
        for k, (pid, items, err) in enumerate(pool.imap(segment, ids, chunksize=8), 1):
            if not items: empty.append((pid, err))
            for it in items: out.write(json.dumps(it, ensure_ascii=False) + "\n")
            n += len(items)
            if k % 200 == 0: print(f"  {k}/{len(ids)} PDFs, {n} items", flush=True)
    print(f"items: {n} from {len(ids) - len(empty)} PDFs; {len(empty)} PDFs gave no items")
    (ROOT / "segment_empty.txt").write_text("\n".join(f"{p}\t{e}" for p, e in sorted(empty)))
