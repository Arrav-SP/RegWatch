"""Day 4: trend analysis of SEC decisions, 2015-2026.

Usage: python analyze.py
Reads data/items.jsonl, data/extracted.jsonl, data/index.csv. Writes results/*.csv and results/*.png.
"""
import csv, json, re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import chi2_contingency, fisher_exact

HERE = Path(__file__).parent
RES = HERE / "results"
DECISIONS = ["approved", "approved_with_conditions", "more_info_requested", "rejected", "deferred"]


# first match wins; titles spell committees ~60 ways ("Andhaematology", "Raio-Diagnostic", ...)
COMMITTEES = [
    ("ind proposals", "IND"), ("covid", "COVID-19"), ("oncol|haemat|hemat", "Oncology & Haematology"), ("nephro", "Nephrology & Urology"),
    ("cardio|renal", "Cardiovascular & Renal"), ("neuro|psych", "Neurology & Psychiatry"),
    ("endocrin|metabol", "Endocrinology & Metabolism"), ("derma|allerg", "Dermatology & Allergy"),
    ("pulmon", "Pulmonary"), ("gastro|hepat", "Gastroenterology & Hepatology"), ("ophthal", "Ophthalmology"),
    ("antimicrob|antivir|antiparas|antifung", "Antimicrobial & Antiviral"), ("vaccin", "Vaccine"),
    ("analges|rheumat|an[a]?esth|ortho", "Analgesics, Rheumatology & Orthopaedics"),
    ("reproduct|urolog", "Reproductive & Urology"), ("radio|raio|diagnos", "Radio-Diagnostic"),
    ("dent", "Dentistry"), ("veterin", "Veterinary"), ("stem cell|cellular", "Cellular & Stem Cell")]


def committee(title, category):
    s = f"{title} {category}".lower()
    return next((name for pat, name in COMMITTEES if re.search(pat, s)), "Other")


def load():
    idx = {int(r["id"]): r for r in csv.DictReader(open(HERE / "data/index.csv", encoding="utf-8"))}
    items = [json.loads(l) for l in open(HERE / "data/items.jsonl", encoding="utf-8")]
    rows = []
    for l in open(HERE / "data/extracted.jsonl", encoding="utf-8"):
        o = json.loads(l)
        it = items[int(o["key"].split("-")[1])]
        meta = idx[it["pdf_id"]]
        # shortcut: release year, not meeting date; they differ only for meetings late in December
        rows.append({**o, "year": meta["release_date"][-4:], "division": it["division"],
                     "committee": committee(meta["title"], meta["category"])})
    df = pd.DataFrame(rows)
    df = df[(df.is_decision == True) & (df.year != "")]
    df["year"] = df.year.astype(int)
    df["era"] = pd.cut(df.year, [0, 2018, 2019, 2021, 9999], labels=["pre-NDCT (<=2018)", "2019 (NDCT rules)", "COVID (2020-21)", "post (2022+)"])
    return df


def rate_table(df, by):
    t = pd.crosstab(df[by], df.decision, normalize="index").reindex(columns=DECISIONS, fill_value=0).round(3)
    t["n"] = df.groupby(by).size()
    return t


def main():
    RES.mkdir(exist_ok=True)
    df = load()
    print(f"{len(df)} decisions, {df.year.min()}-{df.year.max()}")

    by_year = rate_table(df, "year"); by_year.to_csv(RES / "decisions_by_year.csv")
    rate_table(df, "committee").sort_values("n", ascending=False).to_csv(RES / "decisions_by_committee.csv")
    rate_table(df, "request_type").to_csv(RES / "decisions_by_request_type.csv")
    by_era = rate_table(df, "era"); by_era.to_csv(RES / "decisions_by_era.csv")

    # chi-square: is the decision mix different across regulatory eras?
    chi2, p, dof, _ = chi2_contingency(pd.crosstab(df.era, df.decision))
    # waiver requests vs rejection (Shetty et al. found waivers ~5x more likely to be rejected)
    tab = pd.crosstab(df.local_ct_waiver_requested == True, df.decision == "rejected").reindex(index=[True, False], columns=[True, False], fill_value=0)
    odds, p_w = fisher_exact(tab.values)
    transp = df.groupby("year")[["reasons_stated", "risk_benefit_discussed"]].mean().round(3)
    transp.to_csv(RES / "transparency_by_year.csv")
    stats = {"n_decisions": len(df), "era_chi2": round(chi2, 2), "era_dof": dof, "era_p": p,
             "waiver_requests": int(tab.loc[True].sum()), "waiver_reject_odds_ratio": round(odds, 2), "waiver_fisher_p": p_w,
             "reasons_stated_overall": round(df.reasons_stated.mean(), 3)}
    json.dump(stats, open(RES / "stats.json", "w"), indent=2, default=float)
    print(json.dumps(stats, indent=2, default=float))

    ax = by_year[DECISIONS].plot(kind="bar", stacked=True, figsize=(10, 5), colormap="tab10")
    ax.set(title="SEC decisions by year (share of agenda items)", xlabel="", ylabel="share")
    ax.legend(bbox_to_anchor=(1, 1)); plt.tight_layout(); plt.savefig(RES / "decisions_by_year.png", dpi=150); plt.close()
    ax = transp.plot(marker="o", figsize=(8, 4), ylim=(0, 1))
    ax.set(title="Transparency: share of decisions with stated reasons", xlabel="", ylabel="share")
    plt.tight_layout(); plt.savefig(RES / "transparency_by_year.png", dpi=150); plt.close()


if __name__ == "__main__":
    assert committee("Recommendations of the SEC (Oncology) made in its 25th/26 meeting", "") == "Oncology & Haematology"
    assert committee("The 20th SEC (Pulmonary) meeting deliberated", "0") == "Pulmonary"
    main()
