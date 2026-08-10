"""Submit believe jobs for biomarker_v3 — 10,000 articles per hypothesis,
new project (eval-oncokb-v3). State runs/jobs.json keyed by row_id.

Usage: python submit.py [--limit N]
"""
import argparse, json
from pathlib import Path
import requests

HERE = Path(__file__).parent
ASSOC = json.loads((HERE / "data" / "associations.json").read_text())
RUNS = HERE / "runs"; STATE = RUNS / "jobs.json"

API_BASE = "http://localhost:15001/api/v1"
API_KEY = "blv_110aeb494760c8b7b27e6d8b07bf304c14bae5eb7cc9c464"   # project eval-oncokb-v3 (id 33)
RETRIEVER_MODEL_ID = "Qwen__Qwen3-Embedding-0.6B"
N_ARTICLES = 10000
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


def load(): return json.loads(STATE.read_text()) if STATE.exists() else {}
def save(s): RUNS.mkdir(parents=True, exist_ok=True); STATE.write_text(json.dumps(s, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=None); args = ap.parse_args()
    state = load(); H = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}; sub = 0
    for a in ASSOC:
        rid = str(a["row_id"])
        if rid in state: continue
        if args.limit is not None and sub >= args.limit: break
        hyp = a["hypothesis"]
        body = {"name": f"bmv3-{rid}",
                "query_term": json.dumps({"q": hyp, "n": N_ARTICLES, "model_id": RETRIEVER_MODEL_ID}),
                "hypothesis": hyp, "max_articles": N_ARTICLES, "source_type": "qwen_retriever",
                "openai_model": LLM_MODEL, "openai_base_url": LLM_BASE_URL, "openai_api_key": LLM_API_KEY,
                "system_prompt": LLM_SYSTEM_PROMPT, "llm_concurrency_limit": LLM_CONCURRENCY, "llm_temperature": LLM_TEMPERATURE}
        j = requests.post(f"{API_BASE}/jobs", headers=H, json=body, timeout=60).json()
        state[rid] = {"job_id": j["id"], "category": a["category"], "level": a["level"],
                      "expected": a["expected"], "biomarker": a["biomarker"], "drug": a["drug"],
                      "cancer_type": a["cancer_type"], "hypothesis": hyp}
        sub += 1; save(state)
        print(f"  bmv3-{rid} -> job {j['id']} ({a['category']}/{a['level']})")
    print(f"done. {sub} new, {len(state)} total tracked.")


if __name__ == "__main__":
    main()
