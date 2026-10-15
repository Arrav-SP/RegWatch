"""Pick 200 agenda items (stratified by year) for hand-labelling -> labels/to_label.csv.
Fill the empty columns in Excel using the same values as extract.py's PROMPT, save as labels/gold.csv.
"""
import csv, json, random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
idx = {int(r["id"]): r for r in csv.DictReader(open(HERE / "data/index.csv", encoding="utf-8"))}
items = [json.loads(l) for l in open(HERE / "data/items.jsonl", encoding="utf-8")]
by_year = defaultdict(list)
for n, it in enumerate(items):
    if len(it["text"]) >= 80:  # same filter and key as extract.py
        by_year[idx[it["pdf_id"]]["release_date"][-4:]].append((f"{it['pdf_id']}-{n}", it))

random.seed(306)
years = sorted(y for y in by_year if y)  # skip rows with no release date
sample = []
for y in years:  # equal share per year so early years are not swamped by 2024-25
    sample += random.sample(by_year[y], min(len(by_year[y]), -(-200 // len(years))))
sample = random.sample(sample, min(200, len(sample)))
LABELS = ["is_decision", "request_type", "local_ct_waiver_requested", "decision", "reasons_stated"]
(HERE / "labels").mkdir(exist_ok=True)
with open(HERE / "labels/to_label.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["key", "year", "committee", "text"] + LABELS)
    for k, it in sorted(sample):
        w.writerow([k, idx[it["pdf_id"]]["release_date"][-4:], idx[it["pdf_id"]]["title"][:80], it["text"]] + [""] * len(LABELS))
print(f"{len(sample)} items from {len(years)} years -> labels/to_label.csv")
