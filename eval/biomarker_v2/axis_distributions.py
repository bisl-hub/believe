"""Full ranked distribution for each of the 3 axes (descending), one figure each.

  figures/dist_cancer.png      - all cancer types,  count desc
  figures/dist_drug.png        - all drugs,         count desc
  figures/dist_biomarker.png   - all biomarkers,    count desc

Each value's count is shown (e.g. cancer A -> n). Tall horizontal bars.
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


def full_hbar(counter, title, fname, color):
    items = counter.most_common()           # descending
    items = items[::-1]                      # ascending for barh (top = largest)
    n = len(items)
    labels = [(k[:46] + "…") if len(k) > 47 else k for k, _ in items]
    vals = [v for _, v in items]
    height = max(5, 0.17 * n)
    fig, ax = plt.subplots(figsize=(11, height))
    ax.barh(range(n), vals, color=color)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_ylim(-0.5, n - 0.5)
    ax.set_xlabel("count (# of triples)")
    ax.set_title(f"{title}  —  {n} unique (descending)", fontsize=12, fontweight="bold")
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.005, i, str(v), va="center", fontsize=6)
    ax.margins(x=0.08)
    fig.tight_layout()
    fig.savefig(FIG / fname, dpi=110)
    plt.close(fig)
    print(f"saved {fname}  ({n} values, top={items[-1]})")


full_hbar(Counter(o["cancer_type"] for o in T), "Cancer type distribution",
          "dist_cancer.png", "#e76f51")
full_hbar(Counter(o["drug"] for o in T), "Drug distribution",
          "dist_drug.png", "#457b9d")
full_hbar(Counter(o["biomarker"] for o in T), "Biomarker (gene+mutation) distribution",
          "dist_biomarker.png", "#2a9d8f")
