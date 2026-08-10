"""LLM verdict on the *source paper itself*.

For each question whose gold paper (`pubid`) was retrieved, fetch the LLM's
verdict on exactly that paper, then score: support->yes, reject->no,
neutral->undecided. This isolates the LLM's judgment quality, free of retrieval
ranking and majority-vote noise.
"""

import json
import subprocess
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent  # eval/pubmedqa -> repo root (has docker-compose.yml)
STATE = HERE / "runs" / "jobs.json"
OUT = HERE / "runs" / "gold_verdict.json"

VERDICT_TO_PRED = {"support": "yes", "reject": "no", "neutral": None}


def main() -> None:
    state = json.loads(STATE.read_text())
    pairs = [(info["job_id"], str(pubid), info["final_decision"])
             for pubid, info in state.items()]
    gold_by_job = {j: g for j, _p, g in pairs}

    values = ",".join(f"({j},'{p}')" for j, p, _g in pairs)
    sql = (
        f"SELECT job_id, verdict FROM job_results "
        f"WHERE (job_id, pmid) IN ({values})"
    )
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "hypothesis-db",
         "psql", "-U", "user", "-d", "hypothesis_db", "-t", "-A", "-F,", "-c", sql],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    )

    verdict_by_job = {}
    for line in proc.stdout.splitlines():
        if line.strip():
            j, v = line.split(",")
            verdict_by_job[int(j)] = v

    # SRN distribution on the gold paper, split by gold label
    dist = {"yes": defaultdict(int), "no": defaultdict(int)}
    for j, gold in gold_by_job.items():
        v = verdict_by_job.get(j)
        if v is None:
            dist[gold]["(not retrieved)"] += 1
        else:
            dist[gold][v] += 1

    print("=== LLM verdict on the source paper, by gold label ===")
    print(f"{'gold':>5} | {'support':>8} {'reject':>7} {'neutral':>8} {'not-retr':>9} | total")
    for g in ("yes", "no"):
        d = dist[g]
        tot = sum(d.values())
        print(f"{g:>5} | {d['support']:>8} {d['reject']:>7} {d['neutral']:>8} "
              f"{d['(not retrieved)']:>9} | {tot}")

    # Accuracy on the gold paper (only where retrieved)
    correct = wrong = neutral = 0
    for j, gold in gold_by_job.items():
        v = verdict_by_job.get(j)
        if v is None:
            continue  # gold paper not retrieved -> excluded
        pred = VERDICT_TO_PRED[v]
        if pred is None:
            neutral += 1
        elif pred == gold:
            correct += 1
        else:
            wrong += 1

    retrieved = correct + wrong + neutral
    print(f"\n=== Accuracy using ONLY the gold paper's verdict ({retrieved} retrieved) ===")
    print(f"neutral counted as wrong : {correct/retrieved*100:.1f}%  "
          f"(correct {correct} / {retrieved})")
    decided = correct + wrong
    print(f"neutral excluded         : {correct/decided*100:.1f}%  "
          f"(correct {correct} / decided {decided})")
    print(f"  support->yes / reject->no correct = {correct}, "
          f"wrong = {wrong}, neutral (undecided) = {neutral}")

    report = {
        "distribution": {g: dict(dist[g]) for g in dist},
        "retrieved": retrieved,
        "correct": correct, "wrong": wrong, "neutral": neutral,
        "acc_neutral_wrong": round(correct / retrieved, 4) if retrieved else None,
        "acc_neutral_excluded": round(correct / decided, 4) if decided else None,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
