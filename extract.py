"""Day 2b: LLM extraction of structured fields from each agenda item.

Usage: python extract.py [limit]      (resumable; skips items already in data/extracted.jsonl)
Config in regwatch/.env (never commit it). Any OpenAI-compatible endpoint works:
  LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/   (Gemini)
  LLM_MODEL=gemini-3.5-flash-lite
  LLM_API_KEY=...
Optional: LLM_BATCH (items per call, default 10), LLM_WORKERS (default 2), LLM_RPM (default 12).
"""
import json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).parent
DATA = HERE / "data"
for line in (HERE / ".env").read_text().splitlines() if (HERE / ".env").exists() else []:
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

PROMPT = """You extract structured data from Indian CDSCO Subject Expert Committee (SEC) meeting minutes.
Each input item is one agenda row: file number, drug name and strength, firm name, and the committee's recommendation.
Return JSON {"items": [...]} with one object per input item, same order, with exactly these keys:
- "key": copy the input key
- "is_decision": false if the row is not an application deliberated by the committee (summary tables, notes, headings)
- "file_no": application/file number or null
- "drug": drug or product name (with strength if given) or null
- "firm": applicant company without "M/s." or null
- "product_type": one of "drug","fdc","biologic","vaccine","medical_device","other"
- "request_type": one of
    "clinical_trial" (permission for a new CT / CT protocol, any phase),
    "bioequivalence" (BE study),
    "marketing_new_drug" (import/manufacture and market a new drug),
    "new_indication_or_change" (new indication, dosage form, strength, route, age group, label change for an approved drug),
    "protocol_amendment",
    "post_marketing" (PMS / Phase IV / PSUR related),
    "other"
- "ct_phase": "I","II","III","IV","BE" or null
- "local_ct_waiver_requested": true if the firm asked to waive the local (Indian) clinical trial, else false
- "decision": one of
    "approved" (recommended / agreed, no conditions),
    "approved_with_conditions" (recommended subject to conditions such as PMS, Phase IV, protocol changes),
    "rejected" (not recommended / not approved),
    "more_info_requested" (firm asked to submit data, revise and resubmit, or present again),
    "deferred" (not taken up: firm absent, not ready, adjourned),
    "other"
- "waiver_granted": true/false if a local CT waiver was decided, else null
- "reasons_stated": true if the committee gives any justification for its decision (efficacy, safety, unmet need, data gaps, etc.)
- "reason_summary": one short sentence of the stated reason, or null
- "conditions": list of short strings (conditions imposed or data asked for); [] if none
- "risk_benefit_discussed": true if the minutes explicitly weigh benefits against risks/safety
Use only what the text says. Do not guess."""

client = OpenAI(base_url=os.environ.get("LLM_BASE_URL"), api_key=os.environ.get("LLM_API_KEY", "none"))
MODEL = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")
BATCH = int(os.environ.get("LLM_BATCH", 10))
GAP = 60 / float(os.environ.get("LLM_RPM", 12))
lock, last_call = threading.Lock(), [0.0]


def call(batch):
    payload = [{"key": k, "division": it["division"], "text": it["text"][:6000]} for k, it in batch]
    for attempt in range(5):
        with lock:  # simple global rate limit for free tiers
            wait = last_call[0] + GAP - time.time()
            if wait > 0: time.sleep(wait)
            last_call[0] = time.time()
        try:
            r = client.chat.completions.create(
                model=MODEL, temperature=0, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": PROMPT},
                          {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
            out = json.loads(r.choices[0].message.content)["items"]
            got = {o.get("key"): o for o in out}
            if all(k in got for k, _ in batch):
                return [got[k] for k, _ in batch]
            print(f"  batch returned {len(got)}/{len(batch)} keys, retrying", flush=True)
        except Exception as e:
            if getattr(e, "status_code", 429) in (400, 401, 403, 404):  # bad key/model: retrying won't help
                raise
            print(f"  error ({type(e).__name__}: {str(e)[:120]}), retry {attempt + 1}", flush=True)
            time.sleep(2 ** attempt * 5)
    return None


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    items = [json.loads(l) for l in open(DATA / "items.jsonl", encoding="utf-8")]
    out_path = DATA / "extracted.jsonl"
    done = {json.loads(l)["key"] for l in open(out_path, encoding="utf-8")} if out_path.exists() else set()
    todo = [(f"{it['pdf_id']}-{n}", it) for n, it in enumerate(items) if len(it["text"]) >= 80]
    todo = [t for t in todo if t[0] not in done][:limit]
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    print(f"{len(done)} done, {len(todo)} to go in {len(batches)} calls with {MODEL}", flush=True)
    failed = 0
    with ThreadPoolExecutor(int(os.environ.get("LLM_WORKERS", 2))) as ex, \
            open(out_path, "a", encoding="utf-8") as f:
        for n, res in enumerate(ex.map(call, batches), 1):
            if res is None: failed += 1; continue
            for o in res: f.write(json.dumps(o, ensure_ascii=False) + "\n")
            f.flush()
            if n % 20 == 0: print(f"  {n}/{len(batches)} calls", flush=True)
    print(f"finished; {failed} batches failed (re-run to retry them)")


if __name__ == "__main__":
    main()
