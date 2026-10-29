"""Day 3: score the LLM extraction against Arav's hand labels.

Usage: python evaluate.py [gold.xlsx|gold.csv]   (default labels/gold.xlsx)
Prints and writes results/extraction_eval.csv: per field n, accuracy, macro-F1, Cohen's kappa.
"""
import csv, json, sys
from pathlib import Path

from sklearn.metrics import accuracy_score, cohen_kappa_score, f1_score

HERE = Path(__file__).parent
FIELDS = ["is_decision", "request_type", "local_ct_waiver_requested", "decision", "reasons_stated"]


def norm(v):
    return str(v).strip().lower()  # Excel writes TRUE/True; JSON gives true


def evaluate(gold_rows, pred):
    out = []
    for f in FIELDS:
        pairs = [(norm(g[f]), norm(pred[g["key"]].get(f))) for g in gold_rows if g[f].strip() and g["key"] in pred]
        if not pairs:
            continue
        y, p = zip(*pairs)
        out.append({"field": f, "n": len(y), "accuracy": round(accuracy_score(y, p), 3),
                    "macro_f1": round(f1_score(y, p, average="macro", zero_division=0), 3),
                    "kappa": round(cohen_kappa_score(y, p), 3) if len(set(y) | set(p)) > 1 else 1.0})
    return out


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "labels/gold.xlsx"
    if path.suffix == ".xlsx":
        import pandas as pd
        gold = pd.read_excel(path, dtype=str).fillna("").to_dict("records")
    else:
        gold = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    if gold and "checked" in gold[0]:  # human_verified.xlsx: score only rows Arav has checked
        gold = [g for g in gold if str(g["checked"]).strip().upper() == "YES"]
        print(f"{len(gold)} human-checked rows")
    pred = {(o := json.loads(l))["key"]: o for l in open(HERE / "data/extracted.jsonl", encoding="utf-8")}
    missing = [g["key"] for g in gold if g["key"] not in pred]
    if missing:
        print(f"warning: {len(missing)} gold items not extracted yet (re-run extract.py)")
    res = evaluate(gold, pred)
    if not res:
        sys.exit("nothing to score yet (no labelled rows that have been extracted)")
    (HERE / "results").mkdir(exist_ok=True)
    with open(HERE / "results/extraction_eval.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=res[0]); w.writeheader(); w.writerows(res)
    for r in res: print(r)
