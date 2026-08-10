"""Compare believe's literature signal to CELLxGENE tissue-specificity.

Genes are data-derived (housekeeping = lowest tau, tissue_specific = highest).
Hypothesis: "In human {tissue}, {gene} expression has been reported to be
up- or down-regulated." believe per (gene,tissue) support count = literature
signal that the gene is differentially expressed there.

Ground truth: data/gene_ranking.csv (tau, top_tissue) from CELLxGENE.
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
from scipy.stats import spearmanr

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
FIG = HERE / "figures"; FIG.mkdir(exist_ok=True)
STATE = json.loads((HERE / "runs" / "jobs.json").read_text())
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
    by_job = fetch([v["job_id"] for v in STATE.values()])
    genes = sorted({v["gene"] for v in STATE.values()})
    tissues = sorted({v["tissue_gt"] for v in STATE.values()})

    prof = pd.DataFrame(0.0, index=genes, columns=tissues)
    label = {}
    for v in STATE.values():
        vs = by_job.get(v["job_id"])
        if vs:
            prof.loc[v["gene"], v["tissue_gt"]] = vs[:K].count("support")
        label[v["gene"]] = v["label"]

    believe_max = prof.max(axis=1)
    believe_total = prof.sum(axis=1)

    common = [g for g in genes if g in RANK.index]
    data_tau = RANK.loc[common, "tau"]
    data_top = RANK.loc[common, "top_tissue"]

    print("=== believe literature signal vs CELLxGENE tissue-specificity ===")
    for nm, ser in [("max-support", believe_max), ("total-support", believe_total)]:
        rho, p = spearmanr(ser[common].values, data_tau.values)
        print(f"  Spearman({nm:>13}, data-tau) = {rho:+.3f} (p={p:.1e})")

    hk = [g for g in common if label[g] == "housekeeping"]
    ts = [g for g in common if label[g] == "tissue_specific"]
    print(f"\nbelieve max-support: housekeeping(n={len(hk)}) median={believe_max[hk].median():.0f}, "
          f"tissue-specific(n={len(ts)}) median={believe_max[ts].median():.0f}")

    bel_top = prof.idxmax(axis=1)
    hits = [g for g in ts if believe_max[g] > 0 and bel_top[g] == data_top[g]]
    print(f"believe top-tissue == data top-tissue (tissue-specific, support>0): "
          f"{len(hits)}/{len(ts)} ({len(hits)/len(ts)*100:.0f}%)")

    pd.DataFrame({"believe_max": believe_max[common], "believe_total": believe_total[common],
                  "data_tau": data_tau, "label": [label[g] for g in common],
                  "believe_top": bel_top[common], "data_top": data_top}
                 ).sort_values("data_tau", ascending=False).to_csv(HERE / "runs" / "compare.csv")

    # scatter
    fig, ax = plt.subplots(figsize=(7.5, 6))
    col = ["#e76f51" if label[g] == "tissue_specific" else "#457b9d" for g in common]
    ax.scatter(data_tau.values, believe_max[common].values, c=col, s=32)
    for g in common:
        if believe_max[g] >= 60 or data_tau[g] >= 0.97:
            ax.annotate(g, (data_tau[g], believe_max[g]), fontsize=6)
    rho, _ = spearmanr(believe_max[common].values, data_tau.values)
    ax.set_xlabel("data tau (CELLxGENE tissue-specificity)")
    ax.set_ylabel("believe peak support ('up/down-regulated' reports)")
    ax.set_title(f"believe DE-literature signal vs tissue-specificity\nSpearman ρ = {rho:.3f}  "
                 f"(red=tissue-specific, blue=housekeeping)")
    ax.grid(alpha=0.3); fig.tight_layout(); fig.savefig(FIG / "v2_scatter.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.boxplot([believe_max[hk].values, believe_max[ts].values],
               tick_labels=[f"housekeeping\n(n={len(hk)})", f"tissue-specific\n(n={len(ts)})"])
    ax.set_ylabel("believe peak support")
    ax.set_title("believe separates housekeeping vs tissue-specific")
    fig.tight_layout(); fig.savefig(FIG / "v2_box.png", dpi=150); plt.close(fig)
    print("\nsaved compare.csv, v2_scatter.png, v2_box.png")


if __name__ == "__main__":
    main()
