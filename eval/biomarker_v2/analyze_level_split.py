"""Predictive power by OncoKB level, separating the 'no-evidence' cases.

At top-K, a triple is:
  none   : 0 support AND 0 reject among top-K  (literature silent — no evidence)
  decided: otherwise (support or reject majority; equal nonzero = tie, not correct)

Reports per level & K:
  none%               : fraction with zero support/reject evidence
  correct% (all)      : correct / all
  correct% (decided)  : correct / (all - none)   <- predictive power WHEN evidence exists
Two-panel figure.
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


def classify(vs, k, expected):
    t = vs[:k]
    s, r = t.count("support"), t.count("reject")
    if s == 0 and r == 0:
        return "none"
    pred = "support" if s > r else ("reject" if r > s else "tie")
    return "correct" if pred == expected else "wrong"


def main():
    by_job = fetch([v["job_id"] for v in STATE.values()])
    by_level = defaultdict(list)
    for v in STATE.values():
        vs = by_job.get(v["job_id"])
        if vs:
            by_level[v["level"]].append((vs, v["expected"]))
    levels = [l for l in ORDER if l in by_level]
    n = {l: len(by_level[l]) for l in levels}

    none_tab = {l: [] for l in levels}
    dec_tab = {l: [] for l in levels}

    print("none% = 근거(support/reject) 0인 비율   |   decided = none 제외 예측력\n")
    print(f"{'level':>5} {'n':>4} |              none%  (K=1..1000)")
    for l in levels:
        cells = []
        for k in KS:
            c = defaultdict(int)
            for vs, e in by_level[l]:
                c[classify(vs, k, e)] += 1
            none_pct = c["none"] / n[l] * 100
            decided = n[l] - c["none"]
            dec_pct = c["correct"] / decided * 100 if decided else 0
            none_tab[l].append(none_pct)
            dec_tab[l].append(dec_pct)
            cells.append(f"{none_pct:4.0f}")
        print(f"{l:>5} {n[l]:>4} | " + "  ".join(cells))

    print(f"\n{'level':>5} {'n':>4} |        decided correct%  (none 제외, K=1..1000)")
    for l in levels:
        print(f"{l:>5} {n[l]:>4} | " + "  ".join(f"{p:4.0f}" for p in dec_tab[l]))

    # figure: 2 panels
    cmap = {"1": "#1b4332", "2": "#2d6a4f", "3A": "#40916c", "4": "#95d5b2",
            "R1": "#9d4edd", "R2": "#c77dff"}
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.2))
    for l in levels:
        exp = "REJECT" if l.startswith("R") else "SUPPORT"
        axes[0].plot(range(len(KS)), dec_tab[l], "-o", color=cmap[l], lw=2.2, ms=4,
                     label=f"L{l} (n={n[l]}, →{exp})")
        axes[1].plot(range(len(KS)), none_tab[l], "-o", color=cmap[l], lw=2.2, ms=4,
                     label=f"L{l}")
    for ax, ttl, yl in [(axes[0], "Predictive power WHEN evidence exists\n(none excluded)",
                         "correct% (decided)"),
                        (axes[1], "No-evidence rate\n(0 support & 0 reject)", "none%")]:
        ax.set_xticks(range(len(KS))); ax.set_xticklabels(KS)
        ax.set_xlabel("top-K"); ax.set_ylabel(yl); ax.set_ylim(0, 100)
        ax.grid(alpha=0.3); ax.legend(fontsize=8, ncol=2); ax.set_title(ttl)
    fig.suptitle("OncoKB level: predictive power vs no-evidence, separated", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(FIG / "by_level_split.png", dpi=150); plt.close(fig)
    print(f"\nsaved -> {FIG}/by_level_split.png")


if __name__ == "__main__":
    main()
