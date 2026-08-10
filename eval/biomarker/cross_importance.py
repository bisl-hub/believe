"""Within-cancer alteration importance: for each cancer type, which specific
alterations most change believe's verdict when generalized away (A0 vs A1).

Data is sparse per (cancer, alteration), so we focus on the cancers with the
most distinct alterations and show their internal alteration ranking as
small-multiple bar charts + a heatmap for the richest cancers.
"""

import json
import subprocess
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
FIG = HERE / "figures"

ASSOC = json.loads((HERE / "data" / "associations.json").read_text())
MAIN = json.loads((HERE / "runs" / "jobs.json").read_text())
ABL = json.loads((HERE / "runs" / "ablation_jobs.json").read_text())
META = {str(o["row_id"]): o for o in ASSOC}
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


def net(vs):
    top = vs[:K]
    n = len(top)
    return ((top.count("support") - top.count("reject")) / n) if n else 0.0


def main():
    a1 = {}
    for h in ABL["A1"].values():
        for rid in h["row_ids"]:
            a1[str(rid)] = h["job_id"]

    ids = [v["job_id"] for v in MAIN.values()] + [h["job_id"] for h in ABL["A1"].values()]
    by_job = fetch(ids)

    # (cancer, alteration) -> [sum|dnet|, sum signed, n]
    cell = defaultdict(lambda: [0.0, 0.0, 0])
    cancer_n = defaultdict(int)
    for rid, info in MAIN.items():
        v0 = by_job.get(info["job_id"])
        v1 = by_job.get(a1.get(rid))
        if not (v0 and v1):
            continue
        d = net(v1) - net(v0)
        c, alt = META[rid]["cancer_type"], META[rid]["alteration"]
        cell[(c, alt)][0] += abs(d)
        cell[(c, alt)][1] += d
        cell[(c, alt)][2] += 1
        cancer_n[c] += 1

    # cancers ranked by number of DISTINCT alterations with data
    cancer_alts = defaultdict(list)
    for (c, alt), (sa, ss, n) in cell.items():
        cancer_alts[c].append((alt, sa / n, ss / n, n))
    richest = sorted(cancer_alts.items(), key=lambda kv: -len(kv[1]))

    print("=== cancers by # distinct alterations (top 12) ===")
    for c, alts in richest[:12]:
        print(f"  {len(alts):>3} alterations, {cancer_n[c]:>3} rows  | {c}")

    # ---- small multiples: top 6 richest cancers, alteration importance within ----
    top_cancers = [c for c, alts in richest if len(alts) >= 4][:6]
    fig, axes = plt.subplots(2, 3, figsize=(20, 11))
    for ax, c in zip(axes.flat, top_cancers):
        alts = sorted(cancer_alts[c], key=lambda x: x[1])[-10:]
        labels = [(a[:20] + "…") if len(a) > 21 else a for a, _i, _s, _n in alts]
        imp = [i for _a, i, _s, _n in alts]
        signed = [s for _a, _i, s, _n in alts]
        colors = ["#e76f51" if s > 0 else "#2a9d8f" for s in signed]
        ax.barh(range(len(alts)), imp, color=colors)
        ax.set_yticks(range(len(alts)))
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_title(f"{c[:40]}  ({cancer_n[c]} rows)", fontsize=11, fontweight="bold")
        ax.set_xlabel("importance |Δnet|", fontsize=9)
        ax.tick_params(axis="x", labelsize=8)
        ax.margins(x=0.18)
    for ax in axes.flat[len(top_cancers):]:
        ax.axis("off")
    fig.suptitle("Within each cancer: which alteration matters most  "
                 "(red = removing it shifts toward SUPPORT, green = toward REJECT)", fontsize=14)
    fig.subplots_adjust(left=0.16, right=0.98, top=0.92, bottom=0.06, hspace=0.35, wspace=0.6)
    fig.savefig(FIG / "9_cancer_x_alteration.png", dpi=140)
    plt.close(fig)
    print(f"\nsaved -> {FIG}/9_cancer_x_alteration.png")

    # print per-cancer top alterations
    for c in top_cancers:
        top = sorted(cancer_alts[c], key=lambda x: -x[1])[:6]
        print(f"\n{c} ({cancer_n[c]} rows):")
        for a, i, s, n in top:
            print(f"   {a[:36]:<36} imp={i:.3f} signed={s:+.3f} n={n}")


if __name__ == "__main__":
    main()
