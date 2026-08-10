"""Submit believe jobs for gene×tissue expression hypotheses.

"{gene} is highly expressed in human {tissue}." — SUPPORT = literature says
expressed/enriched there. Same retriever/LLM config as other evals.
State: runs/jobs.json keyed by pair_id. Idempotent.
"""

import argparse
import json
from pathlib import Path

import requests

HERE = Path(__file__).parent
PAIRS = json.loads((HERE / "data" / "pairs.json").read_text())
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


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(s):
    RUNS.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    state = load_state()
    # reuse: (gene,tissue)->job_id from a previous run (same hypothesis wording)
    reuse = {}
    reuse_file = HERE / "runs" / "jobs_gexb60.json"
    if reuse_file.exists():
        for v in json.loads(reuse_file.read_text()).values():
            reuse[(v["gene"], v["tissue"])] = v["job_id"]
    headers = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    submitted = reused = 0
    for p in PAIRS:
        pid = p["pair_id"]
        if pid in state:
            continue
        rk = (p["gene"], p["tissue"])
        if rk in reuse:
            state[pid] = {"job_id": reuse[rk], "gene": p["gene"], "tissue": p["tissue"],
                          "tissue_gt": p["tissue_gt"], "label": p["label"]}
            reused += 1
            if reused % 200 == 0:
                save_state(state)
            continue
        if args.limit is not None and submitted >= args.limit:
            break
        hyp = p["hypothesis"]
        body = {
            "name": f"gexb-{pid}",
            "query_term": json.dumps({"q": hyp, "n": N_ARTICLES, "model_id": RETRIEVER_MODEL_ID}),
            "hypothesis": hyp,
            "max_articles": N_ARTICLES,
            "source_type": "qwen_retriever",
            "openai_model": LLM_MODEL, "openai_base_url": LLM_BASE_URL,
            "openai_api_key": LLM_API_KEY, "system_prompt": LLM_SYSTEM_PROMPT,
            "llm_concurrency_limit": LLM_CONCURRENCY, "llm_temperature": LLM_TEMPERATURE,
        }
        r = requests.post(f"{API_BASE}/jobs", headers=headers, json=body, timeout=60)
        r.raise_for_status()
        job = r.json()
        state[pid] = {"job_id": job["id"], "gene": p["gene"], "tissue": p["tissue"],
                      "tissue_gt": p["tissue_gt"], "label": p["label"]}
        submitted += 1
        save_state(state)
    print(f"submitted {submitted} new, reused {reused}, {len(state)} total tracked")


if __name__ == "__main__":
    main()
