# RegWatch: LLM-Assisted Structuring and Analysis of a Decade of Indian Drug-Approval Committee Decisions

*Draft, 2026-11-01. All numbers come from the full corpus: 14,121 extracted agenda items, of which 13,866 are decisions.*

## Abstract
India's Central Drugs Standard Control Organisation (CDSCO) publishes the recommendations of its Subject Expert Committees (SECs) as unstructured PDF minutes. We build RegWatch, a pipeline that turns 1,864 SEC minutes (2015–2026) into a structured dataset of agenda-item decisions:
- scraping and table-aware segmentation;
- OCR for scanned files;
- extraction of request type, decision, local-trial waiver and stated reasons by a large language model (LLM).

Against 200 hand-labelled items, the extraction reaches Cohen's κ = 0.84 for the decision and κ = 0.74 for the request type. Across 13,866 decisions:
- the decision mix differs across regulatory eras (χ² = 183.3, dof = 15, p < 10⁻³⁰);
- waiver requests have 7.5× the odds of rejection (Fisher p < 10⁻¹²⁸);
- the share of decisions stating any reason fell from about 47% (2016–17) to about 21% (2023–25).

Predicting the decision from the request text alone, without leaking the verdict, a fine-tuned BiomedBERT reaches κ = 0.39 on later years and 0.38 on human-labelled items, against 0.37 and 0.33 for a TF-IDF baseline.

## 1. Introduction
SEC recommendations decide whether new drugs, trials and label changes reach Indian patients, yet they exist only as PDF tables. Prior work examined subsets by hand [Shetty et al., citation needed]. We ask three questions:
- **RQ1:** Can an LLM structure these minutes reliably?
- **RQ2:** How have decisions, transparency and waiver outcomes changed across regulatory eras, especially the New Drugs and Clinical Trials (NDCT) Rules of 2019 and COVID-19?
- **RQ3:** Can the outcome be predicted from what the applicant asks for?

## 2. Data and pipeline
1. **Collection.** The CDSCO SEC page index has 1,865 rows. We downloaded 1,864 PDFs (one .doc was skipped) and extracted text with PyMuPDF.
2. **Segmentation.** Agenda items are cut from PDF table rows, giving 13,991 items.
3. **OCR.** 65 scanned PDFs (mostly 2018–19) have no text layer. We OCR them with Tesseract and cut items at sequential item numbers. This added 273 items from 54 PDFs; 11 PDFs yielded none.
4. **Extraction.** Each item of at least 80 characters goes to `gemini-3.5-flash-lite` (temperature 0, JSON output, batches of 10). The model returns is_decision, request type (7 classes), decision (6 classes), waiver requested or granted, reasons stated, a reason summary, conditions, and whether risk–benefit was discussed. Items are processed in a fixed random order, so any partial run is an unbiased sample.
5. **Committee and year.** These come from the index. Committee names are normalised from about 60 title spellings by regular expressions. The year is the release year.

## 3. Annotation and extraction validity (RQ1)
**Gold set.** 200 items, stratified by year, were labelled by one annotator (the author).
- After a first comparison, the labelling guide was revised with four rules:
  - R1: a refused local-trial waiver counts as *rejected*.
  - R2: request type is what was asked for, not conditions imposed.
  - R3: "granted subject to submitting X" counts as *approved with conditions*.
  - R4: *other* is used only when no request or decision is identifiable.
- The relabel changed 82 labels across 65 items. It was drafted with LLM assistance and reviewed by the annotator, and every change is logged.
- Agreement between gold v1 and v2 is κ = 0.75 for both request type and decision.

**Extraction accuracy (gold v2, n = 200):**

| Field | Accuracy | Macro-F1 | κ |
|---|---|---|---|
| is_decision | 0.99 | 0.83 | 0.66 |
| request_type | 0.80 | 0.78 | 0.74 |
| local_ct_waiver_requested | 0.99 | 0.97 | 0.93 |
| decision | 0.88 | 0.87 | 0.84 |
| reasons_stated | 0.81 | 0.80 | 0.60 |

**Main remaining errors:**
- Marketing requests that include a bioequivalence or clinical study are labelled *clinical_trial* or *bioequivalence*.
- The model over-uses *approved_with_conditions*: 15 of its 25 decision errors.

## 4. Trends (RQ2)
n = 13,866 decisions, with every year from 2015 to 2026 represented. 2015 has only 21 items, so 2015 shares are noisy.

**Decision share by regulatory era:**

| Era | Approved | Approved w/ conditions | More info | Rejected | Deferred | n |
|---|---|---|---|---|---|---|
| ≤2018 (pre-NDCT) | 0.26 | 0.34 | 0.17 | 0.11 | 0.10 | 1,659 |
| 2019 (NDCT Rules) | 0.27 | 0.29 | 0.19 | 0.07 | 0.12 | 1,019 |
| 2020–21 (COVID) | 0.25 | 0.31 | 0.22 | 0.08 | 0.12 | 3,134 |
| 2022+ | 0.29 | 0.29 | 0.18 | 0.05 | 0.16 | 8,054 |

- The mix differs significantly across eras (χ² = 183.3, dof = 15, p = 5×10⁻³¹).
- Rejections fall steadily, from 11% to 5%.
- Deferrals rise, from 10% to 16%.
- Requests for more information peaked during COVID.

**Waivers.** 1,276 decisions involved a local-trial waiver request. A waiver request raises the odds of rejection 7.5-fold (Fisher exact p = 3×10⁻¹²⁹), consistent with earlier manual findings [Shetty et al.].

**Transparency.** Overall, 28.9% of decisions state any reason.
- The share fell from 0.47 (2016–17) to 0.39 (2018), 0.25 (2022) and 0.19–0.23 (2023–25).
- Explicit risk–benefit discussion fell from about 0.17 (2016–17) to about 0.03 (2023–25).
- 2026 (partial year) shows a rebound to 0.32.

**By request type:**
- Marketing applications for new drugs (13%) and new indications or changes (12%) have the highest rejection rates.
- Bioequivalence studies are mostly approved with conditions (45%); protocol amendments are mostly approved outright (71%).

See `results/decisions_by_year.png` and `results/transparency_by_year.png`.

## 5. Decision prediction (RQ3)
**Setup.**
- Input is only the request part of each item: text before the first verdict phrase, such as "After detailed deliberation" or "the committee recommended". Items without a clean cut are dropped, so the label cannot leak.
- Labels are the LLM decisions (5 classes). Gold items are held out and scored against human labels.
- Split by year: train ≤2022 (n = 6,978), test ≥2023 (n = 5,909); 181 gold items.

| Model | Test macro-F1 | Test κ | Gold macro-F1 | Gold κ |
|---|---|---|---|---|
| Majority class | 0.10 | 0.00 | 0.07 | 0.00 |
| TF-IDF + SVD + request fields → gradient boosting | 0.49 | 0.37 | 0.48 | 0.33 |
| BiomedBERT (PubMedBERT) fine-tuned, 3 epochs | 0.53 | 0.39 | 0.53 | 0.38 |

Fine-tuned BiomedBERT beats the TF-IDF baseline on both the later-year test set (κ 0.39 vs 0.37) and the human-labelled gold items (κ 0.38 vs 0.33). Its margin is largest on macro-F1 for gold items (0.53 vs 0.48), i.e. on the rarer classes. The request text carries real signal about the outcome, but most of the decision depends on deliberation not visible in the request.

## 6. Limitations
- **Single annotator.** Gold v2 was revised with LLM assistance, which may bias gold toward model behaviour. Mitigations: written rules, a full change log, annotator review, and both versions reported.
- **LLM labels.** The trend and prediction labels are LLM outputs. Gold accuracy (κ 0.74–0.84) bounds their reliability.
- **OCR coverage.** 11 of 65 scanned PDFs yielded no items, and OCR items lose their table structure.
- **Dates.** We use the release year, not the meeting date, so late-December meetings can shift by one year.
- **Coverage.** 2015 is thin (21 decisions); items under 80 characters were not extracted.

## 7. Conclusion
RegWatch turns a decade of CDSCO SEC minutes (14,121 agenda items, 2015–2026) into a structured dataset using a free-tier LLM. Against 200 hand labels it agrees at κ = 0.84 on the decision field. Three findings follow. The decision mix shifted across regulatory eras, with fewer outright rejections and more deferrals after 2022. Requests to waive local trials remain strongly associated with rejection (odds ratio 7.5). The share of decisions that state any reason halved, from about 47% in 2016–17 to about 21% in 2023–25, and explicit risk–benefit discussion almost disappeared. Finally, the request text alone predicts the verdict well above chance (BiomedBERT κ ≈ 0.39) but far from perfectly, so most of the outcome is decided in deliberation that the minutes increasingly do not record. Future work: a second annotator, meeting-level dates, and linking decisions to later market approvals.

## Reproducibility
Code: `download_sec.py`, `segment.py`, `ocr.py`, `extract.py`, `evaluate.py`, `analyze.py`, `predict.py` and `predictor_pubmedbert.ipynb`. The data is rebuilt from public CDSCO pages. Gold labels (v1 and v2) and the relabel log are in `labels/`.
