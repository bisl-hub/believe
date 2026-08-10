"""Per-value feature importance: which specific ALTERATION and which CANCER type
most change believe's verdict when removed.

  alteration importance : per alteration value, effect of generalizing it away
                          (A0 full  vs  A1 -alteration), over rows with that value
  cancer importance     : per cancer type, effect of removing it
                          (A0 full  vs  A2 -cancer), over rows in that cancer

For each row at top-K=1000:
  net = (#support - #reject) / topK      in [-1, +1]
  Δnet(field) = net(ablated) - net(A0)   (signed; + means shifted toward SUPPORT)
Importance of a value = mean |Δnet| over its rows; we also keep signed mean and
the verdict flip rate. Ranks + two figures + tables.
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
MAIN = json.loads((HERE / "runs" / "jobs.json").read_text())
ABL = json.loads((HERE / "runs" / "ablation_jobs.json").read_text())
META = {str(o["row_id"]): o for o in ASSOC}
K = 1000
MIN_N = 4   # require at least this many rows for a stable per-value estimate


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


def net_maj(vs):
    top = vs[:K]
    n = len(top)
    s, r = top.count("support"), top.count("reject")
    maj = "support" if s > r else ("reject" if r > s else "none")
    return ((s - r) / n if n else 0.0), maj


def arm_row_job(arm):
    m = {}
    for h in ABL[arm].values():
        for rid in h["row_ids"]:
            m[str(rid)] = h["job_id"]
    return m


def rank(by_value):
    rows = []
    for val, d in by_value.items():
        if d["n"] < MIN_N:
            continue
        rows.append((val, d["n"], d["abs"] / d["n"], d["signed"] / d["n"], d["flip"] / d["n"]))
    rows.sort(key=lambda x: x[2])  # by |Δnet| ascending (for barh)
    return rows


def barh(rows, title, fname, topn=20):
    rows = rows[-topn:]
    labels = [f"{v}  (n={n})" for v, n, _a, _s, _f in rows]
    absd = [a for _v, _n, a, _s, _f in rows]
    signed = [s for _v, _n, _a, s, _f in rows]
    colors = ["#e76f51" if s > 0 else "#2a9d8f" for s in signed]  # +→support shift
    fig, ax = plt.subplots(figsize=(9, max(4, 0.36 * len(rows))))
    ax.barh(range(len(rows)), absd, color=colors)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("importance = mean |Δ net-support| when removed (top-1000)")
    for i, (a, s) in enumerate(zip(absd, signed)):
        ax.text(a + 0.005, i, f"{a:.2f}{' ↑sup' if s > 0 else ' ↓sup'}", va="center", fontsize=7)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(FIG / fname, dpi=150)
    plt.close(fig)


def main():
    a1, a2 = arm_row_job("A1"), arm_row_job("A2")
    ids = [v["job_id"] for v in MAIN.values()]
    ids += [h["job_id"] for arm in ("A1", "A2") for h in ABL[arm].values()]
    by_job = fetch(ids)

    by_alt = defaultdict(lambda: {"n": 0, "abs": 0.0, "signed": 0.0, "flip": 0})
    by_can = defaultdict(lambda: {"n": 0, "abs": 0.0, "signed": 0.0, "flip": 0})

    for rid, info in MAIN.items():
        v0 = by_job.get(info["job_id"])
        v1 = by_job.get(a1.get(rid))
        v2 = by_job.get(a2.get(rid))
        if not v0:
            continue
        net0, m0 = net_maj(v0)
        alt, can = META[rid]["alteration"], META[rid]["cancer_type"]
        if v1:
            net1, m1 = net_maj(v1)
            d = by_alt[alt]
            d["n"] += 1; d["abs"] += abs(net1 - net0); d["signed"] += (net1 - net0); d["flip"] += (m1 != m0)
        if v2:
            net2, m2 = net_maj(v2)
            d = by_can[can]
            d["n"] += 1; d["abs"] += abs(net2 - net0); d["signed"] += (net2 - net0); d["flip"] += (m2 != m0)

    alt_rows = rank(by_alt)
    can_rows = rank(by_can)

    def show(title, rows):
        print(f"\n=== {title} (n>={MIN_N}, top 15 by importance) ===")
        print(f"{'value':<42} {'n':>3} {'|Δnet|':>7} {'signed':>7} {'flip%':>6}")
        for v, n, a, s, f in sorted(rows, key=lambda x: -x[2])[:15]:
            print(f"{v[:42]:<42} {n:>3} {a:>7.3f} {s:>+7.3f} {f*100:>5.0f}%")

    show("ALTERATION importance (generalize away)", alt_rows)
    show("CANCER importance (remove)", can_rows)

    barh(alt_rows, "Per-alteration importance (red=removing shifts toward SUPPORT)",
         "7_alteration_importance.png")
    barh(can_rows, "Per-cancer-type importance (effect of removing cancer)",
         "8_cancer_importance.png")
    print(f"\nsaved -> {FIG}/7_alteration_importance.png, 8_cancer_importance.png")


if __name__ == "__main__":
    main()
