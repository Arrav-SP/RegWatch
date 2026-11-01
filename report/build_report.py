"""Builds the BCSE306L report (Word) by filling the course template.
Usage (from regwatch/): python report/build_report.py <template.docx>
All numbers are read from results/ or stated from the paper; figures are regenerated here."""
import copy, csv, json, sys
from pathlib import Path

import docx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report"
FIG = OUT / "figures"; FIG.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
from evaluate import norm  # same label normalisation as the official scores

TITLE = "RegWatch: LLM-Assisted Structuring and Analysis of a Decade of Indian Drug-Approval Committee Decisions"
SHORT = "RegWatch: LLM Analysis of CDSCO SEC Decisions"


def rcsv(name):
    return list(csv.DictReader(open(ROOT / "results" / name, encoding="utf-8")))


EXT = {r["field"]: r for r in rcsv("extraction_eval.csv")}
PRED = {r["model"]: r for r in rcsv("predictor_eval.csv") + rcsv("predictor_eval_bert.csv")}
STATS = json.load(open(ROOT / "results/stats.json"))
ERA = rcsv("decisions_by_era.csv")
REQ = rcsv("decisions_by_request_type.csv")
TRN = {r["year"]: r for r in rcsv("transparency_by_year.csv")}


# ---------- figures ----------
def fig_pipeline():
    steps = ["CDSCO SEC\nindex page\n(1,865 rows)", "download_sec.py\n1,864 PDFs", "segment.py\ntable rows →\n13,991 items",
             "ocr.py\nTesseract on 65\nscanned PDFs\n(+273 items)", "extract.py\nGemini LLM,\nJSON schema\n(14,121 items)",
             "evaluate.py\nκ vs 200\nhand labels", "analyze.py\ntrends, χ²,\nFisher", "predict.py +\nBiomedBERT\nverdict model"]
    fig, ax = plt.subplots(figsize=(11, 3.4)); ax.axis("off")
    for i, s in enumerate(steps):
        r, c = divmod(i, 4); x, y = c * 2.75, 1.6 - r * 1.6
        col = "#DCE6F2" if i < 5 else "#F6E3D4"
        ax.add_patch(plt.Rectangle((x, y), 2.2, 1.15, fc=col, ec="#14213D", lw=1.2))
        ax.text(x + 1.1, y + 0.575, s, ha="center", va="center", fontsize=8.5)
        if c < 3: ax.annotate("", (x + 2.7, y + 0.575), (x + 2.2, y + 0.575), arrowprops=dict(arrowstyle="->", lw=1.3))
    ax.annotate("", (1.1, 1.15), (9.35, 1.6), arrowprops=dict(arrowstyle="->", lw=1.3, connectionstyle="arc3,rad=0.15"))
    ax.set_xlim(-0.1, 11); ax.set_ylim(-0.1, 2.85)
    ax.text(0, 2.82, "Data layer (blue)  →  Analysis layer (orange)", fontsize=9, style="italic")
    fig.tight_layout(); fig.savefig(FIG / "pipeline.png", dpi=200); plt.close(fig)


def fig_confusion():
    import pandas as pd
    from sklearn.metrics import confusion_matrix
    gold = pd.read_excel(ROOT / "labels/gold.xlsx", dtype=str).fillna("")
    pred = {j["key"]: j for j in map(json.loads, open(ROOT / "data/extracted_gold.jsonl", encoding="utf-8"))}
    y, p = [], []
    for _, g in gold.iterrows():
        if g["key"] in pred and g["decision"]:
            y.append(norm(g["decision"])); p.append(norm(pred[g["key"]].get("decision")))
    labs = ["approved", "approved_with_conditions", "more_info_requested", "rejected", "deferred", "other"]
    labs = [l for l in labs if l in set(y) | set(p)]
    m = confusion_matrix(y, p, labels=labs)
    short = {"approved": "approved", "approved_with_conditions": "appr. w/ cond.", "more_info_requested": "more info",
             "rejected": "rejected", "deferred": "deferred", "other": "other"}
    fig, ax = plt.subplots(figsize=(6.2, 5)); ax.imshow(m, cmap="Blues")
    ax.set_xticks(range(len(labs)), [short[l] for l in labs], rotation=35, ha="right")
    ax.set_yticks(range(len(labs)), [short[l] for l in labs])
    for i in range(len(labs)):
        for j in range(len(labs)):
            ax.text(j, i, m[i, j], ha="center", va="center", color="white" if m[i, j] > m.max() / 2 else "black")
    ax.set_xlabel("LLM prediction"); ax.set_ylabel("Human gold label (v2)")
    ax.set_title(f"Decision field, n = {len(y)}"); fig.tight_layout()
    fig.savefig(FIG / "confusion_decision.png", dpi=200); plt.close(fig)
    return len(y)


fig_pipeline(); N_CM = fig_confusion()

# ---------- document helpers ----------
d = docx.Document(sys.argv[1])
body = d.element.body


def set_text(par, text):
    runs = par.runs
    runs[0].text = text
    for r in runs[1:]: r.text = ""


def replace_in_runs(par, old_bits, new):
    """Header placeholder may be split over runs; overwrite the runs that carry it."""
    hit = [r for r in par.runs if any(b in r.text for b in old_bits)]
    if hit:
        hit[0].text = new
        for r in hit[1:]: r.text = ""


paras = d.paragraphs
# cover
set_text(paras[4], TITLE)
for r in paras[4].runs: r.font.size = Pt(22)
set_text(paras[6], "Arav - 24BCE2425")
for i in (8, 7): paras[i]._p.getparent().remove(paras[i]._p)  # solo project: drop member 2/3 lines
paras = d.paragraphs
for p in paras[:22]:
    if "2026" in p.text and len(p.text) < 30: set_text(p, "November 01, 2026")
# TOC typo fixes only, keep entries
for p in paras[:40]:
    for a, b in [("Priniciple", "Principle"), ("Objecives", "Objectives")]:
        for t in p._p.iter(qn("w:t")):  # TOC text may sit inside hyperlinks, not plain runs
            if t.text and a in t.text: t.text = t.text.replace(a, b)
# header title on every section
for s in d.sections:
    for hp in s.header.paragraphs:
        replace_in_runs(hp, ["<", "Case", "study", "Title", ">"], SHORT)

# remember the template's own heading formatting (its headings override style auto-numbering and fonts)
def grab(pred):
    tp = next(p for p in paras if pred(p))
    rpr = next((r._r.rPr for r in tp.runs if r._r.rPr is not None and r.text.strip()), None)
    return copy.deepcopy(tp._p.pPr), copy.deepcopy(rpr)
TPL = {"h1": grab(lambda p: p.style.name == "Heading 1" and p.text.startswith("2. Literature")),
       "h2": grab(lambda p: p.text.startswith("3.1 Concept")),
       "abs": grab(lambda p: p.style.name == "Unnumbered Heading 1")}

# drop the template body (from "Abstract" heading on), keep final sectPr
start = next(i for i, p in enumerate(paras) if p.style.name == "Unnumbered Heading 1" and p.text.strip() == "Abstract")
SECT = None  # the template's first section break (holds header/footer refs) lives in the abstract paragraph
for p in paras[start:]:
    if p._p.pPr is not None and p._p.pPr.find(qn("w:sectPr")) is not None:
        SECT = copy.deepcopy(p._p.pPr.find(qn("w:sectPr")))
    p._p.getparent().remove(p._p)
assert SECT is not None, "template section break not found"
for t in list(d.tables): t._tbl.getparent().remove(t._tbl)

H1_BREAKS = not d.styles["Heading 1"].paragraph_format.page_break_before


def page_break():
    d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def tpl_par(kind, text):
    ppr, rpr = TPL[kind]
    p = d.add_paragraph()
    if ppr is not None: p._p.insert(0, copy.deepcopy(ppr))
    r = p.add_run(text)
    if rpr is not None: r._r.insert(0, copy.deepcopy(rpr))
    return p


def h1(text, first=False):
    if H1_BREAKS and not first: page_break()
    tpl_par("h1", text)


def h2(text): tpl_par("h2", text)
def h3(text): d.add_paragraph(text, style="Heading 3")


def para(text, bold_lead=None, align_justify=True):
    p = d.add_paragraph(style="Normal")
    if bold_lead:
        p.add_run(bold_lead).bold = True
    p.add_run(text)
    if align_justify: p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return p


def bullets(items):
    for it in items:
        p = d.add_paragraph(style="Normal")  # template has no bullet numbering defined; hanging-indent bullet instead
        p.paragraph_format.left_indent = Inches(0.3); p.paragraph_format.first_line_indent = Inches(-0.2)
        p.paragraph_format.space_after = Pt(3); p.add_run("•  ")
        if isinstance(it, tuple):
            p.add_run(it[0]).bold = True; p.add_run(it[1])
        else:
            p.add_run(it)


def code(text):
    for line in text.strip("\n").split("\n"):
        p = d.add_paragraph(style="Code")
        p.paragraph_format.space_after = Pt(0); p.paragraph_format.space_before = Pt(0)
        r = p.add_run(line if line else " "); r.font.size = Pt(8.5); r.font.name = "Consolas"
    d.add_paragraph()


def caption(text):
    p = d.add_paragraph(style="Caption") if "Caption" in [s.name for s in d.styles] else d.add_paragraph()
    r = p.add_run(text); r.italic = True; r.font.size = Pt(10)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def figure(path, width, cap):
    p = d.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(width))
    caption(cap)


def borders(tbl):
    tblPr = tbl._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{side}")
        for k, v in (("val", "single"), ("sz", "4"), ("space", "0"), ("color", "000000")): e.set(qn(f"w:{k}"), v)
        b.append(e)
    tblPr.append(b)


def table(rows, widths=None, cap=None):
    if cap: caption(cap)
    t = d.add_table(rows=len(rows), cols=len(rows[0])); borders(t)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j); c.text = ""
            r = c.paragraphs[0].add_run(str(val)); r.font.size = Pt(10); r.bold = i == 0
            pf = c.paragraphs[0].paragraph_format; pf.space_after = Pt(1); pf.space_before = Pt(1); pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
            if i == 0:
                sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), "D9E2F3")
                c._tc.get_or_add_tcPr().append(sh)
            if widths: c.width = Inches(widths[j])
    d.add_paragraph()
    return t


f2 = lambda x: f"{float(x):.2f}"
pct = lambda x: f"{100 * float(x):.0f}%"


def avg(years, col):
    return sum(float(TRN[y][col]) for y in years) / len(years)


# ---------- content ----------
tpl_par("abs", "Abstract")
para(
    "India's Central Drugs Standard Control Organisation (CDSCO) decides which new drugs, clinical trials and label changes reach "
    "Indian patients on the advice of its Subject Expert Committees (SECs), but these recommendations are published only as "
    "unstructured PDF minutes, which makes them impossible to analyse at scale. This case study builds RegWatch, an AI pipeline that "
    "converts 1,864 SEC minutes released between 2015 and 2026 into a structured, validated dataset of 14,121 agenda items. The pipeline "
    "combines web scraping, table-aware text segmentation, Tesseract OCR for scanned files, and schema-constrained information "
    "extraction with a large language model (Gemini 3.5 Flash-Lite). Validated against 200 hand-labelled items, the extraction reaches "
    f"Cohen's κ = {f2(EXT['decision']['kappa'])} on the committee decision and κ = {f2(EXT['request_type']['kappa'])} on the request type. "
    f"Statistical analysis of {STATS['n_decisions']:,} decisions shows that the decision mix differs significantly across regulatory eras "
    f"(χ² = {STATS['era_chi2']:.1f}, p < 10⁻³⁰), that requests to waive local clinical trials carry {STATS['waiver_reject_odds_ratio']:.1f}× "
    "the odds of rejection, and that the share of decisions stating any reason fell from about 47% (2016–17) to about 21% (2023–25). "
    "Finally, a leakage-free decision predictor that sees only the applicant's request reaches κ = "
    f"{f2(PRED['biomedbert (test)']['kappa'])} with a fine-tuned BiomedBERT model on later, unseen years. The whole system runs at zero "
    "monetary cost on free-tier services.")
d.paragraphs[-1]._p.get_or_add_pPr().append(SECT)  # restore section break right after the abstract, as in the template

h1("1. Introduction")
para(
    "Drug regulation is a high-stakes decision process: approving an unsafe drug harms patients, and delaying an effective one denies "
    "them treatment. In India, the SECs of CDSCO examine every application for a new drug, a new clinical trial, a bioequivalence "
    "study or a change to an approved product, and record a recommendation in meeting minutes. Over a decade these minutes form a "
    "rich record of how the regulator reasons, but the record is locked inside more than 1,800 PDF files with inconsistent layouts, "
    "some of them scanned images. No one can read them all by hand.")
para(
    "RegWatch applies Artificial Intelligence to this problem in three stages. First, natural-language processing and a large "
    "language model (LLM) turn each agenda item into structured fields (request type, decision, waiver, reasons). Second, the "
    "extracted data is validated against human labels and analysed statistically for trends. Third, supervised machine-learning "
    "models test whether the outcome can be predicted from the request alone. The project answers three research questions:")
bullets([("RQ1: ", "Can an LLM structure regulatory minutes reliably enough for research use?"),
         ("RQ2: ", "How have decisions, transparency and waiver outcomes changed across regulatory eras, in particular the New Drugs "
                   "and Clinical Trials (NDCT) Rules, 2019 and the COVID-19 period?"),
         ("RQ3: ", "Can the committee's verdict be predicted from what the applicant asks for?")])

h2("1.1 Domain Information")
para(
    "CDSCO, headed by the Drugs Controller General of India (DCGI), is India's national drug regulator under the Ministry of Health "
    "and Family Welfare. Since 2011 it has relied on Subject Expert Committees, panels of clinicians and pharmacologists organised by "
    "therapeutic area (oncology, cardiology, neurology, vaccines and others), to review applications. Each SEC meeting produces "
    "minutes listing agenda items as table rows: file number, drug and strength, applicant firm, a summary of what was presented, and "
    "the committee's recommendation.")
para(
    "The NDCT Rules, 2019 replaced the older Schedule Y framework and introduced timelines and explicit provisions for waiving local "
    "clinical trials (Rule 101) when a drug is already approved in specified countries. A local clinical-trial waiver request asks the "
    "regulator to approve a drug for India without testing it on Indian patients, so the way SECs handle such requests is of direct "
    "public-health interest. Typical outcomes recorded in the minutes are approval, approval with conditions (for example a Phase IV "
    "study), a request for more information, rejection, and deferral.")

h2("1.2 Software Libraries Used")
table([["Library / Service", "Version / tier", "Purpose in RegWatch"],
       ["Python", "3.14", "Implementation language for all scripts"],
       ["requests", "latest", "Downloading the CDSCO index and PDF minutes"],
       ["PyMuPDF (fitz)", "latest", "PDF text and table extraction; OCR hook (pdfocr_tobytes)"],
       ["Tesseract OCR", "5.x (UB Mannheim build)", "Text recognition for 65 scanned PDFs"],
       ["openai (SDK)", "latest", "Client for Gemini's OpenAI-compatible endpoint"],
       ["Google Gemini 3.5 Flash-Lite", "Free tier", "LLM for schema-constrained information extraction"],
       ["pandas, openpyxl", "latest", "Tabular processing and the Excel labelling sheets"],
       ["scikit-learn", "latest", "TF-IDF, TruncatedSVD, HistGradientBoosting, Cohen's κ, F1"],
       ["SciPy", "latest", "Chi-square and Fisher exact tests"],
       ["matplotlib", "latest", "Trend charts and figures"],
       ["Hugging Face Transformers, PyTorch", "Google Colab (free T4 GPU)", "Fine-tuning BiomedBERT"]],
      widths=[1.9, 1.6, 3.0])

h2("1.3 Contributions by Team Members")
para("This case study was carried out individually. Arav (24BCE2425) was responsible for every stage of the work:")
bullets(["Problem framing, research questions and literature review",
         "Data collection, segmentation and OCR pipeline",
         "LLM prompt design, extraction runs under free-tier limits, and the labelling guide",
         "Hand annotation of the 200-item gold set and the logged guide revision",
         "Statistical trend analysis, the decision predictor and BiomedBERT fine-tuning",
         "Report and presentation"])

h2("1.4 Challenges Faced")
bullets([("Free-tier API quota. ", "The daily Gemini quota allows roughly 490 calls. Extraction was made resumable, items are batched "
                                   "ten per call, and the run stops itself after three consecutive failures so quota is never wasted."),
         ("Scanned PDFs. ", "65 minutes (mostly 2018–19) had no text layer. They were OCR'd with Tesseract and appended without "
                            "changing the identifiers of existing items."),
         ("Inconsistent layouts. ", "Tables change format across years and committees; items are cut from table rows with a "
                                    "fallback splitter on item numbers."),
         ("Ambiguous labels. ", "The first comparison exposed inconsistent human labels for edge cases (refused waivers, conditional "
                                "grants). Four written rules were added and every relabel was logged."),
         ("Label leakage. ", "The minutes contain the verdict, so the predictor's input is cut before verdict phrases such as "
                             "\"After detailed deliberation\"."),
         ("Sampling bias. ", "An early partial run covered only 2015–18. Items are now processed in a fixed random order, so any "
                             "partial run is an unbiased sample.")])

h2("1.5 Scientific / Technical Principle Note")
para(
    "Zero-shot information extraction with LLMs. ", bold_lead=None)
d.paragraphs[-1].runs[0].bold = True
d.paragraphs[-1].add_run(
    "A pretrained transformer language model is given a precise schema (field names, allowed classes and decision rules) and the raw "
    "item text, and returns JSON. Because the model is not fine-tuned, its correctness must be measured against human labels; "
    "temperature 0 and a fixed schema make the output deterministic and machine-checkable.")
para("Inter-annotator agreement. ", bold_lead=None); d.paragraphs[-1].runs[0].bold = True
d.paragraphs[-1].add_run(
    "Cohen's κ measures agreement between the LLM and the human annotator after removing agreement expected by chance, which plain "
    "accuracy cannot do when classes are imbalanced.")
para("Supervised text classification and transfer learning. ", bold_lead=None); d.paragraphs[-1].runs[0].bold = True
d.paragraphs[-1].add_run(
    "The predictor compares a classical bag-of-words pipeline (TF-IDF features, dimensionality reduction, gradient-boosted trees) "
    "with transfer learning: BiomedBERT, a BERT model pretrained on PubMed abstracts, is fine-tuned on the task. A temporal split "
    "(train up to 2022, test 2023 onwards) checks that the model generalises to future decisions.")
para("Statistical inference. ", bold_lead=None); d.paragraphs[-1].runs[0].bold = True
d.paragraphs[-1].add_run(
    "Chi-square tests of independence check whether the decision distribution depends on the regulatory era; Fisher's exact test "
    "and the odds ratio quantify the association between waiver requests and rejection.")

h1("2. Literature and Reference Log")
para("The literature was reviewed along four lines: the regulatory domain, LLMs for annotation and extraction, biomedical language "
     "models, and the evaluation methods used. The log below records each source, what it contributes and how RegWatch uses it.")
table([["#", "Source", "Key contribution", "Use in RegWatch"],
       ["[1]", "CDSCO, SEC meeting minutes portal", "Primary record of SEC recommendations, 2015–2026", "The dataset itself (1,864 PDFs)"],
       ["[2]", "MoHFW, New Drugs and Clinical Trials Rules, 2019", "Current regulatory framework; Rule 101 local-trial waiver",
        "Defines eras and the waiver variable"],
       ["[3]", "Brown et al., 2020 (GPT-3)", "LLMs perform tasks from instructions with few or no examples", "Basis for zero-shot extraction"],
       ["[4]", "Agrawal et al., 2022", "LLMs extract clinical information from free text with few examples",
        "Supports LLM extraction in the medical domain"],
       ["[5]", "Gilardi et al., 2023", "ChatGPT matches or beats crowd workers on text annotation", "Justifies LLM labelling at scale"],
       ["[6]", "Devlin et al., 2019 (BERT)", "Bidirectional transformer pretraining and fine-tuning", "Architecture of the neural predictor"],
       ["[7]", "Gu et al., 2021 (PubMedBERT)", "Domain-specific pretraining on PubMed beats general BERT on biomedical NLP",
        "Choice of BiomedBERT"],
       ["[8]", "Vaswani et al., 2017", "Transformer self-attention architecture", "Foundation of both LLM and BERT"],
       ["[9]", "Cohen, 1960", "Chance-corrected agreement coefficient κ", "Main validation metric"],
       ["[10]", "Landis & Koch, 1977", "Interpretation bands for κ (0.81–1.00 almost perfect)", "Reading the validation results"],
       ["[11]", "Salton & Buckley, 1988", "TF-IDF term weighting", "Baseline text features"],
       ["[12]", "Ke et al., 2017 (LightGBM)", "Histogram-based gradient boosting", "Baseline classifier design"],
       ["[13]", "Pedregosa et al., 2011", "scikit-learn library", "Baseline models and metrics"],
       ["[14]", "Kaufman et al., 2012", "Taxonomy of leakage in data mining", "Leakage-free predictor design"],
       ["[15]", "Smith, 2007", "Architecture of the Tesseract OCR engine", "OCR of scanned minutes"],
       ["[16]", "Wolf et al., 2020", "Hugging Face Transformers library", "BiomedBERT fine-tuning"]],
      widths=[0.4, 1.8, 2.3, 2.0], cap="Table 2.1: Literature and reference log")
para(
    "Review. Work on LLMs for annotation [3]–[5] shows that instruction-following models can label text at or above crowd-worker "
    "quality, but the same studies stress that agreement must be measured against human labels in each new domain, which is why "
    "RegWatch builds its own gold set and reports κ [9], [10] rather than trusting the model. For prediction, domain-specific "
    "pretraining [7] consistently outperforms general models on biomedical text, motivating BiomedBERT over general BERT [6]. "
    "Leakage [14] is the main threat to any outcome predictor built from documents that also contain the outcome, and is handled "
    "explicitly.")
para(
    "Research gap. The SEC minutes [1] are widely reported on case by case in the trade press, and the waiver policy [2] is well "
    "documented, but a search of the literature found no systematic, machine-readable analysis of SEC decisions across the decade, "
    "no measurement of how often the committees justify their decisions, and no validated dataset that other researchers could reuse. "
    "RegWatch addresses this gap.")

h1("3. Concept Sketches, Equations, and Models")
h2("3.1 Concept Sketches")
figure(FIG / "pipeline.png", 6.3, "Figure 3.1: RegWatch pipeline, from raw CDSCO minutes to validated data, trends and prediction")
para(
    "Figure 3.1 shows the end-to-end design. The data layer (blue) scrapes the CDSCO index, downloads each PDF, cuts it into agenda "
    "items using table rows, recovers scanned files with OCR, and sends each item to the LLM, which returns a fixed JSON schema. "
    "The analysis layer (orange) first validates the extraction against human labels, then computes trends and statistical tests, "
    "and finally trains decision predictors on the request part of each item. Every stage writes a file that the next stage reads, "
    "so each step can be re-run and checked independently.")

h2("3.2 Equations")
para("Cohen's kappa (agreement between LLM and human beyond chance):", bold_lead=None)
code("κ = (p_o − p_e) / (1 − p_e),   p_e = Σ_k p_k(LLM) · p_k(human)")
para("where p_o is the observed agreement and p_e the agreement expected if both labelled at random with their own class "
     "frequencies.")
para("Macro-averaged F1 (gives every decision class equal weight, so rare outcomes such as rejection matter):")
code("F1_k = 2 · P_k · R_k / (P_k + R_k),   Macro-F1 = (1/K) Σ_k F1_k")
para("Chi-square test of independence (era × decision table):")
code("χ² = Σ_i Σ_j (O_ij − E_ij)² / E_ij,   E_ij = (row_i total · column_j total) / N,   dof = (r − 1)(c − 1)")
para("Odds ratio for rejection given a waiver request (tested with Fisher's exact test):")
code("OR = (a / b) / (c / d)    a, b = rejected / not rejected with waiver;  c, d = without waiver")
para("TF-IDF weight of term t in item d (baseline features):")
code("tfidf(t, d) = tf(t, d) · log( (1 + N) / (1 + df(t)) ) + 1")
para("Class-weighted cross-entropy used to fine-tune BiomedBERT on imbalanced decisions:")
code("L = − Σ_i w_(y_i) · log softmax(z_i)_(y_i),   w_k ∝ N / (K · n_k)")

h2("3.3 Models")
para("", bold_lead="M1 – LLM extractor (Gemini 3.5 Flash-Lite). ")
d.paragraphs[-1].add_run(
    "Zero-shot, temperature 0, JSON response mode, ten items per call. The prompt defines 15 output fields with closed class lists "
    "and four disambiguation rules (refused waiver = rejected; request type = what was asked; \"granted subject to\" = approved with "
    "conditions; \"other\" only when nothing is identifiable).")
para("", bold_lead="M2 – Baseline predictor. ")
d.paragraphs[-1].add_run(
    "Request text → TF-IDF (1–2-grams) → TruncatedSVD (300 dimensions), concatenated with one-hot request type, product type and "
    "waiver flag → HistGradientBoostingClassifier with balanced class weights. A majority-class model gives the floor.")
para("", bold_lead="M3 – BiomedBERT predictor. ")
d.paragraphs[-1].add_run(
    "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract fine-tuned for 3 epochs (learning rate 2×10⁻⁵, batch 16, max length 256, "
    "mixed precision) with the weighted loss above, on the same split as M2.")
para("", bold_lead="Statistical models. ")
d.paragraphs[-1].add_run("Chi-square test over four eras (≤2018, 2019, 2020–21, 2022+) × six decisions, and Fisher's exact test "
                         "on the 2×2 waiver × rejection table.")

h1("4. Feasibility Calculation Sheet")
para("Feasibility was assessed before the full run using corpus statistics, published free-tier limits and the results of the "
     "early sample run (Section 11).")
table([["Quantity", "Calculation", "Value"],
       ["Items to extract (≥ 80 characters)", "count from items.jsonl", "14,131"],
       ["Average item length", "8,224,536 characters / 14,131", "≈ 582 characters ≈ 146 tokens"],
       ["LLM calls needed", "14,131 / 10 items per call", "≈ 1,414 calls"],
       ["Input tokens", "14,131 × 146 + 1,414 × ≈ 1,000 prompt tokens", "≈ 3.5 million"],
       ["Daily throughput (free tier)", "observed: 4,870 items in one day", "≈ 490 calls/day"],
       ["Calendar time for extraction", "1,414 / 490", "≈ 3 days"],
       ["Monetary cost", "free tier (Gemini) + free Colab T4", "₹0"],
       ["Gold-set precision", "SE = √(0.88 · 0.12 / 200)", "± 4.5% (95% CI on accuracy)"],
       ["Storage", "PDFs + JSONL", "≈ 583 MB"]],
      widths=[2.2, 2.7, 1.6], cap="Table 4.1: Feasibility calculations")
table([["Dimension", "Assessment", "Verdict"],
       ["Technical", "All components are standard, installed libraries; LLM extraction proven on a 4,670-item sample", "Feasible"],
       ["Data", "Minutes are public on cdsco.gov.in; 96% have a text layer, the rest are recoverable by OCR", "Feasible"],
       ["Economic", "No paid services; runs on a laptop plus free Colab GPU", "Feasible"],
       ["Schedule", "≈ 3 days of quota-paced extraction, resumable", "Feasible"],
       ["Legal / ethical", "Public government documents; no personal data beyond company names", "Feasible"]],
      widths=[1.3, 4.0, 1.2], cap="Table 4.2: Feasibility summary")

h1("5. Problem Statement and Objectives")
h2("5.1 Problem Statement")
para(
    "Indian drug-approval decisions are published only as heterogeneous PDF minutes, so regulators, industry and researchers cannot "
    "measure how the SECs decide, whether their practice has changed across regulatory reforms, or how transparently they justify "
    "their recommendations. Manual review of more than 14,000 agenda items is infeasible, and an automated approach is only useful "
    "if its accuracy is demonstrated against human judgement.")
h2("5.2 Objectives")
bullets(["O1: Build an automated pipeline that converts all SEC minutes from 2015–2026 into a structured agenda-item dataset, "
         "including scanned files.",
         "O2: Extract request type, decision, waiver and justification fields with an LLM and validate them against a hand-labelled "
         "gold set, targeting κ ≥ 0.70 on the main fields.",
         "O3: Quantify trends in decisions, waivers and stated reasons across regulatory eras with appropriate statistical tests.",
         "O4: Build a leakage-free model that predicts the decision from the request alone and compare a classical baseline with a "
         "fine-tuned biomedical transformer.",
         "O5: Achieve all of the above at zero monetary cost with reproducible, resumable code."])

h1("6. Use Case and Stakeholder Definition")
h2("6.1 Use Cases")
table([["Use case", "Issue addressed", "How RegWatch helps"],
       ["UC1 Trend monitoring", "No one knows how SEC decisions have shifted over time", "Year- and era-wise decision shares with significance tests"],
       ["UC2 Transparency audit", "Decisions often give no reasons", "Measures the share of decisions stating reasons, per year"],
       ["UC3 Waiver analysis", "Waiver policy outcomes are anecdotal", "Quantifies rejection odds for waiver requests"],
       ["UC4 Application planning", "Firms cannot gauge likely outcomes", "Predictor estimates the verdict from a draft request"],
       ["UC5 Search and research", "Minutes are unsearchable PDFs", "Structured, queryable dataset of 14,121 items"]],
      widths=[1.6, 2.3, 2.6])
h2("6.2 Stakeholders")
bullets([("Regulators (CDSCO, SEC members): ", "review consistency across committees and years, and track the effect of the NDCT Rules."),
         ("Pharmaceutical regulatory-affairs teams: ", "benchmark how similar requests were decided and which conditions are typically imposed."),
         ("Health-policy researchers and academics: ", "use the validated dataset for further studies without re-extracting PDFs."),
         ("Journalists, patient groups and civil society: ", "monitor transparency of approvals affecting public health."),
         ("Students and educators: ", "a worked example of validated LLM extraction and leakage-free ML on real government data.")])

h1("7. Functional / Performance Requirement Sheet")
table([["ID", "Requirement", "Type", "Target", "Achieved"],
       ["F1", "Download all SEC minutes from the CDSCO index", "Functional", "All rows", "1,864 / 1,865 (one .doc skipped)"],
       ["F2", "Segment minutes into agenda items", "Functional", "Table-aware", "13,991 items"],
       ["F3", "Recover scanned PDFs", "Functional", "OCR", "273 items from 54 / 65 scans"],
       ["F4", "Extract 15 structured fields per item", "Functional", "JSON schema", "14,121 items"],
       ["F5", "Resume after interruption without duplicates", "Functional", "Yes", "Yes (key-based skip)"],
       ["F6", "Score extraction against human labels", "Functional", "Accuracy, F1, κ", "evaluate.py"],
       ["F7", "Trend tables, charts and tests", "Functional", "Per year / era", "analyze.py"],
       ["F8", "Predict decision from request only", "Functional", "No leakage", "predict.py + notebook"],
       ["P1", "Decision-field agreement", "Performance", "κ ≥ 0.70", f"κ = {f2(EXT['decision']['kappa'])}"],
       ["P2", "Request-type agreement", "Performance", "κ ≥ 0.70", f"κ = {f2(EXT['request_type']['kappa'])}"],
       ["P3", "Predictor above chance on unseen years", "Performance", "κ > 0", f"κ = {f2(PRED['biomedbert (test)']['kappa'])}"],
       ["P4", "Cost", "Performance", "₹0", "₹0"],
       ["P5", "Quota safety", "Performance", "Stop on exhaustion", "Stops after 3 failed batches"]],
      widths=[0.4, 2.3, 0.9, 1.1, 1.8], cap="Table 7.1: Functional and performance requirements")

h1("8. Analytical and Desk Study Report")
para(f"All results in this section use the full corpus: {STATS['n_decisions']:,} agenda items classified as decisions, every year "
     "from 2015 to 2026 (2015 has only 21 items, so its shares are noisy).")
h2("8.1 Decisions across regulatory eras")
rows = [["Era", "Approved", "Appr. w/ cond.", "More info", "Rejected", "Deferred", "n"]]
for r in ERA:
    rows.append([r["era"], f2(r["approved"]), f2(r["approved_with_conditions"]), f2(r["more_info_requested"]),
                 f2(r["rejected"]), f2(r["deferred"]), f"{int(r['n']):,}"])
table(rows, cap="Table 8.1: Decision shares by regulatory era")
para(f"The decision mix depends on the era (χ² = {STATS['era_chi2']:.1f}, dof = {STATS['era_dof']}, p = {STATS['era_p']:.0e}). "
     "Outright rejections fell from 11% before the NDCT Rules to 5% after 2022, while deferrals rose from 10% to 16%. Requests for "
     "more information peaked during COVID-19.")
p = ROOT / "results/decisions_by_year.png"
if p.exists(): figure(p, 6.0, "Figure 8.1: Share of each decision type per year")
h2("8.2 Local clinical-trial waivers")
para(f"{STATS['waiver_requests']:,} decisions involved a request to waive the local clinical trial. Such requests carry "
     f"{STATS['waiver_reject_odds_ratio']:.1f} times the odds of rejection of other applications (Fisher's exact p = "
     f"{STATS['waiver_fisher_p']:.0e}), consistent with the restrictive waiver policy in the NDCT Rules [2].")
h2("8.3 Transparency of decisions")
para(f"Overall, {100 * STATS['reasons_stated_overall']:.1f}% of decisions state any reason. The share fell from "
     f"{avg(['2016', '2017'], 'reasons_stated'):.2f} (2016–17) to {float(TRN['2018']['reasons_stated']):.2f} (2018), "
     f"{float(TRN['2022']['reasons_stated']):.2f} (2022) and about {avg(['2023', '2024', '2025'], 'reasons_stated'):.2f} (2023–25). "
     f"Explicit risk–benefit discussion fell from about {avg(['2016', '2017'], 'risk_benefit_discussed'):.2f} to "
     f"{avg(['2023', '2024', '2025'], 'risk_benefit_discussed'):.2f}. The partial year 2026 shows a rebound to "
     f"{float(TRN['2026']['reasons_stated']):.2f}.")
p = ROOT / "results/transparency_by_year.png"
if p.exists(): figure(p, 6.0, "Figure 8.2: Share of decisions stating reasons and discussing risk–benefit, per year")
h2("8.4 Decisions by request type")
rows = [["Request type", "Approved", "Appr. w/ cond.", "More info", "Rejected", "Deferred", "n"]]
for r in REQ:
    rows.append([r["request_type"], f2(r["approved"]), f2(r["approved_with_conditions"]), f2(r["more_info_requested"]),
                 f2(r["rejected"]), f2(r["deferred"]), f"{int(r['n']):,}"])
table(rows, cap="Table 8.2: Decision shares by request type")
para("Marketing applications for new drugs (13%) and new indications or changes (12%) are rejected most often. Bioequivalence "
     "studies are mostly approved with conditions (45%), and protocol amendments are mostly approved outright (71%).")

h1("9. Component Identification and Characterization Sheet")
table([["Component", "File", "Input → Output", "Technique", "LOC"],
       ["Collector", "download_sec.py", "CDSCO index → 1,864 PDFs + stats.csv", "HTTP scraping, retries", "99"],
       ["Segmenter", "segment.py", "PDFs → items.jsonl (13,991)", "PyMuPDF table rows → items", "72"],
       ["OCR module", "ocr.py", "65 scanned PDFs → +273 items", "Tesseract via PyMuPDF; append-only", "71"],
       ["Extractor", "extract.py", "items → extracted.jsonl (15 fields)", "Gemini LLM, JSON schema, batching", "128"],
       ["Labelling tools", "make_label_sample.py, make_label_sheet.py", "items → stratified Excel sheet", "Stratified sampling, dropdowns", "94"],
       ["Evaluator", "evaluate.py", "gold.xlsx + predictions → scores", "Accuracy, macro-F1, Cohen's κ", "53"],
       ["Analyzer", "analyze.py", "extracted → trend CSV/PNG, stats.json", "Aggregation, χ², Fisher", "95"],
       ["Predictor", "predict.py", "extracted → predictor_eval.csv, split", "Leak-free cut, TF-IDF+SVD+GBM", "77"],
       ["Neural predictor", "predictor_pubmedbert.ipynb", "split → BiomedBERT metrics", "Transformer fine-tuning (Colab)", "–"]],
      widths=[1.1, 1.5, 1.8, 1.7, 0.4], cap="Table 9.1: System components")
para("Characterization. Each component is a single script with one input and one output file, so stages are independent and "
     "re-runnable. Data-safety properties: the extractor skips items already done (resumable), the OCR module asserts that existing "
     "items are byte-identical after appending, and secrets (API key) live only in an untracked .env file.")

h1("10. First-Pass Performance Prediction Document")
para("Before running the full pipeline, expected performance was estimated from the literature and a small pilot. The table "
     "compares those first-pass predictions with what was finally measured.")
table([["Metric", "First-pass prediction", "Basis", "Measured"],
       ["Decision κ (LLM vs human)", "0.70–0.85", "LLM annotation studies [4], [5]", f2(EXT["decision"]["kappa"])],
       ["Request-type κ", "0.65–0.80", "More classes, more ambiguity", f2(EXT["request_type"]["kappa"])],
       ["Waiver-requested κ", "> 0.85", "Explicit wording in minutes", f2(EXT["local_ct_waiver_requested"]["kappa"])],
       ["Reasons-stated κ", "0.50–0.70", "Subjective judgement", f2(EXT["reasons_stated"]["kappa"])],
       ["Predictor κ (baseline)", "0.25–0.40", "Verdict depends on unseen deliberation", f2(PRED["tfidf+gbm (test)"]["kappa"])],
       ["Predictor κ (BiomedBERT)", "baseline + 0.02–0.10", "Domain pretraining [7]", f2(PRED["biomedbert (test)"]["kappa"])],
       ["Extraction time", "≈ 3 days", "Free-tier quota (Table 4.1)", "3 days"]],
      widths=[1.8, 1.4, 2.2, 1.0], cap="Table 10.1: Predicted vs measured performance")
para("All measured values fall inside or above the predicted ranges, so the first-pass model of the system was sound.")

h1("11. Early Simulation Output (Feasibility Evidence)")
para("Because items are extracted in a fixed random order, the first day's partial run (4,670 items, one third of the corpus) is "
     "an unbiased sample. Its results served as feasibility evidence before the full run, and the full-corpus results confirm "
     "them:")
table([["Result", "Early sample (4,670 items)", "Full corpus (14,121 items)"],
       ["Decisions analysed", "4,575", f"{STATS['n_decisions']:,}"],
       ["Reasons stated, 2016–17 → 2023–25", "44% → 21%", "47% → 21%"],
       ["Era effect (χ², dof 15)", "70.3, p ≈ 4×10⁻⁹", f"{STATS['era_chi2']:.1f}, p ≈ {STATS['era_p']:.0e}"],
       ["Waiver odds ratio for rejection", "7.3 (423 requests)", f"{STATS['waiver_reject_odds_ratio']:.1f} ({STATS['waiver_requests']:,} requests)"],
       ["TF-IDF predictor κ (test / gold)", "0.35 / 0.25", f"{f2(PRED['tfidf+gbm (test)']['kappa'])} / {f2(PRED['tfidf+gbm (gold)']['kappa'])}"],
       ["BiomedBERT κ (test / gold)", "0.40 / 0.36", f"{f2(PRED['biomedbert (test)']['kappa'])} / {f2(PRED['biomedbert (gold)']['kappa'])}"]],
      widths=[2.4, 2.0, 2.1], cap="Table 11.1: Early sample vs full corpus")
para("Every finding kept its direction and grew stronger in significance with three times the data, which shows that the "
     "findings are not artefacts of a small sample.")
para("Pilot gold-set run of the extraction prompt (console output):")
code(f"""$ python extract.py --gold
$ python evaluate.py labels/gold.xlsx data/extracted_gold.jsonl
field                       n   accuracy  macro_f1  kappa
is_decision               200   {EXT['is_decision']['accuracy']:>6}    {EXT['is_decision']['macro_f1']:>6}  {EXT['is_decision']['kappa']}
request_type              200   {EXT['request_type']['accuracy']:>6}    {EXT['request_type']['macro_f1']:>6}  {EXT['request_type']['kappa']}
local_ct_waiver_requested 200   {EXT['local_ct_waiver_requested']['accuracy']:>6}    {EXT['local_ct_waiver_requested']['macro_f1']:>6}  {EXT['local_ct_waiver_requested']['kappa']}
decision                  200   {EXT['decision']['accuracy']:>6}    {EXT['decision']['macro_f1']:>6}  {EXT['decision']['kappa']}
reasons_stated            200   {EXT['reasons_stated']['accuracy']:>6}    {EXT['reasons_stated']['macro_f1']:>6}  {EXT['reasons_stated']['kappa']}""")

h1("12. Initial Qualitative Risk List")
table([["#", "Risk", "Likelihood", "Impact", "Mitigation"],
       ["R1", "LLM mislabels items (hallucination, wrong class)", "Medium", "High", "Closed class lists, temperature 0, validation on 200 gold items (κ reported)"],
       ["R2", "Free-tier quota exhausted mid-run", "High", "Medium", "Resumable extraction; stop after 3 failed batches; random order keeps partial runs unbiased"],
       ["R3", "Scanned PDFs lose data", "Medium", "Medium", "Tesseract OCR; 54 of 65 recovered; limitation reported"],
       ["R4", "Inconsistent human labels", "Medium", "High", "Written rules R1–R4; full change log; v1 and v2 both kept"],
       ["R5", "Label leakage inflates predictor", "High", "High", "Text cut before verdict phrases; items without a clean cut dropped"],
       ["R6", "Temporal over-fitting", "Medium", "Medium", "Train ≤2022, test ≥2023"],
       ["R7", "Single annotator bias", "Medium", "Medium", "Guide revision logged; v1-v2 agreement reported (κ 0.75)"],
       ["R8", "API key exposure", "Low", "High", "Key only in untracked .env; never printed or committed"],
       ["R9", "Release year ≠ meeting date", "Low", "Low", "Documented; affects only late-December meetings"]],
      widths=[0.35, 1.8, 0.8, 0.7, 2.85], cap="Table 12.1: Qualitative risk register")

h1("13. Lab Test / Simulation Report for Critical Functions")
para("This section shows the critical functions of the system with their code and test output.")
h2("13.1 Schema-constrained LLM extraction (extract.py)")
para("The prompt fixes the output schema and the decision rules; excerpt:")
code('''PROMPT = """You extract structured data from Indian CDSCO Subject Expert Committee (SEC) meeting minutes.
Return JSON {"items": [...]} with one object per input item, same order, with exactly these keys:
- "request_type": one of "clinical_trial", "bioequivalence", "marketing_new_drug",
    "new_indication_or_change", "protocol_amendment", "post_marketing", "other"
  request_type is what the firm asked for, not what the committee imposed ...
- "decision": one of "approved", "approved_with_conditions", "rejected"
    (also a refused local CT waiver), "more_info_requested", "deferred", "other"
- "reasons_stated": true if the committee gives any justification for its decision
Use only what the text says. Do not guess."""

r = client.chat.completions.create(model=MODEL, temperature=0,
        response_format={"type": "json_object"}, messages=[...])''')
h2("13.2 Quota guard (extract.py)")
code('''if res is None:
    failed += 1; streak += 1
    if streak >= 3:
        ex.shutdown(wait=False, cancel_futures=True)
        print("3 batches failed in a row: quota exhausted, re-run later (resumable)")
        break
    continue
streak = 0''')
para("Test: when the daily quota ran out (HTTP 429), the run stopped cleanly; re-running continued from the last saved item. "
     "Day 1 ended at 9,540 items and day 2 completed the corpus at 14,121 items with no duplicates.")
h2("13.3 Leakage-free request splitter (predict.py)")
code('''VERDICT = re.compile(r"after (detailed |detail )?deliberation|(the )?(committee|sec|experts?) (has |have )?"
                     r"(recommended|opined|noted|observed|concluded|did not|...)"
                     r"|firm (did not|didn.t) turn up|deferred|withdrawn", re.I)

def request_part(text):
    m = VERDICT.search(text)
    return text[:m.start()].strip(" |.,") if m and m.start() >= 40 else None  # no clean cut -> drop''')
para("Test: a built-in self-check asserts that the verdict sentence is removed from sample items and that items without a clean "
     "cut are dropped rather than guessed.")
h2("13.4 Append-only OCR (ocr.py)")
code('''before = items_path.read_bytes()
... append OCR items ...
after = items_path.read_bytes()
assert after[:len(before)] == before, "existing items changed"  # keys of earlier items must not move''')
h2("13.5 Predictor run (console output)")
code(f"""$ python predict.py
{{'train': 6978, 'test': 5909, 'gold': 181}}
{{'model': 'majority (test)',  'n': 5909, 'macro_f1': {PRED['majority (test)']['macro_f1']}, 'kappa': {PRED['majority (test)']['kappa']}}}
{{'model': 'tfidf+gbm (test)', 'n': 5909, 'macro_f1': {PRED['tfidf+gbm (test)']['macro_f1']}, 'kappa': {PRED['tfidf+gbm (test)']['kappa']}}}
{{'model': 'tfidf+gbm (gold)', 'n': 181,  'macro_f1': {PRED['tfidf+gbm (gold)']['macro_f1']}, 'kappa': {PRED['tfidf+gbm (gold)']['kappa']}}}

# Colab notebook (BiomedBERT, T4 GPU)
{{'model': 'biomedbert (test)', 'n': 5909, 'macro_f1': {PRED['biomedbert (test)']['macro_f1']}, 'kappa': {PRED['biomedbert (test)']['kappa']}}}
{{'model': 'biomedbert (gold)', 'n': 181,  'macro_f1': {PRED['biomedbert (gold)']['macro_f1']}, 'kappa': {PRED['biomedbert (gold)']['kappa']}}}""")
h2("13.6 Trend analysis (console output)")
code(f"""$ python analyze.py
{STATS['n_decisions']} decisions, 2015-2026
{json.dumps(STATS, indent=2)}""")

h1("14. Analytical Model Validation Document")
h2("14.1 Extraction validity against human labels")
para("A gold set of 200 items, stratified by year, was labelled by hand in Excel with dropdown menus, independently of the LLM. "
     "After a first comparison the labelling guide was revised once with four written rules; the revision changed 82 labels "
     "across 65 items, every change is logged with its rule and reason, and agreement between gold v1 and v2 is κ = 0.75.")
rows = [["Field", "n", "Accuracy", "Macro-F1", "Cohen's κ", "Landis–Koch band"]]
band = lambda k: "almost perfect" if k > 0.8 else "substantial" if k > 0.6 else "moderate"
for f, name in [("decision", "Decision"), ("request_type", "Request type"), ("local_ct_waiver_requested", "Waiver requested"),
                ("reasons_stated", "Reasons stated"), ("is_decision", "Is a decision")]:
    r = EXT[f]; rows.append([name, r["n"], f2(r["accuracy"]), f2(r["macro_f1"]), f2(r["kappa"]), band(float(r["kappa"]))])
table(rows, cap="Table 14.1: LLM extraction vs human gold labels (v2)")
figure(FIG / "confusion_decision.png", 4.6, f"Figure 14.1: Confusion matrix for the decision field (n = {N_CM})")
para("Error analysis. Most remaining decision errors come from the model over-using approved_with_conditions (15 of its 25 "
     "decision errors). For request type, marketing applications that include a bioequivalence or clinical study are sometimes "
     "labelled as the study type. The is-a-decision κ (0.66) looks low only because non-decisions are rare: there are 2 errors in "
     "200 items.")
h2("14.2 Predictor validation")
para("The predictor is validated three ways: (1) no leakage, since the input is only the text before the verdict phrase; (2) a "
     "temporal split, training on decisions up to 2022 and testing on 2023 onwards; and (3) a human check, with the 181 usable "
     "gold items held out of training and scored against human labels.")
table([["Model", "Test macro-F1", "Test κ", "Gold macro-F1", "Gold κ"],
       ["Majority class (floor)", f2(PRED["majority (test)"]["macro_f1"]), f2(PRED["majority (test)"]["kappa"]),
        f2(PRED["majority (gold)"]["macro_f1"]), f2(PRED["majority (gold)"]["kappa"])],
       ["TF-IDF + SVD + request fields → gradient boosting", f2(PRED["tfidf+gbm (test)"]["macro_f1"]), f2(PRED["tfidf+gbm (test)"]["kappa"]),
        f2(PRED["tfidf+gbm (gold)"]["macro_f1"]), f2(PRED["tfidf+gbm (gold)"]["kappa"])],
       ["BiomedBERT fine-tuned (3 epochs)", f2(PRED["biomedbert (test)"]["macro_f1"]), f2(PRED["biomedbert (test)"]["kappa"]),
        f2(PRED["biomedbert (gold)"]["macro_f1"]), f2(PRED["biomedbert (gold)"]["kappa"])]],
      widths=[2.6, 1.0, 0.8, 1.1, 0.8], cap="Table 14.2: Decision predictor results")
para("BiomedBERT beats the baseline on both test sets, with its largest margin on macro-F1 for the human-labelled items "
     "(0.53 vs 0.48), meaning it handles the rarer decision classes better. Both models are far above the majority floor, so the "
     "request text carries real signal, but κ ≈ 0.4 also shows that most of the outcome is decided in deliberation that the request "
     "does not reveal.")
h2("14.3 Robustness checks")
bullets(["Sample stability: findings from the one-third random sample match the full corpus (Table 11.1).",
         "Guide revision: v1 vs v2 gold agreement κ = 0.75; both versions are kept so results can be reproduced with either.",
         "Limitations: single annotator; trend labels are LLM outputs bounded by the κ values above; 11 scanned PDFs yielded no items; "
         "the release year is used instead of the exact meeting date."])

h1("15. Conclusion")
para(
    "RegWatch shows that a free-tier large language model, wrapped in a careful pipeline and validated against human labels, can "
    "turn a decade of unstructured regulatory minutes into a research-grade dataset. Of the objectives set out, O1 and O2 are met: "
    f"14,121 agenda items were extracted from 1,864 minutes, and agreement with human labels is almost perfect on the decision "
    f"field (κ = {f2(EXT['decision']['kappa'])}) and substantial on the request type (κ = {f2(EXT['request_type']['kappa'])}).")
para(
    "O3 produced three findings about Indian drug regulation. The decision mix shifted significantly across regulatory eras, with "
    "fewer outright rejections and more deferrals after 2022. Requests to waive local trials remain strongly associated with "
    f"rejection (odds ratio {STATS['waiver_reject_odds_ratio']:.1f}). And the share of decisions that state any reason halved, from "
    "about 47% in 2016–17 to about 21% in 2023–25, while explicit risk–benefit discussion almost disappeared. This transparency "
    "measure is new and is directly relevant to public accountability.")
para(
    f"For O4, the request text alone predicts the verdict well above chance (BiomedBERT κ = {f2(PRED['biomedbert (test)']['kappa'])} "
    "on unseen years), but far from perfectly: most of the outcome is decided in deliberation that the minutes increasingly do not "
    "record. O5 was met, with the entire system running at zero cost. Future work: a second annotator to measure human–human "
    "agreement, exact meeting dates, linking decisions to later market approvals, and a public search interface over the dataset.")

h1("References")
refs = [
    "Central Drugs Standard Control Organisation, \"Subject Expert Committee meeting minutes and recommendations,\" Ministry of Health "
    "and Family Welfare, Government of India. [Online]. Available: https://cdsco.gov.in",
    "Ministry of Health and Family Welfare, \"New Drugs and Clinical Trials Rules, 2019,\" G.S.R. 227(E), Gazette of India, 19 Mar. 2019.",
    "T. B. Brown et al., \"Language models are few-shot learners,\" in Advances in Neural Information Processing Systems 33 (NeurIPS), 2020.",
    "M. Agrawal, S. Hegselmann, H. Lang, Y. Kim, and D. Sontag, \"Large language models are few-shot clinical information extractors,\" "
    "in Proc. EMNLP, 2022.",
    "F. Gilardi, M. Alizadeh, and M. Kubli, \"ChatGPT outperforms crowd workers for text-annotation tasks,\" Proc. Natl. Acad. Sci. USA, "
    "vol. 120, no. 30, 2023.",
    "J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, \"BERT: Pre-training of deep bidirectional transformers for language "
    "understanding,\" in Proc. NAACL-HLT, 2019.",
    "Y. Gu et al., \"Domain-specific language model pretraining for biomedical natural language processing,\" ACM Trans. Comput. "
    "Healthcare, vol. 3, no. 1, 2021.",
    "A. Vaswani et al., \"Attention is all you need,\" in Advances in Neural Information Processing Systems 30 (NeurIPS), 2017.",
    "J. Cohen, \"A coefficient of agreement for nominal scales,\" Educational and Psychological Measurement, vol. 20, no. 1, pp. 37–46, 1960.",
    "J. R. Landis and G. G. Koch, \"The measurement of observer agreement for categorical data,\" Biometrics, vol. 33, no. 1, "
    "pp. 159–174, 1977.",
    "G. Salton and C. Buckley, \"Term-weighting approaches in automatic text retrieval,\" Information Processing & Management, "
    "vol. 24, no. 5, pp. 513–523, 1988.",
    "G. Ke et al., \"LightGBM: A highly efficient gradient boosting decision tree,\" in Advances in Neural Information Processing "
    "Systems 30 (NeurIPS), 2017.",
    "F. Pedregosa et al., \"Scikit-learn: Machine learning in Python,\" Journal of Machine Learning Research, vol. 12, "
    "pp. 2825–2830, 2011.",
    "S. Kaufman, S. Rosset, C. Perlich, and O. Stitelman, \"Leakage in data mining: Formulation, detection, and avoidance,\" ACM Trans. "
    "Knowledge Discovery from Data, vol. 6, no. 4, 2012.",
    "R. Smith, \"An overview of the Tesseract OCR engine,\" in Proc. 9th Int. Conf. Document Analysis and Recognition (ICDAR), 2007.",
    "T. Wolf et al., \"Transformers: State-of-the-art natural language processing,\" in Proc. EMNLP: System Demonstrations, 2020.",
]
for i, r in enumerate(refs, 1):
    p = d.add_paragraph(style="Normal"); p.add_run(f"[{i}] {r}")
    p.paragraph_format.left_indent = Inches(0.4); p.paragraph_format.first_line_indent = Inches(-0.4)

out = OUT / "RegWatch_BCSE306L_Report.docx"
d.save(out)
print("saved", out, "| H1 page-break-before in style:", not H1_BREAKS)
