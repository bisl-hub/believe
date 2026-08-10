"""Predictive power by OncoKB evidence level (v2 linked results).

correct = top-K majority verdict equals expected
          (therapeutic levels 1/2/3A/4 -> support, resistance R1/R2 -> reject).
Table across K + line figure.
"""

import json
import subprocess
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
FIG = HERE / "figures"
STATE = json.loads((HERE / "runs" / "jobs.json").read_text())

KS = [1, 5, 10, 25, 50, 100, 250, 500, 1000]
ORDER = ["1", "2", "3A", "4", "R1", "R2"]


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


def maj(vs, k):
    t = vs[:k]
    s, r = t.count("support"), t.count("reject")
    return "support" if s > r else ("reject" if r > s else "none")


def main():
    by_job = fetch([v["job_id"] for v in STATE.values()])
    by_level = defaultdict(list)
    for v in STATE.values():
        vs = by_job.get(v["job_id"])
        if vs:
            by_level[v["level"]].append((vs, v["expected"]))

    levels = [l for l in ORDER if l in by_level]
    n = {l: len(by_level[l]) for l in levels}

    # table
    print(f"OncoKB level별 예측력 (correct% = 기대 verdict 다수결)\n")
    print(f"{'level':>5} {'n':>4} {'exp':>4} | " + " ".join(f"K{k:<4}" for k in KS))
    table = {l: [] for l in levels}
    for l in levels:
        exp = "reject" if l.startswith("R") else "support"
        cells = []
        for k in KS:
            c = sum(1 for vs, e in by_level[l] if maj(vs, k) == e)
            pct = c / n[l] * 100
            table[l].append(pct)
            cells.append(f"{pct:4.0f}")
        print(f"{l:>5} {n[l]:>4} {exp[:3]:>4} | " + "  ".join(cells))

    # figure
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    cmap = {"1": "#1b4332", "2": "#2d6a4f", "3A": "#40916c", "4": "#95d5b2",
            "R1": "#9d4edd", "R2": "#c77dff"}
    for l in levels:
        exp = "REJECT" if l.startswith("R") else "SUPPORT"
        ax.plot(range(len(KS)), table[l], "-o", color=cmap.get(l, "#888"),
                lw=2.2, ms=4, label=f"L{l} (n={n[l]}, →{exp})")
    ax.set_xticks(range(len(KS))); ax.set_xticklabels(KS)
    ax.set_xlabel("top-K articles used"); ax.set_ylabel("predictive power = correct% (by majority)")
    ax.set_ylim(0, 100); ax.grid(alpha=0.3); ax.legend(fontsize=8, ncol=2)
    ax.set_title("Predictive power by OncoKB evidence level\n"
                 "(therapeutic 1>2>3A>4; resistance R1/R2 expect REJECT)")
    fig.tight_layout(); fig.savefig(FIG / "by_level.png", dpi=150); plt.close(fig)
    print(f"\nsaved -> {FIG}/by_level.png")


if __name__ == "__main__":
    main()
