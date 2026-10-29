"""Day 6: predict the committee's decision from the request text alone.

Usage: python predict.py
Input = only the request part of each item (text before the committee's verdict), so the label cannot leak.
Labels = LLM-extracted decisions; split by year (train <= 2022, test >= 2023); gold items are held out and
scored against Arav's human labels. Writes results/predictor_eval.csv and data/predictor_split.csv (for Colab).
"""
import json, re

import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import cohen_kappa_score, f1_score
from sklearn.preprocessing import OneHotEncoder
from scipy.sparse import hstack

from analyze import DECISIONS, HERE, load

# first verdict phrase marks where the committee's answer starts
VERDICT = re.compile(r"after (detailed |detail )?deliberation|(the )?(committee|sec|experts?) (has |have )?"
                     r"(recommended|opined|noted|observed|concluded|did not|didn.t|could not|agreed|is of|was of|deliberated|advised)"
                     r"|firm (did not|didn.t) turn up|deferred|withdrawn", re.I)
META = ["request_type", "product_type", "local_ct_waiver_requested"]  # request-side fields only


def request_part(text):
    m = VERDICT.search(text)
    return text[:m.start()].strip(" |.,") if m and m.start() >= 40 else None  # no clean cut -> drop, never guess


def _selfcheck():
    t = "CT/1/24 DrugA | M/s X | The firm presented their proposal for Phase III. After detailed deliberation the committee recommended..."
    assert request_part(t) == "CT/1/24 DrugA | M/s X | The firm presented their proposal for Phase III", request_part(t)
    assert request_part("CT/2/24 DrugB | M/s Y | Firm did not turn up for presentation.") is None  # too short to keep


def scores(name, y, p):
    return {"model": name, "n": len(y), "macro_f1": round(f1_score(y, p, average="macro", zero_division=0), 3),
            "kappa": round(cohen_kappa_score(y, p), 3)}


def main():
    items = [json.loads(l) for l in open(HERE / "data/items.jsonl", encoding="utf-8")]
    df = load()
    df["request_text"] = [request_part(items[int(k.split("-")[1])]["text"]) for k in df.key]
    df = df[df.request_text.notna() & df.decision.isin(DECISIONS)].copy()
    gold = pd.read_excel(HERE / "labels/gold.xlsx", dtype=str).set_index("key")
    df["split"] = ["gold" if k in gold.index else ("train" if y <= 2022 else "test") for k, y in zip(df.key, df.year)]
    df["label"] = [gold.decision[k] if s == "gold" else d for k, s, d in zip(df.key, df.split, df.decision)]
    df = df[df.label.isin(DECISIONS)]
    print(df.split.value_counts().to_dict())
    df[["key", "year", "split", "request_text", "label"] + META].to_csv(HERE / "data/predictor_split.csv", index=False)

    tr = df[df.split == "train"]
    tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True)
    svd = TruncatedSVD(300, random_state=0)
    ohe = OneHotEncoder(handle_unknown="ignore")
    feats = lambda d, fit=False: hstack([
        (svd.fit_transform(tfidf.fit_transform(d.request_text)) if fit else svd.transform(tfidf.transform(d.request_text))),
        (ohe.fit_transform(d[META].astype(str)) if fit else ohe.transform(d[META].astype(str)))]).toarray()
    clf = HistGradientBoostingClassifier(class_weight="balanced", random_state=0).fit(feats(tr, True), tr.label)
    majority = tr.label.mode()[0]

    rows = []
    for s in ["test", "gold"]:
        d = df[df.split == s]
        if d.empty: continue
        rows += [scores(f"majority ({s})", d.label, [majority] * len(d)),
                 scores(f"tfidf+gbm ({s})", d.label, clf.predict(feats(d)))]
    pd.DataFrame(rows).to_csv(HERE / "results/predictor_eval.csv", index=False)
    for r in rows: print(r)


if __name__ == "__main__":
    _selfcheck()
    main()
