# RegWatch

RegWatch turns the published meeting minutes of India's drug regulator into a structured dataset.

CDSCO's Subject Expert Committees (SECs) review applications for clinical trials, bioequivalence
studies, new drugs and label changes. They publish their recommendations as PDFs. Each PDF is a table
of agenda items: the file number, drug, firm and the committee's recommendation. RegWatch downloads
every PDF and splits it into agenda items. An LLM then extracts structured fields from each item,
and the extraction is scored against hand-labelled examples.

> Status: work in progress. The pipeline runs end to end. The hand-labelled evaluation set and
> results are not published in this repository yet.

## Pipeline

| Step | Script | Input | Output |
|---|---|---|---|
| 1. Download | `download_sec.py` | CDSCO SEC page | `data/index.csv`, `data/pdfs/`, `data/text/`, `data/stats.csv` |
| 2. Segment | `segment.py` | PDFs | `data/items.jsonl` (one agenda item per line) |
| 3. Extract | `extract.py` | agenda items | `data/extracted.jsonl` (structured fields per item) |
| 4. Sample | `make_label_sample.py` | items | `labels/to_label.csv` (200 items for labelling) |
| 5. Label sheet | `make_label_sheet.py` | sample | `labels/gold.xlsx` (dropdown-only labelling sheet) |
| 6. Evaluate | `evaluate.py` | hand labels + extraction | `results/extraction_eval.csv` |

### 1. Download (`download_sec.py`)
- Parses the SEC listing page into an index of every PDF (title, release date, category, size, URL).
  An assertion checks that every download link on the page was parsed.
- Downloads with 4 workers and retries with exponential backoff. Some links return an HTML wrapper
  instead of the file; the script follows the wrapper to the real PDF. Responses that aren't PDFs are
  reported, not saved.
- Extracts text with PyMuPDF. A PDF with fewer than 200 characters per page has no text layer, so
  it's flagged as scanned. Corrupt PDFs are recorded and skipped.
- Re-runnable: files already on disk are skipped.

### 2. Segment (`segment.py`)
- Reads each PDF's tables with PyMuPDF and turns table rows into agenda items. It handles:
  - section headings such as "GCT Division"
  - merged cells that repeat their text
  - rows continued across page breaks
- Column layouts differ between years, so cells are kept in order and the LLM assigns fields.
- Scanned PDFs are skipped. Runs in parallel, and includes an assert-based self-check of the row
  parser.

### 3. Extract (`extract.py`)
- Sends agenda items to any OpenAI-compatible endpoint (Gemini by default) in batches of 10, with
  JSON output and temperature 0.
- Each item becomes one record with these fields:
  - `is_decision`
  - `file_no`, `drug`, `firm`, `product_type`
  - `request_type`: clinical trial, BE study, new drug, new indication or change, protocol
    amendment, post-marketing, or other
  - `ct_phase`
  - `local_ct_waiver_requested`, `waiver_granted`
  - `decision`: approved, approved with conditions, rejected, more info requested, deferred, or other
  - `reasons_stated`, `reason_summary`
  - `conditions`
  - `risk_benefit_discussed`
- The prompt tells the model to use only what the text says and not to guess.
- Reliability:
  - A global rate limit keeps it within free-tier quotas.
  - Transient errors are retried with backoff. Authentication and model errors fail fast.
  - A batch whose response is missing any input keys is retried.
  - Runs are resumable: items already in `data/extracted.jsonl` are skipped.

### 4–6. Evaluation
- `make_label_sample.py` draws 200 items stratified by year, with a fixed seed, so later years with
  more meetings don't dominate the sample.
- `make_label_sheet.py` builds an Excel sheet with dropdowns for each label and a "how to label"
  guide tab. It refuses to overwrite an existing `gold.xlsx`, which holds the hand labels.
- `evaluate.py` compares the extraction with the hand labels on five fields: `is_decision`,
  `request_type`, `local_ct_waiver_requested`, `decision` and `reasons_stated`. For each field it
  reports accuracy, macro-F1 and Cohen's kappa.

## Setup

Requires Python 3.

```bash
pip install pymupdf requests openai scikit-learn pandas openpyxl
```

Create a `.env` file next to the scripts. It is git-ignored; never commit it.

```
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-3.5-flash-lite
LLM_API_KEY=your-key
# Optional: LLM_BATCH=10  LLM_WORKERS=2  LLM_RPM=12
```

## Usage

```bash
python download_sec.py        # 1. download and extract text
python segment.py             # 2. split PDFs into agenda items
python extract.py [limit]     # 3. LLM extraction (resumable; re-run to retry failed batches)
python make_label_sample.py   # 4. pick 200 items to label
python make_label_sheet.py    # 5. build labels/gold.xlsx, then label it by hand
python evaluate.py            # 6. score the extraction against the labels
```

## Limitations
- Scanned PDFs (no text layer) are skipped; there is no OCR yet.
- Segmentation depends on PyMuPDF's table detection. PDFs that yield no items are listed in
  `data/segment_empty.txt`.
- Agenda items shorter than 80 characters are not sent for extraction.
- LLM extraction can be wrong. That is why every field the evaluation covers is measured against
  hand labels before the dataset is used.

## Data
All source documents are public minutes from the CDSCO website. The `data/` folder is git-ignored,
so this repository contains code and labels only, not the downloaded PDFs. Downloads use a modest
level of concurrency and identify themselves with a descriptive User-Agent.
