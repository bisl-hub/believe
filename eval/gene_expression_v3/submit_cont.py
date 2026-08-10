"""Continuous comparison: run believe on genes spanning the FULL tau range
(data/genes_cont.json), reusing existing results where available.
State: runs/jobs_cont.json. New jobs named gexc-.
"""

import json
from pathlib import Path
import requests

HERE = Path(__file__).parent
GENES = json.loads((HERE / "data" / "genes_cont.json").read_text())
STATE_F = HERE / "runs" / "jobs_cont.json"
API_BASE = "http://localhost:15001/api/v1"
API_KEY = "blv_901165f3f25fd0cf893d56848bfbbdc7b9d61b1dc2bc8969"
TISSUES = [("brain","brain"),("blood","blood"),("lung","lung"),("liver","liver"),
           ("heart","heart"),("kidney","kidney"),("pancreas","pancreas"),("colon","colon"),
           ("small intestine","small intestine"),("stomach","stomach"),("spleen","spleen"),
           ("skin of body","skin"),("adipose tissue","adipose tissue"),("musculature","skeletal muscle"),
           ("breast","breast"),("bone marrow","bone marrow"),("lymph node","lymph node"),
           ("esophagus","esophagus"),("uterus","uterus"),("placenta","placenta")]
SP='''Classify whether the given ABSTRACT supports, contradicts, or is neutral toward the HYPOTHESIS.

OUTPUT FORMAT (JSON):
{
  "verdict": "SUPPORT" | "REJECT" | "NEUTRAL",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "rationale": "justification referencing the abstract, about 2-3 sentences"
}'''


def main():
    # reuse from prior believe runs
    reuse = {}
    for f in ["jobs.json", "jobs_gexb60.json"]:
        p = HERE / "runs" / f
        if p.exists():
            for v in json.loads(p.read_text()).values():
                reuse[(v["gene"], v["tissue"])] = v["job_id"]
    state = json.loads(STATE_F.read_text()) if STATE_F.exists() else {}
    H = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}
    new = reused = 0
    for gi, g in enumerate(GENES):
        for ti, (gt, disp) in enumerate(TISSUES):
            pid = f"{gi}_{ti}"
            if pid in state:
                continue
            if (g, disp) in reuse:
                state[pid] = {"job_id": reuse[(g, disp)], "gene": g, "tissue": disp, "tissue_gt": gt}
                reused += 1
            else:
                hyp = f"In human {disp}, {g} expression has been reported to be up- or down-regulated."
                body = {"name": f"gexc-{pid}", "query_term": json.dumps({"q": hyp, "n": 1000, "model_id": "Qwen__Qwen3-Embedding-0.6B"}),
                        "hypothesis": hyp, "max_articles": 1000, "source_type": "qwen_retriever",
                        "openai_model": "openai/gpt-oss-120b", "openai_base_url": "http://143.248.74.105:11434/v1",
                        "openai_api_key": "bislaprom3#", "system_prompt": SP,
                        "llm_concurrency_limit": 256, "llm_temperature": 0.0}
                j = requests.post(f"{API_BASE}/jobs", headers=H, json=body, timeout=60).json()
                state[pid] = {"job_id": j["id"], "gene": g, "tissue": disp, "tissue_gt": gt}
                new += 1
            if (new + reused) % 200 == 0:
                STATE_F.write_text(json.dumps(state, ensure_ascii=False))
    STATE_F.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    print(f"new {new}, reused {reused}, total {len(state)}")


if __name__ == "__main__":
    main()
