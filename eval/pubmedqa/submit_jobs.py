"""Bulk-register believe analysis jobs for PubMedQA evaluation.

For every yes/no instance in pqa_labeled (maybe excluded), submit one
qwen_retriever analysis job where the PubMedQA *question* is used both as the
retrieval query and as the hypothesis. Each job retrieves the top-1000 PMIDs
(ranked by the Qwen embedding model) and asks believe's LLM to judge each
abstract as support / reject / neutral.

State (pubid -> job_id, final_decision) is written to runs/jobs.json so the
script is idempotent and resumable.

Usage:
    python submit_jobs.py            # submit all yes/no jobs not yet submitted
    python submit_jobs.py --limit 1  # smoke test: submit just one
"""

import argparse
import json
from pathlib import Path

import requests

HERE = Path(__file__).parent
DATA = HERE / "data" / "pqa_labeled.json"
RUNS = HERE / "runs"
STATE = RUNS / "jobs.json"

API_BASE = "http://localhost:15001/api/v1"
API_KEY = "blv_901165f3f25fd0cf893d56848bfbbdc7b9d61b1dc2bc8969"

RETRIEVER_MODEL_ID = "Qwen__Qwen3-Embedding-0.6B"
N_ARTICLES = 1000

# LLM config for the analysis (verdict) step.
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
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def save_state(state: dict) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="Max new jobs to submit this run")
    args = ap.parse_args()

    rows = json.loads(DATA.read_text())
    yes_no = [r for r in rows if r["final_decision"] in ("yes", "no")]
    print(f"{len(yes_no)} yes/no instances (of {len(rows)} total)")

    state = load_state()
    headers = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    submitted = 0

    for r in yes_no:
        pubid = str(r["pubid"])
        if pubid in state:
            continue
        if args.limit is not None and submitted >= args.limit:
            break

        question = r["question"]
        query_term = json.dumps(
            {"q": question, "n": N_ARTICLES, "model_id": RETRIEVER_MODEL_ID}
        )
        body = {
            "name": f"pqa-{pubid}",
            "query_term": query_term,
            "hypothesis": question,
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
        state[pubid] = {
            "job_id": job["id"],
            "final_decision": r["final_decision"],
            "question": question,
        }
        submitted += 1
        save_state(state)
        print(f"  submitted pqa-{pubid} -> job {job['id']} ({r['final_decision']})")

    print(f"done. {submitted} new jobs submitted, {len(state)} total tracked.")


if __name__ == "__main__":
    main()
