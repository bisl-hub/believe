"""Data-driven gene selection: rank ALL genes by cross-tissue expression
variability (tau) and pick the extremes — bottom-30 = housekeeping (stable),
top-30 = context-variable (sensitive).

Per tissue we subsample cells (selection only; pseudobulk mean over thousands of
cells is stable), compute pseudobulk mean expression for ALL genes, then tau
across tissues. Filtered to reasonably expressed genes so they have literature.

Output: data/gene_ranking.csv, data/selected_genes.json
"""

import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
CENSUS_VERSION = "2025-11-08"
TISSUES = ["brain", "blood", "lung", "liver", "heart", "kidney", "pancreas",
           "colon", "small intestine", "stomach", "spleen", "skin of body",
           "adipose tissue", "musculature", "breast", "bone marrow",
           "lymph node", "esophagus", "uterus", "placenta"]
N_PER_TISSUE = 4000
CANDIDATE_CAP = 200_000   # only read up to this many cell IDs per tissue (speed)
MIN_PEAK_CP10K = 5.0
TOPN = 30


def tau(x):
    x = np.clip(np.asarray(x, float), 0, None)
    if x.max() <= 0:
        return np.nan
    return float((1 - x / x.max()).sum() / (len(x) - 1))


def one_tissue(t):
    import cellxgene_census
    from scipy.sparse import diags
    random.seed(hash(t) % 10000)
    with cellxgene_census.open_soma(census_version=CENSUS_VERSION) as census:
        human = census["census_data"]["homo_sapiens"]
        # read cell IDs in batches, stop once we have enough candidates (fast for huge tissues)
        cand = []
        total = 0
        for tbl in human.obs.read(
                value_filter=f"tissue_general == '{t}' and is_primary_data == True",
                column_names=["soma_joinid"]):
            arr = tbl.column("soma_joinid").to_numpy()
            cand.append(arr); total += len(arr)
            if total >= CANDIDATE_CAP:
                break
        ids = np.concatenate(cand)
        samp = np.array(random.sample(list(ids), min(N_PER_TISSUE, len(ids))))
        ad = cellxgene_census.get_anndata(
            census, organism="Homo sapiens", measurement_name="RNA",
            obs_coords=samp.tolist(), obs_column_names=["soma_joinid", "raw_sum"])
        rs = ad.obs["raw_sum"].to_numpy().astype("float64"); rs[rs == 0] = 1
        norm = diags(1e4 / rs) @ ad.X.tocsr()
        mean = np.asarray(norm.mean(axis=0)).ravel()
        return t, ad.n_obs, pd.Series(mean, index=ad.var["feature_name"].to_numpy())


def main():
    profiles = {}
    with ProcessPoolExecutor(max_workers=len(TISSUES)) as ex:
        for t, n, ser in ex.map(one_tissue, TISSUES):
            profiles[t] = ser
            print(f"  {t:>16}: {n:,} cells sampled, {len(ser)} genes", flush=True)

    M = pd.DataFrame(profiles)            # genes x tissues
    M = M.groupby(level=0).mean()         # collapse duplicate feature names
    peak = M.max(axis=1)
    M = M[peak >= MIN_PEAK_CP10K]         # keep reasonably expressed genes
    taus = M.apply(lambda r: tau(r.values), axis=1).dropna().sort_values()

    rank = pd.DataFrame({"tau": taus, "peak_cp10k": peak[taus.index],
                         "top_tissue": M.loc[taus.index].idxmax(axis=1)})
    rank.to_csv(HERE / "data" / "gene_ranking.csv")

    housekeeping = list(taus.index[:TOPN])
    sensitive = list(taus.index[-TOPN:][::-1])
    json.dump({"housekeeping": housekeeping, "sensitive": sensitive},
              open(HERE / "data" / "selected_genes.json", "w"), ensure_ascii=False, indent=2)

    print(f"\nranked {len(taus)} expressed genes (peak>={MIN_PEAK_CP10K} CP10k)")
    print(f"\n=== housekeeping (lowest tau) ===")
    for g in housekeeping:
        print(f"  tau={taus[g]:.3f} peak={peak[g]:8.1f}  {g}")
    print(f"\n=== sensitive (highest tau) ===")
    for g in sensitive:
        print(f"  tau={taus[g]:.3f} peak={peak[g]:8.1f}  {g}  [{rank.loc[g,'top_tissue']}]")


if __name__ == "__main__":
    main()
