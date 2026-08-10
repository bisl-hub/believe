"""Score believe's PubMedQA evaluation.

For each submitted job we have up to 1000 articles, each LLM-judged as
support / reject / neutral, ordered by the Qwen retriever rank. We treat the
job as a binary classifier of the PubMedQA question:

    predict "yes"  if  (#support > #reject)  among the top-K articles
    predict "no"   if  (#reject  > #support)
    (ties are counted as incorrect)

We then sweep K over {1, 10, 100, 500, 1000} to see how retrieval depth affects
agreement with PubMedQA's gold `final_decision` (maybe excluded upstream).

Reads job_results straight from Postgres (ordered by qwen_rank) for speed.

Usage:
    python analyze.py
"""

import json
import subprocess
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent  # eval/pubmedqa -> repo root (has docker-compose.yml)
STATE = HERE / "runs" / "jobs.json"
OUT = HERE / "runs" / "scores.json"

K_VALUES = [1, 10, 100, 500, 1000]


def fetch_results(job_ids: list) -> dict:
    """job_id -> list of verdicts in retrieval-rank order.

    Scoped strictly to our job_ids — this is a shared DB with many unrelated
    job_results rows, so a full-table scan would be catastrophic.
    """
    id_list = ",".join(str(j) for j in job_ids)
    # Ordering by qwen_rank gives retrieval order; rows without a rank sort last.
    sql = (
        f"COPY (SELECT job_id, qwen_rank, verdict FROM job_results "
        f"WHERE job_id IN ({id_list}) "
        f"ORDER BY job_id, qwen_rank NULLS LAST, id) TO STDOUT WITH CSV"
    )
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "hypothesis-db",
         "psql", "-U", "user", "-d", "hypothesis_db", "-c", sql],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    )
    by_job: dict = defaultdict(list)
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        job_id, _rank, verdict = line.split(",", 2)
        by_job[int(job_id)].append(verdict)
    return by_job


def predict(verdicts: list, k: int) -> str | None:
    """Majority of support vs reject among top-k. None on tie/empty."""
    top = verdicts[:k]
    s = top.count("support")
    r = top.count("reject")
    if s > r:
        return "yes"
    if r > s:
        return "no"
    return None  # tie -> counted as wrong


def main() -> None:
    state = json.loads(STATE.read_text())
    job_ids = [info["job_id"] for info in state.values()]
    by_job = fetch_results(job_ids)

    # Build per-question (gold, verdict-list).
    items = []
    missing = 0
    for pubid, info in state.items():
        verdicts = by_job.get(info["job_id"])
        if not verdicts:
            missing += 1
            continue
        items.append((info["final_decision"], verdicts))

    print(f"{len(items)} jobs with results, {missing} missing/empty.\n")

    report = {"n_jobs": len(items), "missing": missing, "by_k": {}}
    for k in K_VALUES:
        correct = wrong = tie = 0
        # confusion: gold -> {yes,no,tie}
        conf = {"yes": defaultdict(int), "no": defaultdict(int)}
        for gold, verdicts in items:
            pred = predict(verdicts, k)
            if pred is None:
                tie += 1
                conf[gold]["tie"] += 1
                wrong += 1
                continue
            conf[gold][pred] += 1
            if pred == gold:
                correct += 1
            else:
                wrong += 1
        n = correct + wrong
        acc = correct / n if n else 0.0
        report["by_k"][k] = {
            "accuracy": round(acc, 4),
            "correct": correct,
            "wrong": wrong,
            "ties": tie,
            "confusion": {g: dict(conf[g]) for g in conf},
        }
        print(f"K={k:<5} acc={acc:.4f}  correct={correct} wrong={wrong} (ties={tie})")

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
