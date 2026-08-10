"""3-axis analysis of the OncoKB triples: accuracy by drug / biomarker / cancer.

correct = top-K majority verdict equals expected (therapeutic->support,
resistance->reject). Reports overall accuracy across K and per-value correct%
for each axis; saves ranked figures.
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
STATE = json.loads((HERE / "runs" / "jobs.json").read_text())

K_FIG = 100
K_TABLE = [1, 10, 100, 1000]
MIN_N = 5


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


def maj(vs, k):
    t = vs[:k]
    s, r = t.count("support"), t.count("reject")
    return "support" if s > r else ("reject" if r > s else "none")


def main():
    by_job = fetch([v["job_id"] for v in STATE.values()])
    rows = [(v, by_job.get(v["job_id"])) for v in STATE.values()]
    rows = [(v, vs) for v, vs in rows if vs]

    # overall accuracy by K
    print(f"{len(rows)} triples with results\n")
    print(f"{'K':>5} {'overall':>8} {'therapeutic':>12} {'resistance':>11}")
    for k in K_TABLE:
        tot = defaultdict(lambda: [0, 0])
        for v, vs in rows:
            cat = v["category"]
            ok = (maj(vs, k) == v["expected"])
            tot["all"][0] += ok; tot["all"][1] += 1
            tot[cat][0] += ok; tot[cat][1] += 1
        def acc(g): return tot[g][0] / tot[g][1] * 100 if tot[g][1] else 0
        print(f"{k:>5} {acc('all'):>7.1f}% {acc('therapeutic'):>11.1f}% {acc('resistance'):>10.1f}%")

    # per-axis correct% at K_FIG
    def by_axis(field):
        g = defaultdict(lambda: [0, 0])
        for v, vs in rows:
            ok = (maj(vs, K_FIG) == v["expected"])
            g[v[field]][0] += ok; g[v[field]][1] += 1
        out = [(val, c / n * 100, n) for val, (c, n) in g.items() if n >= MIN_N]
        out.sort(key=lambda x: x[1])
        return out

    def barh(data, title, fname, color, topn=25):
        data = data[-topn:] if len(data) > topn else data
        fig, ax = plt.subplots(figsize=(9, max(4, 0.34 * len(data))))
        labels = [f"{(v[:40]+'…') if len(v)>41 else v}  (n={n})" for v, _p, n in data]
        vals = [p for _v, p, _n in data]
        colors = [color if p >= 50 else "#c44" for p in vals]
        ax.barh(range(len(data)), vals, color=colors)
        ax.set_yticks(range(len(data))); ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlim(0, 100); ax.axvline(50, color="gray", lw=0.6, ls=":")
        ax.set_xlabel(f"correct% (expected verdict by majority @ top-{K_FIG})")
        for i, p in enumerate(vals):
            ax.text(p + 1, i, f"{p:.0f}", va="center", fontsize=7)
        ax.set_title(title, fontsize=12, fontweight="bold")
        fig.tight_layout(); fig.savefig(FIG / fname, dpi=140); plt.close(fig)

    for field, title, fname, color in [
        ("drug", "Accuracy by drug", "axis_drug.png", "#457b9d"),
        ("biomarker", "Accuracy by biomarker (gene+mutation)", "axis_biomarker.png", "#2a9d8f"),
        ("cancer_type", "Accuracy by cancer type", "axis_cancer.png", "#e76f51"),
    ]:
        data = by_axis(field)
        barh(data, f"{title}  (n>={MIN_N}, top {min(25,len(data))})", fname, color)
        print(f"\n=== {title} (best & worst, n>={MIN_N}) ===")
        for v, p, n in sorted(data, key=lambda x: -x[1])[:5]:
            print(f"  {p:5.0f}%  {v}  (n={n})")
        for v, p, n in sorted(data, key=lambda x: x[1])[:5]:
            print(f"  {p:5.0f}%  {v}  (n={n})  [low]")

    print(f"\nsaved axis figures -> {FIG}")


if __name__ == "__main__":
    main()
