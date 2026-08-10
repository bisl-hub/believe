"""Bulk-register believe analysis jobs for the biomarker eval.

Each curated association becomes one qwen_retriever job: the clinical hypothesis
is used both as the retrieval query and as the hypothesis. believe retrieves the
top-1000 PMIDs and judges each abstract support / reject / neutral. Every
association is a true relationship, so the expected verdict is SUPPORT.

State (row_id -> job_id) in runs/jobs.json; idempotent and resumable.

Usage:
    python submit_jobs.py            # submit all not-yet-submitted
    python submit_jobs.py --limit 1  # smoke test
"""

import argparse
import json
from pathlib import Path

import requests

HERE = Path(__file__).parent
ASSOC = HERE / "data" / "associations.json"
RUNS = HERE / "runs"
STATE = RUNS / "jobs.json"

API_BASE = "http://localhost:15001/api/v1"
API_KEY = "blv_901165f3f25fd0cf893d56848bfbbdc7b9d61b1dc2bc8969"

RETRIEVER_MODEL_ID = "Qwen__Qwen3-Embedding-0.6B"
N_ARTICLES = 1000

LLM_MODEL = "openai/gpt-oss-120b"
LLM_BASE_URL = "http://143.248.74.105:11434/v1"
LLM_API_KEY = "bislaprom3#"
LLM_CONCURRENCY = 256
LLM_TEMPERATURE = 0.0
LLM_SYSTEM_PROMPT = """Classify whether the given ABSTRACT supports, contradicts, or is neutral toward the HYPOTHESIS.

OUTPUT FORMAT (JSON):
{
  "verdict": "SUPPORT" | "REJECT" | "NEUTRAL",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "rationale": "justification referencing the abstract, about 2-3 sentences"
}"""


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    assoc = json.loads(ASSOC.read_text())
    print(f"{len(assoc)} associations")

    state = load_state()
    headers = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    submitted = 0

    for a in assoc:
        rid = str(a["row_id"])
        if rid in state:
            continue
        if args.limit is not None and submitted >= args.limit:
            break

        hyp = a["hypothesis"]
        query_term = json.dumps({"q": hyp, "n": N_ARTICLES, "model_id": RETRIEVER_MODEL_ID})
        body = {
            "name": f"biomarker-{rid}",
            "query_term": query_term,
            "hypothesis": hyp,
            "max_articles": N_ARTICLES,
            "source_type": "qwen_retriever",
            "openai_model": LLM_MODEL,
            "openai_base_url": LLM_BASE_URL,
            "openai_api_key": LLM_API_KEY,
            "system_prompt": LLM_SYSTEM_PROMPT,
            "llm_concurrency_limit": LLM_CONCURRENCY,
            "llm_temperature": LLM_TEMPERATURE,
        }
        resp = requests.post(f"{API_BASE}/jobs", headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        job = resp.json()
        state[rid] = {
            "job_id": job["id"],
            "category": a["category"],
            "level": a["level"],
            "expected": a["expected"],
            "hypothesis": hyp,
            "pmids": a["pmids"],
        }
        submitted += 1
        save_state(state)
        print(f"  biomarker-{rid} -> job {job['id']} ({a['category']})")

    print(f"done. {submitted} new, {len(state)} total tracked.")


if __name__ == "__main__":
    main()
