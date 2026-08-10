"""Generate figures for the biomarker eval + context-contribution analysis.

Outputs PNGs to figures/:
  1 ablation_effect.png   - support/reject by ablation arm (therapeutic vs resistance)
  2 by_level.png          - correct% vs K per OncoKB level
  3 by_cancer.png         - correct% per cancer type (top by count)
  4 by_gene.png           - correct% per gene (top by count)
  5 resistance_flip.png   - resistance reject% A0 vs A1 by gene (alteration ablation)
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

ASSOC = json.loads((HERE / "data" / "associations.json").read_text())
MAIN = json.loads((HERE / "runs" / "jobs.json").read_text())            # A0 (unified)
ABL = json.loads((HERE / "runs" / "ablation_jobs.json").read_text())     # arms
SCORES = json.loads((HERE / "runs" / "scores.json").read_text())          # by level
ABL_SCORES = json.loads((HERE / "runs" / "ablation_scores.json").read_text())

META = {str(o["row_id"]): o for o in ASSOC}


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


def majority(vs, k):
    t = vs[:k]
    s, r = t.count("support"), t.count("reject")
    return "support" if s > r else ("reject" if r > s else "none")


# ---------- Fig 1: ablation effect ----------
def fig_ablation():
    arms = ["A0", "A1", "A2", "A3"]
    labels = {"A0": "A0\nfull", "A1": "A1\n-alteration", "A2": "A2\n-cancer", "A3": "A3\ngene-only"}
    k = "1000"
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, cat, exp in [(axes[0], "therapeutic", "support"), (axes[1], "resistance", "reject")]:
        sup = [ABL_SCORES[k][a][cat]["support_pct"] * 100 for a in arms]
        rej = [ABL_SCORES[k][a][cat]["reject_pct"] * 100 for a in arms]
        x = range(len(arms))
        ax.bar([i - 0.2 for i in x], sup, 0.4, label="SUPPORT", color="#2a9d8f")
        ax.bar([i + 0.2 for i in x], rej, 0.4, label="REJECT", color="#e76f51")
        ax.set_xticks(list(x))
        ax.set_xticklabels([labels[a] for a in arms])
        ax.set_title(f"{cat}  (n={ABL_SCORES[k][arms[0]][cat]['n']}, expected {exp.upper()})")
        ax.set_ylabel("% of rows (majority @ top-1000)")
        ax.axhline(50, color="gray", lw=0.6, ls=":")
        for i, (s, r) in enumerate(zip(sup, rej)):
            ax.text(i - 0.2, s + 1, f"{s:.0f}", ha="center", fontsize=8)
            ax.text(i + 0.2, r + 1, f"{r:.0f}", ha="center", fontsize=8)
        ax.legend(fontsize=8)
    fig.suptitle("Ablation effect: removing the specific alteration flips resistance (REJECT→SUPPORT)", fontsize=11)
    fig.tight_layout()
    fig.savefig(FIG / "1_ablation_effect.png", dpi=150)
    plt.close(fig)


# ---------- Fig 2: by level ----------
def fig_level():
    levels = ["1", "2", "3A", "4", "R1", "R2"]
    Ks = [int(k) for k in SCORES["by_k"].keys()]
    Ks.sort()
    fig, ax = plt.subplots(figsize=(8, 5))
    cmap = {"1": "#1b4332", "2": "#2d6a4f", "3A": "#40916c", "4": "#95d5b2",
            "R1": "#9d4edd", "R2": "#c77dff"}
    for lvl in levels:
        ys = [SCORES["by_k"][str(k)][lvl]["correct_pct"] * 100 for k in Ks]
        n = SCORES["by_level"][lvl]["n"]
        ax.plot(range(len(Ks)), ys, "-o", label=f"L{lvl} (n={n})", color=cmap[lvl], lw=2, ms=4)
    ax.set_xticks(range(len(Ks)))
    ax.set_xticklabels(Ks)
    ax.set_xlabel("top-K articles used")
    ax.set_ylabel("correct% (expected verdict by majority)")
    ax.set_title("Confirmation by OncoKB evidence level\n(therapeutic 1-4 expect SUPPORT, resistance R1/R2 expect REJECT)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(FIG / "2_by_level.png", dpi=150)
    plt.close(fig)


# ---------- per-row correct (A0) for cancer/gene breakdowns ----------
def group_correct(by_job, field, k=100, min_n=8):
    groups = defaultdict(lambda: [0, 0])  # field_val -> [correct, n]
    for rid, info in MAIN.items():
        v = by_job.get(info["job_id"])
        if not v:
            continue
        m = majority(v, k)
        exp = info["expected"]
        val = META[rid][field]
        groups[val][1] += 1
        if m == exp:
            groups[val][0] += 1
    rows = [(val, c / n * 100, n) for val, (c, n) in groups.items() if n >= min_n]
    rows.sort(key=lambda x: x[1])
    return rows


def fig_bar(rows, title, fname, topn=18):
    rows = rows[-topn:] if len(rows) > topn else rows
    fig, ax = plt.subplots(figsize=(8, max(4, 0.34 * len(rows))))
    labels = [f"{v}  (n={n})" for v, _p, n in rows]
    vals = [p for _v, p, _n in rows]
    colors = ["#2a9d8f" if p >= 50 else "#e76f51" for p in vals]
    ax.barh(range(len(rows)), vals, color=colors)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("correct% (expected verdict by majority @ top-100)")
    ax.set_xlim(0, 100)
    ax.axvline(50, color="gray", lw=0.6, ls=":")
    for i, p in enumerate(vals):
        ax.text(p + 1, i, f"{p:.0f}", va="center", fontsize=7)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(FIG / fname, dpi=150)
    plt.close(fig)


# ---------- Fig 5: resistance flip by gene (A0 vs A1) ----------
def fig_flip(by_job_all):
    # A1 row->job
    a1_row_job = {}
    for h in ABL["A1"].values():
        for rid in h["row_ids"]:
            a1_row_job[str(rid)] = h["job_id"]
    k = 1000
    by_gene = defaultdict(lambda: {"a0": [0, 0], "a1": [0, 0]})  # gene -> reject counts
    for rid, info in MAIN.items():
        if info["category"] != "resistance":
            continue
        gene = META[rid]["gene"]
        v0 = by_job_all.get(info["job_id"])
        v1 = by_job_all.get(a1_row_job.get(rid))
        if v0:
            by_gene[gene]["a0"][1] += 1
            if majority(v0, k) == "reject":
                by_gene[gene]["a0"][0] += 1
        if v1:
            by_gene[gene]["a1"][1] += 1
            if majority(v1, k) == "reject":
                by_gene[gene]["a1"][0] += 1
    genes = [(g, d) for g, d in by_gene.items() if d["a0"][1] >= 4]
    genes.sort(key=lambda x: -x[1]["a0"][1])
    genes = genes[:10]
    names = [g for g, _ in genes]
    a0 = [d["a0"][0] / d["a0"][1] * 100 for _, d in genes]
    a1 = [d["a1"][0] / d["a1"][1] * 100 if d["a1"][1] else 0 for _, d in genes]
    x = range(len(names))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.bar([i - 0.2 for i in x], a0, 0.4, label="A0 full (keeps mutation)", color="#264653")
    ax.bar([i + 0.2 for i in x], a1, 0.4, label="A1 -alteration (generalized)", color="#e9c46a")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{g}\n(n={d['a0'][1]})" for g, d in genes], fontsize=8)
    ax.set_ylabel("REJECT% (correct for resistance) @ top-1000")
    ax.set_title("Resistance detection collapses when the specific alteration is removed\n(REJECT = believe correctly says 'drug does NOT work')")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 105)
    fig.tight_layout()
    fig.savefig(FIG / "5_resistance_flip_by_gene.png", dpi=150)
    plt.close(fig)


def main():
    fig_ablation()
    fig_level()
    print("fig 1,2 done")

    a0_jobs = [info["job_id"] for info in MAIN.values()]
    a1_jobs = [h["job_id"] for h in ABL["A1"].values()]
    by_job = fetch(a0_jobs + a1_jobs)

    fig_bar(group_correct(by_job, "cancer_type"), "believe accuracy by cancer type (A0 full)",
            "3_by_cancer.png")
    fig_bar(group_correct(by_job, "gene"), "believe accuracy by gene (A0 full)",
            "4_by_gene.png")
    fig_flip(by_job)
    print("fig 3,4,5 done")
    print(f"saved -> {FIG}")


if __name__ == "__main__":
    main()
