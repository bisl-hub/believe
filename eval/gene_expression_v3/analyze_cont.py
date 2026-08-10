"""Continuous comparison: believe peak-support vs CELLxGENE tau across the full
tau range (genes_cont.json). Scatter + Spearman + binned trend.
"""

import json
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, pearsonr

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
FIG = HERE / "figures"
STATE = json.loads((HERE / "runs" / "jobs_cont.json").read_text())
RANK = pd.read_csv(HERE / "data" / "gene_ranking.csv", index_col=0)
K = 1000


def fetch(job_ids):
    sql = (f"COPY (SELECT job_id, qwen_rank, verdict FROM job_results "
           f"WHERE job_id IN ({','.join(map(str, job_ids))}) "
           f"ORDER BY job_id, qwen_rank NULLS LAST, id) TO STDOUT WITH CSV")
    out = subprocess.run(["docker", "compose", "exec", "-T", "hypothesis-db",
                          "psql", "-U", "user", "-d", "hypothesis_db", "-c", sql],
                         cwd=str(REPO_ROOT), capture_output=True, text=True, check=True).stdout
    by = defaultdict(list)
    for line in out.splitlines():
        if line.strip():
            j, _r, v = line.split(",", 2)
            by[int(j)].append(v)
    return by


def main():
    by_job = fetch(list({v["job_id"] for v in STATE.values()}))
    genes = sorted({v["gene"] for v in STATE.values()})
    tissues = sorted({v["tissue_gt"] for v in STATE.values()})
    sup = pd.DataFrame(0.0, index=genes, columns=tissues)
    for v in STATE.values():
        vs = by_job.get(v["job_id"])
        if vs:
            sup.loc[v["gene"], v["tissue_gt"]] = vs[:K].count("support")

    peak = sup.max(axis=1)
    total = sup.sum(axis=1)
    common = [g for g in genes if g in RANK.index]
    tau = RANK.loc[common, "tau"]

    rs, ps = spearmanr(peak[common], tau)
    rs2, _ = spearmanr(total[common], tau)
    print(f"{len(common)} genes spanning tau {tau.min():.2f}~{tau.max():.2f}")
    print(f"Spearman(peak_support, tau)  = {rs:+.3f} (p={ps:.1e})")
    print(f"Spearman(total_support, tau) = {rs2:+.3f}")
    # log-scale pearson on peak
    rp, _ = pearsonr(np.log1p(peak[common]), tau)
    print(f"Pearson(log1p(peak), tau)    = {rp:+.3f}")

    # binned trend
    bins = np.linspace(tau.min(), 1.0, 8)
    df = pd.DataFrame({"tau": tau, "peak": peak[common]})
    df["bin"] = pd.cut(df.tau, bins)
    binned = df.groupby("bin", observed=True)["peak"].median()
    print("\nmedian peak-support by tau bin:")
    print(binned.to_string())

    # scatter
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(tau, peak[common], c=tau, cmap="viridis", s=34, edgecolor="none")
    # binned median line
    centers = [iv.mid for iv in binned.index]
    ax.plot(centers, binned.values, "-o", color="crimson", lw=2, label="median per tau-bin")
    for g in common:
        if peak[g] >= 60:
            ax.annotate(g, (tau[g], peak[g]), fontsize=6)
    ax.set_xlabel("data tau (CELLxGENE tissue-specificity, continuous)")
    ax.set_ylabel("believe peak support")
    ax.set_title(f"believe signal vs continuous tissue-specificity\nSpearman ρ = {rs:.3f} (n={len(common)}, full tau range)")
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout(); fig.savefig(FIG / "cont_scatter.png", dpi=150); plt.close(fig)
    print(f"\nsaved cont_scatter.png")


if __name__ == "__main__":
    main()
