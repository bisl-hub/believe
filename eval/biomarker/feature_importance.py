"""Feature importance via ablation: how much does removing each field change
believe's verdict, measured PER ROW.

For every original row we compare its full hypothesis (A0) against the
alteration-removed (A1) and cancer-removed (A2) versions, at top-K=1000:

  net support score  = (#support - #reject) / (top-K count)   in [-1, +1]
  flip               = majority verdict changed vs A0

Field importance =
  - flip rate : fraction of rows whose majority verdict changed when removed
  - |Δnet|    : mean absolute change in the net support score when removed
Reported per category, plus the direction of resistance flips. Saves a figure.
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
FIG.mkdir(exist_ok=True)

MAIN = json.loads((HERE / "runs" / "jobs.json").read_text())
ABL = json.loads((HERE / "runs" / "ablation_jobs.json").read_text())
K = 1000


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


def stats(vs):
    top = vs[:K]
    n = len(top)
    s, r = top.count("support"), top.count("reject")
    maj = "support" if s > r else ("reject" if r > s else "none")
    net = (s - r) / n if n else 0.0
    return maj, net


def arm_row_job(arm):
    m = {}
    for h in ABL[arm].values():
        for rid in h["row_ids"]:
            m[str(rid)] = h["job_id"]
    return m


def main():
    a1, a2 = arm_row_job("A1"), arm_row_job("A2")
    ids = [v["job_id"] for v in MAIN.values()]
    ids += [h["job_id"] for arm in ("A1", "A2") for h in ABL[arm].values()]
    by_job = fetch(ids)

    # per category accumulate
    agg = {c: {"n": 0,
               "alt_flip": 0, "can_flip": 0,
               "alt_dnet": 0.0, "can_dnet": 0.0,
               "alt_rej2sup": 0, "alt_sup2rej": 0}
           for c in ("therapeutic", "resistance")}

    for rid, info in MAIN.items():
        cat = info["category"]
        v0 = by_job.get(info["job_id"])
        v1 = by_job.get(a1.get(rid))
        v2 = by_job.get(a2.get(rid))
        if not (v0 and v1 and v2):
            continue
        m0, net0 = stats(v0)
        m1, net1 = stats(v1)
        m2, net2 = stats(v2)
        a = agg[cat]
        a["n"] += 1
        a["alt_flip"] += (m1 != m0)
        a["can_flip"] += (m2 != m0)
        a["alt_dnet"] += abs(net1 - net0)
        a["can_dnet"] += abs(net2 - net0)
        if m0 == "reject" and m1 == "support":
            a["alt_rej2sup"] += 1
        if m0 == "support" and m1 == "reject":
            a["alt_sup2rej"] += 1

    print(f"=== Feature importance (per-row ablation, top-{K}) ===\n")
    print(f"{'category':>11} {'n':>4} | {'-alteration':>22} | {'-cancer':>18}")
    print(f"{'':>11} {'':>4} | {'flip%':>9} {'|Δnet|':>11} | {'flip%':>8} {'|Δnet|':>9}")
    for c in ("therapeutic", "resistance"):
        a = agg[c]
        n = a["n"] or 1
        print(f"{c:>11} {a['n']:>4} | {a['alt_flip']/n*100:>8.1f}% {a['alt_dnet']/n:>11.3f} | "
              f"{a['can_flip']/n*100:>7.1f}% {a['can_dnet']/n:>9.3f}")
    print()
    ar = agg["resistance"]
    print(f"resistance flip direction when alteration removed: "
          f"reject→support {ar['alt_rej2sup']}, support→reject {ar['alt_sup2rej']}")

    # ---- figure ----
    cats = ["therapeutic", "resistance"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    # left: flip rate
    altf = [agg[c]["alt_flip"] / (agg[c]["n"] or 1) * 100 for c in cats]
    canf = [agg[c]["can_flip"] / (agg[c]["n"] or 1) * 100 for c in cats]
    x = range(len(cats))
    axes[0].bar([i - 0.2 for i in x], altf, 0.4, label="remove alteration", color="#e76f51")
    axes[0].bar([i + 0.2 for i in x], canf, 0.4, label="remove cancer", color="#457b9d")
    axes[0].set_xticks(list(x)); axes[0].set_xticklabels(cats)
    axes[0].set_ylabel("% of rows whose verdict CHANGED")
    axes[0].set_title("Verdict flip rate (which field is load-bearing)")
    for i, (av, cv) in enumerate(zip(altf, canf)):
        axes[0].text(i - 0.2, av + 1, f"{av:.0f}", ha="center", fontsize=8)
        axes[0].text(i + 0.2, cv + 1, f"{cv:.0f}", ha="center", fontsize=8)
    axes[0].legend(fontsize=8)
    # right: |Δnet|
    altd = [agg[c]["alt_dnet"] / (agg[c]["n"] or 1) for c in cats]
    cand = [agg[c]["can_dnet"] / (agg[c]["n"] or 1) for c in cats]
    axes[1].bar([i - 0.2 for i in x], altd, 0.4, label="remove alteration", color="#e76f51")
    axes[1].bar([i + 0.2 for i in x], cand, 0.4, label="remove cancer", color="#457b9d")
    axes[1].set_xticks(list(x)); axes[1].set_xticklabels(cats)
    axes[1].set_ylabel("mean |Δ net-support score|  (0..2)")
    axes[1].set_title("Magnitude of verdict change")
    for i, (av, cv) in enumerate(zip(altd, cand)):
        axes[1].text(i - 0.2, av + 0.01, f"{av:.2f}", ha="center", fontsize=8)
        axes[1].text(i + 0.2, cv + 0.01, f"{cv:.2f}", ha="center", fontsize=8)
    axes[1].legend(fontsize=8)
    fig.suptitle("Feature importance by ablation: alteration is decisive for resistance; "
                 "for therapeutic both fields matter modestly", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "6_feature_importance.png", dpi=150)
    plt.close(fig)
    print(f"\nsaved -> {FIG}/6_feature_importance.png")


if __name__ == "__main__":
    main()
