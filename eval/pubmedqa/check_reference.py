"""Check whether each PubMedQA question's *source paper* (its `pubid`) was
retrieved by the Qwen retriever, and at what rank.

Each job's job_results rows carry (pmid, qwen_rank). For every question we look
up whether the gold pubid appears among the retrieved PMIDs and its rank, then
report recall@K for the same K sweep used in scoring.
"""

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent  # eval/pubmedqa -> repo root (has docker-compose.yml)
STATE = HERE / "runs" / "jobs.json"
OUT = HERE / "runs" / "reference_recall.json"

K_VALUES = [1, 10, 100, 500, 1000]


def main() -> None:
    state = json.loads(STATE.read_text())
    # (job_id, gold_pubid) pairs
    pairs = [(info["job_id"], str(pubid)) for pubid, info in state.items()]

    # Row-value IN: find the gold paper's rank within its own job's results.
    values = ",".join(f"({j},'{p}')" for j, p in pairs)
    sql = (
        f"SELECT job_id, pmid, qwen_rank FROM job_results "
        f"WHERE (job_id, pmid) IN ({values})"
    )
    proc = subprocess.run(
        ["docker", "compose", "exec", "-T", "hypothesis-db",
         "psql", "-U", "user", "-d", "hypothesis_db", "-t", "-A", "-F,", "-c", sql],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    )

    # job_id -> rank of its gold paper (if retrieved)
    found_rank = {}
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        job_id, _pmid, rank = line.split(",")
        found_rank[int(job_id)] = int(rank) if rank else None

    total = len(pairs)
    ranks = [found_rank.get(j) for j, _ in pairs]
    found_any = sum(1 for r in ranks if r is not None)

    print(f"{total} questions")
    print(f"source paper retrieved within top-1000: {found_any} ({found_any/total*100:.1f}%)")
    print(f"not retrieved at all: {total - found_any} ({(total-found_any)/total*100:.1f}%)\n")

    report = {"total": total, "found_within_1000": found_any, "recall_at_k": {}}
    print(f"{'K':>5} {'recall@K':>9} {'count':>7}")
    for k in K_VALUES:
        c = sum(1 for r in ranks if r is not None and r <= k)
        report["recall_at_k"][k] = {"recall": round(c / total, 4), "count": c}
        print(f"{k:>5} {c/total*100:>8.1f}% {c:>7}")

    # rank distribution among the ones that were found
    got = sorted(r for r in ranks if r is not None)
    if got:
        import statistics
        report["rank_stats"] = {
            "median": statistics.median(got),
            "mean": round(statistics.mean(got), 1),
            "min": got[0],
            "max": got[-1],
        }
        print(f"\nrank when found — median {statistics.median(got)}, "
              f"mean {statistics.mean(got):.1f}, min {got[0]}, max {got[-1]}")

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
