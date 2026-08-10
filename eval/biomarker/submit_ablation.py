"""Submit the ablation arms (A1/A2/A3) — one job per unique hypothesis.

Same retriever/LLM config as the main run. State per (arm, hyp_id) in
runs/ablation_jobs.json; idempotent and resumable.

Usage:
    python submit_ablation.py            # all arms
    python submit_ablation.py --arm A1   # one arm
    python submit_ablation.py --arm A1 --limit 1
"""

import argparse
import json
from pathlib import Path

import requests

HERE = Path(__file__).parent
ABL = HERE / "data" / "ablation.json"
RUNS = HERE / "runs"
STATE = RUNS / "ablation_jobs.json"

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


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s):
    RUNS.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["A1", "A2", "A3"], default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    abl = json.loads(ABL.read_text())
    arms = [args.arm] if args.arm else ["A1", "A2", "A3"]
    state = load_state()
    headers = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    submitted = 0

    for arm in arms:
        state.setdefault(arm, {})
        for h in abl[arm]:
            hid = h["hyp_id"]
            if hid in state[arm]:
                continue
            if args.limit is not None and submitted >= args.limit:
                break
            hyp = h["hypothesis"]
            query_term = json.dumps({"q": hyp, "n": N_ARTICLES, "model_id": RETRIEVER_MODEL_ID})
            body = {
                "name": f"bmk-abl-{hid}",
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
            state[arm][hid] = {"job_id": job["id"], "hypothesis": hyp, "row_ids": h["row_ids"]}
            submitted += 1
            save_state(state)
        print(f"{arm}: {len(state[arm])}/{len(abl[arm])} submitted")

    print(f"done. {submitted} new this run.")


if __name__ == "__main__":
    main()
