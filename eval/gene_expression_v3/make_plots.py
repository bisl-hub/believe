"""Reject-aware scoring + intuitive plots for gene_expression_v3.

believe per (gene,tissue): support (reported up/down-regulated) and reject
(reported stable/no change). Compare scores:
  peak_support = max_t support
  peak_net     = max_t (support - reject)
Plots: support heatmap (genes x tissues), strip plot HK vs TS, ROC curve.
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
from sklearn.metrics import roc_auc_score, roc_curve

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent.parent
FIG = HERE / "figures"
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
    by_job = fetch(list({v["job_id"] for v in STATE.values()}))
    genes = sorted({v["gene"] for v in STATE.values()})
    tissues = sorted({v["tissue_gt"] for v in STATE.values()})
    sup = pd.DataFrame(0.0, index=genes, columns=tissues)
    rej = pd.DataFrame(0.0, index=genes, columns=tissues)
    label = {}
    for v in STATE.values():
        vs = by_job.get(v["job_id"]);
        if vs:
            top = vs[:K]
            sup.loc[v["gene"], v["tissue_gt"]] = top.count("support")
            rej.loc[v["gene"], v["tissue_gt"]] = top.count("reject")
        label[v["gene"]] = v["label"]

    net = sup - rej
    peak_support = sup.max(axis=1)
    peak_net = net.max(axis=1)
    y = pd.Series({g: 1 if label[g] == "tissue_specific" else 0 for g in genes})

    print(f"reject totals: sum={int(rej.values.sum())}, support sum={int(sup.values.sum())} "
          f"(reject is {rej.values.sum()/max(1,sup.values.sum())*100:.1f}% of support)")
    print(f"AUC peak_support = {roc_auc_score(y[genes], peak_support[genes]):.3f}")
    print(f"AUC peak_net     = {roc_auc_score(y[genes], peak_net[genes]):.3f}")

    # ---- Plot 1: heatmap (subset: 20 highest-tau TS + 20 lowest-tau HK) ----
    order = RANK.loc[[g for g in genes if g in RANK.index], "tau"].sort_values()
    hk20 = list(order.index[:20]); ts20 = list(order.index[-20:])
    rows = ts20[::-1] + hk20[::-1]               # tissue-specific on top
    sub = sup.loc[rows]
    fig, ax = plt.subplots(figsize=(11, 13))
    im = ax.imshow(np.sqrt(sub.values), aspect="auto", cmap="magma")
    ax.set_xticks(range(len(tissues))); ax.set_xticklabels(tissues, rotation=90, fontsize=8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{g}" for g in rows], fontsize=7)
    ax.axhline(len(ts20) - 0.5, color="cyan", lw=2)
    ax.text(len(tissues)+0.3, len(ts20)/2, "tissue-specific", rotation=90, va="center", color="#444")
    ax.text(len(tissues)+0.3, len(ts20)+len(hk20)/2, "housekeeping", rotation=90, va="center", color="#444")
    fig.colorbar(im, ax=ax, label="sqrt(believe support count)")
    ax.set_title("believe support per gene×tissue\n(tissue-specific genes light up in ONE tissue; housekeeping stay dark)")
    fig.tight_layout(); fig.savefig(FIG / "heatmap.png", dpi=140); plt.close(fig)

    # ---- Plot 2: strip plot peak_support HK vs TS ----
    fig, ax = plt.subplots(figsize=(6, 6))
    rng = np.random.default_rng(0)
    for i, (grp, c) in enumerate([("housekeeping", "#457b9d"), ("tissue_specific", "#e76f51")]):
        gg = [g for g in genes if label[g] == grp]
        xs = i + (rng.random(len(gg)) - 0.5) * 0.3
        ax.scatter(xs, peak_support[gg], c=c, s=30, alpha=0.7)
        ax.hlines(peak_support[gg].median(), i-0.25, i+0.25, color="black", lw=2)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["housekeeping\n(60)", "tissue-specific\n(60)"])
    ax.set_ylabel("believe peak support"); ax.set_title("believe peak support: HK vs tissue-specific\n(black bar = median)")
    fig.tight_layout(); fig.savefig(FIG / "strip.png", dpi=150); plt.close(fig)

    # ---- Plot 3: ROC ----
    fpr, tpr, _ = roc_curve(y[genes], peak_support[genes])
    auc = roc_auc_score(y[genes], peak_support[genes])
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.plot(fpr, tpr, color="#e76f51", lw=2.5, label=f"believe peak support (AUC={auc:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="gray", label="random (0.5)")
    ax.set_xlabel("false positive rate"); ax.set_ylabel("true positive rate")
    ax.set_title("ROC: distinguishing tissue-specific from housekeeping"); ax.legend(fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "roc.png", dpi=150); plt.close(fig)
    print(f"saved heatmap.png, strip.png, roc.png")


if __name__ == "__main__":
    main()
