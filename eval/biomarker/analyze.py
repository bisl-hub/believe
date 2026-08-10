"""Score the biomarker eval (unified 'predicts response to' framing).

Every association is phrased as a response claim. Ground truth per row is in
runs/jobs.json `expected`:
  therapeutic -> support   (drug works)
  resistance  -> reject    (drug does not work; response claim is false)

For each job we take the top-K retrieved articles (by qwen_rank) and decide the
majority of support vs reject. A row is *correct* when the majority equals its
expected verdict. Reported per OncoKB level (and overall) across all K.

Reads job_results from Postgres, scoped to our job_ids.
"""

import json
import subprocess
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
STATE = HERE / "runs" / "jobs.json"
OUT = HERE / "runs" / "scores.json"

K_VALUES = [1, 5, 10, 25, 50, 100, 250, 500, 1000]
LEVEL_ORDER = ["1", "2", "3A", "4", "R1", "R2"]
LEVEL_EXPECTED = {"1": "support", "2": "support", "3A": "support", "4": "support",
                  "R1": "reject", "R2": "reject"}


def fetch(job_ids):
    sql = (f"COPY (SELECT job_id, qwen_rank, verdict FROM job_results "
           f"WHERE job_id IN ({','.join(map(str, job_ids))}) "
           f"ORDER BY job_id, qwen_rank NULLS LAST, id) TO STDOUT WITH CSV")
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "hypothesis-db",
         "psql", "-U", "user", "-d", "hypothesis_db", "-c", sql],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True).stdout
    by = defaultdict(list)
    for line in out.splitlines():
        if line.strip():
            j, _r, v = line.split(",", 2)
            by[int(j)].append(v)
    return by


def majority(verdicts, k):
    top = verdicts[:k]
    s, r = top.count("support"), top.count("reject")
    if s > r:
        return "support"
    if r > s:
        return "reject"
    return "none"  # all-neutral or exact tie


def main():
    state = json.loads(STATE.read_text())
    by_job = fetch([info["job_id"] for info in state.values()])

    # level -> list of (job_id, expected)
    by_level = defaultdict(list)
    for info in state.values():
        if by_job.get(info["job_id"]):
            by_level[info["level"]].append(info)

    levels = [l for l in LEVEL_ORDER if l in by_level]
    report = {"by_level": {l: {"n": len(by_level[l]), "expected": LEVEL_EXPECTED[l]}
                           for l in levels}, "by_k": {}}

    for k in K_VALUES:
        print(f"\n===== K = {k} =====")
        print(f"{'level':>6} {'n':>5} {'exp':>4} | {'support%':>8} {'reject%':>7} {'none%':>6} | {'correct%':>8}")
        report["by_k"][k] = {}
        for lvl in levels:
            items = by_level[lvl]
            exp = LEVEL_EXPECTED[lvl]
            agg = defaultdict(int)
            for info in items:
                agg[majority(by_job[info["job_id"]], k)] += 1
            n = len(items)
            sp, rj, no = agg["support"], agg["reject"], agg["none"]
            correct = agg[exp]
            report["by_k"][k][lvl] = {
                "support": sp, "reject": rj, "none": no,
                "support_pct": round(sp / n, 4), "reject_pct": round(rj / n, 4),
                "none_pct": round(no / n, 4), "correct_pct": round(correct / n, 4),
            }
            print(f"{lvl:>6} {n:>5} {exp[:3]:>4} | {sp/n*100:>7.1f}% {rj/n*100:>6.1f}% "
                  f"{no/n*100:>5.1f}% | {correct/n*100:>7.1f}%")

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\ncorrect% = 기대 verdict(치료=support, 내성=reject) 다수결 비율")
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
