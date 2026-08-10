"""Ground-truth tissue expression from CELLxGENE (full cells, parallel).

For each tissue in the panel, stream the X matrix (restricted to our gene set)
in chunks and accumulate the mean CP10k expression per gene over ALL cells of
that tissue (no subsampling). Tissues run in parallel processes; TileDB
multithreads the reads within each.

Outputs:
  data/gt_expr.csv  : rows=gene, cols=tissue, mean CP10k
  data/gt_tau.csv   : per gene tau tissue-specificity (0=housekeeping,1=specific)

Run with the cxgene conda env (python 3.11, cellxgene-census).
"""

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
GENES = [g["gene"] for g in json.loads((HERE / "data" / "genes.json").read_text())]
CENSUS_VERSION = "2025-11-08"

# tissue panel (tissue_general labels). believe-side display names cleaned later.
TISSUES = [
    "brain", "blood", "lung", "liver", "heart", "kidney", "pancreas", "colon",
    "small intestine", "stomach", "spleen", "skin of body", "adipose tissue",
    "musculature", "breast", "bone marrow", "lymph node", "esophagus",
    "uterus", "placenta",
]


def one_tissue(t):
    import cellxgene_census, tiledbsoma
    gene_filter = "feature_name in [" + ", ".join(f"'{g}'" for g in GENES) + "]"
    with cellxgene_census.open_soma(census_version=CENSUS_VERSION) as census:
        human = census["census_data"]["homo_sapiens"]
        q = human.axis_query(
            measurement_name="RNA",
            obs_query=tiledbsoma.AxisQuery(
                value_filter=f"tissue_general == '{t}' and is_primary_data == True"),
            var_query=tiledbsoma.AxisQuery(value_filter=gene_filter),
        )
        var = q.var(column_names=["soma_joinid", "feature_name"]).concat().to_pandas()
        vid2name = dict(zip(var.soma_joinid.to_numpy(), var.feature_name))
        obs = q.obs(column_names=["soma_joinid", "raw_sum"]).concat().to_pandas()
        n_cells = len(obs)
        if n_cells == 0:
            return t, 0, {}
        rs = pd.Series(obs.raw_sum.to_numpy().astype("float64"),
                       index=obs.soma_joinid.to_numpy())
        rs[rs == 0] = 1.0
        sums = {g: 0.0 for g in GENES}
        for tbl in q.X("raw").tables():
            d0 = tbl.column("soma_dim_0").to_numpy()
            d1 = tbl.column("soma_dim_1").to_numpy()
            val = tbl.column("soma_data").to_numpy().astype("float64")
            norm = val / rs.loc[d0].to_numpy() * 1e4
            for vid in np.unique(d1):
                m = d1 == vid
                sums[vid2name[vid]] += float(norm[m].sum())
        means = {g: sums[g] / n_cells for g in GENES}
        return t, n_cells, means


def tau(profile):
    x = np.asarray(profile, dtype=float)
    x = np.clip(x, 0, None)
    if x.max() <= 0:
        return np.nan
    xhat = x / x.max()
    return float((1 - xhat).sum() / (len(x) - 1))


def main():
    results = {}
    counts = {}
    with ProcessPoolExecutor(max_workers=6) as ex:
        for t, n, means in ex.map(one_tissue, TISSUES):
            print(f"  {t:>16}: {n:>12,} cells", flush=True)
            if n:
                results[t] = means
                counts[t] = n

    expr = pd.DataFrame(results).reindex(GENES)  # rows=gene, cols=tissue
    expr.to_csv(HERE / "data" / "gt_expr.csv")
    taus = expr.apply(lambda row: tau(row.values), axis=1)
    taus.sort_values(ascending=False).to_csv(HERE / "data" / "gt_tau.csv", header=["tau"])
    print("\ntop tissue-specific (high tau):")
    print(taus.sort_values(ascending=False).head(8).to_string())
    print("\nmost housekeeping (low tau):")
    print(taus.sort_values().head(8).to_string())
    print(f"\nsaved gt_expr.csv ({expr.shape}) and gt_tau.csv")


if __name__ == "__main__":
    main()
