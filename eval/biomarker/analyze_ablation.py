"""Context-contribution analysis: compare ablation arms A1/A2/A3 to A0.

Each ablation hypothesis was run once and covers several original rows. We map
its top-K majority verdict back to every original row it covers, then score each
row against its own `expected` label (therapeutic->support, resistance->reject).
This lets us compare, per category, how generalizing a field changes believe's
verdict relative to the full hypothesis (A0).

A0 results come from runs/jobs.json; A1/A2/A3 from runs/ablation_jobs.json.
"""

import json
import subprocess
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
MAIN = HERE / "runs" / "jobs.json"
ABL = HERE / "runs" / "ablation_jobs.json"
OUT = HERE / "runs" / "ablation_scores.json"

K_VALUES = [1, 10, 100, 1000]


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
    return "none"


def main():
    main_state = json.loads(MAIN.read_text())  # row_id -> {job_id, category, expected,...}
    abl_state = json.loads(ABL.read_text())     # arm -> hyp_id -> {job_id, row_ids}

    # row_id -> meta (expected, category)
    row_meta = {rid: {"expected": v["expected"], "category": v["category"]}
                for rid, v in main_state.items()}

    # Collect job ids: A0 per-row + ablation per-hyp
    a0_jobs = {rid: v["job_id"] for rid, v in main_state.items()}
    all_ids = set(a0_jobs.values())
    # arm -> row_id -> job_id (map each covered row to its hypothesis job)
    arm_row_job = {}
    for arm, hyps in abl_state.items():
        m = {}
        for h in hyps.values():
            for rid in h["row_ids"]:
                m[str(rid)] = h["job_id"]
            all_ids.add(h["job_id"])
        arm_row_job[arm] = m

    by_job = fetch(list(all_ids))

    arms = ["A0", "A1", "A2", "A3"]

    def row_job(arm, rid):
        return a0_jobs[rid] if arm == "A0" else arm_row_job[arm].get(rid)

    report = {}
    for k in K_VALUES:
        print(f"\n================= K = {k} =================")
        header = f"{'arm':>4} | {'category':>11} {'n':>5} | {'support%':>8} {'reject%':>7} {'none%':>6} | {'correct%':>8}"
        print(header)
        report[k] = {}
        for arm in arms:
            for cat in ("therapeutic", "resistance"):
                rows = [rid for rid, m in row_meta.items() if m["category"] == cat]
                agg = defaultdict(int)
                n = 0
                for rid in rows:
                    jid = row_job(arm, rid)
                    v = by_job.get(jid)
                    if not v:
                        continue
                    n += 1
                    agg[majority(v, k)] += 1
                if not n:
                    continue
                exp = "support" if cat == "therapeutic" else "reject"
                sp, rj, no = agg["support"], agg["reject"], agg["none"]
                report[k].setdefault(arm, {})[cat] = {
                    "n": n, "support": sp, "reject": rj, "none": no,
                    "support_pct": round(sp / n, 4), "reject_pct": round(rj / n, 4),
                    "none_pct": round(no / n, 4), "correct_pct": round(agg[exp] / n, 4),
                }
                print(f"{arm:>4} | {cat:>11} {n:>5} | {sp/n*100:>7.1f}% {rj/n*100:>6.1f}% "
                      f"{no/n*100:>5.1f}% | {agg[exp]/n*100:>7.1f}%")
            print("     |")

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nA0=full · A1=−alteration · A2=−cancer · A3=gene-only")
    print(f"correct% = therapeutic→support / resistance→reject 다수결 비율")
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
