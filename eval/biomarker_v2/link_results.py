"""Link each v2 OncoKB triple to its already-run v1 job (identical hypothesis).
Writes runs/jobs.json = {triple_id: {job_id, drug, biomarker, cancer_type,
level, category, expected}}.
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
T = json.loads((HERE / "data" / "triples.json").read_text())
V1 = json.loads((HERE.parent / "biomarker" / "runs" / "jobs.json").read_text())
OUT = HERE / "runs" / "jobs.json"
OUT.parent.mkdir(exist_ok=True)

v1_by_hyp = {v["hypothesis"]: v for v in V1.values()}

state, missing = {}, 0
for o in T:
    hyp = f"In {o['cancer_type']}, {o['biomarker']} predicts response to {o['drug']}."
    j = v1_by_hyp.get(hyp)
    if not j:
        missing += 1
        continue
    state[str(o["triple_id"])] = {
        "job_id": j["job_id"], "drug": o["drug"], "biomarker": o["biomarker"],
        "cancer_type": o["cancer_type"], "level": o["level"],
        "category": o["category"], "expected": o["expected"],
    }

OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2))
print(f"linked {len(state)}/{len(T)} triples to v1 jobs (missing {missing})")
