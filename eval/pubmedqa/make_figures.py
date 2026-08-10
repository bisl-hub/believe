"""Figures for the PubMedQA eval.

  1 accuracy_vs_k.png  - overall / yes / no / tie-excluded accuracy vs K
  2 confusion_vs_k.png - how yes(552) and no(338) questions get classified vs K
  3 retriever_recall.png - source paper found within top-K (recall@K)
  4 gold_verdict.png   - LLM verdict on the source paper + accuracy
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

SCORES = json.loads((HERE / "runs" / "scores.json").read_text())
RECALL = json.loads((HERE / "runs" / "reference_recall.json").read_text())
GOLD = json.loads((HERE / "runs" / "gold_verdict.json").read_text())

KS = [int(k) for k in SCORES["by_k"].keys()]
KS.sort()
N_YES, N_NO = 552, 338


def fig_accuracy():
    overall, yes_acc, no_acc, tie_excl = [], [], [], []
    for k in KS:
        v = SCORES["by_k"][str(k)]
        overall.append(v["accuracy"] * 100)
        yes_acc.append(v["confusion"]["yes"]["yes"] / N_YES * 100)
        no_acc.append(v["confusion"]["no"]["no"] / N_NO * 100)
        dec = v["correct"] + (v["wrong"] - v["ties"])
        tie_excl.append(v["correct"] / dec * 100 if dec else 0)
    x = range(len(KS))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x, overall, "-o", label="overall accuracy", color="#264653", lw=2.5)
    ax.plot(x, tie_excl, "--o", label="tie-excluded accuracy", color="#888", lw=1.5)
    ax.plot(x, yes_acc, "-s", label="yes questions (recall)", color="#2a9d8f", lw=2)
    ax.plot(x, no_acc, "-^", label="no questions (recall)", color="#e76f51", lw=2)
    ax.set_xticks(list(x)); ax.set_xticklabels(KS)
    ax.set_xlabel("top-K articles used (support vs reject majority)")
    ax.set_ylabel("accuracy %")
    ax.set_title("PubMedQA: accuracy vs retrieval depth\n(peaks at K=1, 'no' questions collapse as K grows)")
    ax.grid(alpha=0.3); ax.legend(fontsize=9); ax.set_ylim(0, 100)
    for xi, y in zip(x, overall):
        ax.text(xi, y + 2, f"{y:.0f}", ha="center", fontsize=8)
    fig.tight_layout(); fig.savefig(FIG / "1_accuracy_vs_k.png", dpi=150); plt.close(fig)


def fig_confusion():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    specs = [("yes", N_YES, ["yes", "no", "tie"], ["#2a9d8f", "#e76f51", "#bbb"], axes[0]),
             ("no", N_NO, ["no", "yes", "tie"], ["#2a9d8f", "#e76f51", "#bbb"], axes[1])]
    for gold, n, order, colors, ax in specs:
        bottoms = [0] * len(KS)
        for cls, col in zip(order, colors):
            vals = [SCORES["by_k"][str(k)]["confusion"][gold].get(cls, 0) / n * 100 for k in KS]
            lbl = {"yes": "→ predict yes", "no": "→ predict no", "tie": "→ tie"}[cls]
            if cls == gold:
                lbl += " (correct)"
            ax.bar(range(len(KS)), vals, bottom=bottoms, color=col, label=lbl)
            bottoms = [b + v for b, v in zip(bottoms, vals)]
        ax.set_xticks(range(len(KS))); ax.set_xticklabels(KS)
        ax.set_title(f"'{gold}' questions (n={n})")
        ax.set_xlabel("top-K"); ax.set_ylabel("% of questions")
        ax.legend(fontsize=8)
    fig.suptitle("How each gold class gets classified as K grows", fontsize=12)
    fig.tight_layout(); fig.savefig(FIG / "2_confusion_vs_k.png", dpi=150); plt.close(fig)


def fig_recall():
    ks = [int(k) for k in RECALL["recall_at_k"].keys()]
    ks.sort()
    vals = [RECALL["recall_at_k"][str(k)]["recall"] * 100 for k in ks]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.plot(range(len(ks)), vals, "-o", color="#457b9d", lw=2.5, ms=7)
    ax.set_xticks(range(len(ks))); ax.set_xticklabels(ks)
    ax.set_xlabel("top-K"); ax.set_ylabel("recall@K %")
    ax.set_ylim(0, 100); ax.grid(alpha=0.3)
    ax.set_title(f"Retriever recall: source paper found within top-K\n"
                 f"(median rank 1, {RECALL['found_within_1000']}/{RECALL['total']} found in top-1000)")
    for xi, y in zip(range(len(ks)), vals):
        ax.text(xi, y - 6, f"{y:.0f}%", ha="center", fontsize=9)
    fig.tight_layout(); fig.savefig(FIG / "3_retriever_recall.png", dpi=150); plt.close(fig)


def fig_gold():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4),
                             gridspec_kw={"width_ratios": [1.3, 1]})
    # left: SRN distribution by gold label
    ax = axes[0]
    cats = ["support", "reject", "neutral", "(not retrieved)"]
    colors = ["#2a9d8f", "#e76f51", "#e9c46a", "#ccc"]
    for i, gold in enumerate(["yes", "no"]):
        bottom = 0
        n = N_YES if gold == "yes" else N_NO
        for cls, col in zip(cats, colors):
            v = GOLD["distribution"][gold].get(cls, 0) / n * 100
            ax.bar(i, v, bottom=bottom, color=col,
                   label=cls if i == 0 else None)
            if v > 4:
                ax.text(i, bottom + v / 2, f"{v:.0f}", ha="center", va="center", fontsize=8)
            bottom += v
    ax.set_xticks([0, 1]); ax.set_xticklabels([f"yes (n={N_YES})", f"no (n={N_NO})"])
    ax.set_ylabel("% of questions"); ax.set_ylim(0, 100)
    ax.set_title("LLM verdict on the source paper")
    ax.legend(fontsize=8, loc="lower center", ncol=2)
    # right: accuracy
    ax = axes[1]
    accs = [GOLD["acc_neutral_wrong"] * 100, GOLD["acc_neutral_excluded"] * 100]
    bars = ax.bar(["neutral=wrong", "neutral excluded"], accs, color=["#264653", "#2a9d8f"])
    ax.set_ylim(0, 100); ax.set_ylabel("accuracy %")
    ax.set_title(f"Accuracy using only the source paper\n(n={GOLD['retrieved']} retrieved)")
    for b, a in zip(bars, accs):
        ax.text(b.get_x() + b.get_width() / 2, a + 1.5, f"{a:.1f}", ha="center", fontsize=10)
    fig.suptitle("believe judges the actual source paper very accurately (92-93%)", fontsize=12)
    fig.tight_layout(); fig.savefig(FIG / "4_gold_verdict.png", dpi=150); plt.close(fig)


def main():
    fig_accuracy(); fig_confusion(); fig_recall(); fig_gold()
    print(f"saved 4 figures -> {FIG}")


if __name__ == "__main__":
    main()
