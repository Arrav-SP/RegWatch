"""Day 1: download every CDSCO SEC recommendation PDF and extract its text.

Usage: python download_sec.py            (re-runnable; skips files already on disk)
Outputs (next to this script):
  data/index.csv       one row per PDF listed on the SEC page
  data/pdfs/<id>.pdf   raw PDFs, named by the archive id
  data/text/<id>.txt   text extracted with PyMuPDF
  data/stats.csv       pages / chars per file, flags scanned PDFs
"""
import base64, csv, html, re, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf
import requests

BASE = "https://cdsco.gov.in"
SEC_PAGE = BASE + "/opencms/opencms/en/Committees/SEC/"
ROOT = Path(__file__).parent / "data"
PDFS, TEXT = ROOT / "pdfs", ROOT / "text"
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (RegWatch student project; BCSE306L)"

ROW = re.compile(
    r"<tr>\s*<td>(\d+)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*"
    r"<td><a href='([^']*num_id_pk=([^']+))'.*?</td>\s*<td>(.*?)</td>", re.S)


def parse_index(page):
    rows = []
    for sno, title, date, cat, href, b64, size in ROW.findall(page):
        rows.append({
            "id": int(base64.b64decode(b64).decode()), "title": " ".join(html.unescape(title).split()),
            "release_date": date.strip(), "category": html.unescape(cat).strip(),
            "size": size.strip(), "url": BASE + href})
    return rows


def fetch(row):
    out = PDFS / f"{row['id']}.pdf"
    if out.exists() and out.stat().st_size > 0:
        return row["id"], "cached"
    for attempt in range(4):
        try:
            r = S.get(row["url"], timeout=60)
            m = r.ok and re.search(rb"iframe src='([^']+)'", r.content)
            if m:  # common_download.jsp returns an iframe wrapper pointing at the real file
                r = S.get(BASE + requests.utils.quote(m.group(1).decode()), timeout=60)
            if r.ok and r.content[:5] == b"%PDF-":
                out.write_bytes(r.content)
                return row["id"], "ok"
            if r.ok:  # some links serve HTML / other formats; keep note, don't save as pdf
                return row["id"], f"not_pdf:{r.headers.get('Content-Type', '')}"
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    return row["id"], "failed"


def extract(pid):
    pdf, txt = PDFS / f"{pid}.pdf", TEXT / f"{pid}.txt"
    try:
        with pymupdf.open(pdf) as doc:
            text = "\n\f".join(p.get_text() for p in doc)
            pages = doc.page_count
    except Exception as e:  # corrupt PDF: record it, keep going
        return {"id": pid, "pages": 0, "chars": 0, "scanned": "", "error": str(e)[:80]}
    txt.write_text(text, encoding="utf-8")
    chars = len(text.strip())
    # shortcut: <200 chars/page means no text layer; OCR those later if they matter
    return {"id": pid, "pages": pages, "chars": chars, "scanned": chars < 200 * max(pages, 1), "error": ""}


def main():
    PDFS.mkdir(parents=True, exist_ok=True); TEXT.mkdir(exist_ok=True)
    page = S.get(SEC_PAGE, timeout=60).text
    rows = parse_index(page)
    assert rows and page.count("num_id_pk=") == len(rows), f"parsed {len(rows)} of {page.count('num_id_pk=')} links"
    with open(ROOT / "index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
    print(f"index: {len(rows)} PDFs listed")

    status = {}
    with ThreadPoolExecutor(4) as ex:  # 4 workers keeps load on the govt server modest
        for n, (pid, st) in enumerate(ex.map(fetch, rows), 1):
            status[pid] = st
            if n % 100 == 0: print(f"  downloaded {n}/{len(rows)}", flush=True)
    bad = {k: v for k, v in status.items() if v not in ("ok", "cached")}
    print(f"download: {len(rows) - len(bad)} ok, {len(bad)} problems", bad if bad else "")

    stats = [extract(int(p.stem)) for p in sorted(PDFS.glob("*.pdf"))]
    with open(ROOT / "stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=stats[0]); w.writeheader(); w.writerows(stats)
    print(f"text: {sum(s['scanned'] is True for s in stats)} scanned, "
          f"{sum(bool(s['error']) for s in stats)} unreadable, of {len(stats)}")


if __name__ == "__main__":
    sys.exit(main())
