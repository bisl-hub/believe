"""Distribution statistics for biomarker_v2 across 3 axes:
   drug  +  biomarker (gene+mutation)  +  cancer type.

Reads data/triples.json, saves figures/distributions.png.
"""

import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

T = json.loads((HERE / "data" / "triples.json").read_text())

biomarker = Counter(o["biomarker"] for o in T)
drug = Counter(o["drug"] for o in T)
cancer = Counter(o["cancer_type"] for o in T)

print(f"triples: {len(T)}")
print(f"unique biomarkers: {len(biomarker)} | drugs: {len(drug)} | cancers: {len(cancer)}")
print(f"biomarker appears once: {sum(1 for v in biomarker.values() if v == 1)} | "
      f"max: {biomarker.most_common(1)[0]}")


def hbar(ax, counter, title, n=20, color="#2a9d8f"):
    items = counter.most_common(n)[::-1]
    labels = [(k[:34] + "…") if len(k) > 35 else k for k, _ in items]
    vals = [v for _, v in items]
    ax.barh(range(len(items)), vals, color=color)
    ax.set_yticks(range(len(items))); ax.set_yticklabels(labels, fontsize=8)
    ax.set_title(title, fontsize=11, fontweight="bold")
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.01, i, str(v), va="center", fontsize=7)
    ax.margins(x=0.12)


fig, axes = plt.subplots(2, 2, figsize=(16, 12))
hbar(axes[0, 0], biomarker, f"Top biomarkers (gene+mutation)  [{len(biomarker)} unique]", color="#2a9d8f")
hbar(axes[0, 1], drug, f"Top drugs  [{len(drug)} unique]", color="#457b9d")
hbar(axes[1, 0], cancer, f"Top cancer types  [{len(cancer)} unique]", color="#e76f51")

ax = axes[1, 1]
fof = Counter(biomarker.values())
xs = sorted(fof); ys = [fof[x] for x in xs]
ax.bar([str(x) for x in xs], ys, color="#888")
ax.set_title("Biomarker frequency distribution (long tail)", fontsize=11, fontweight="bold")
ax.set_xlabel("# of triples a biomarker appears in"); ax.set_ylabel("# of biomarkers")
for i, y in enumerate(ys):
    ax.text(i, y + max(ys) * 0.01, str(y), ha="center", fontsize=7)

fig.suptitle(f"biomarker_v2 distribution — drug / biomarker(gene+mutation) / cancer "
             f"(n={len(T)} triples)", fontsize=14)
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(FIG / "distributions.png", dpi=140)
plt.close(fig)
print(f"saved -> {FIG}/distributions.png")
