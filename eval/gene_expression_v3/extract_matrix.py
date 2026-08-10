"""Save the data gene×tissue pseudobulk expression matrix for the current genes
(those in runs/jobs.json), so we can compare believe's per-tissue pattern to the
real per-tissue expression. Subsampled per tissue (fast), parallel.
Output: data/data_matrix.csv (rows=gene, cols=tissue, mean CP10k).
"""
import json, random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).parent
CENSUS = "2025-11-08"
GENES = sorted({v["gene"] for v in json.loads((HERE/"runs"/"jobs.json").read_text()).values()})
TISSUES = ["brain","blood","lung","liver","heart","kidney","pancreas","colon",
           "small intestine","stomach","spleen","skin of body","adipose tissue",
           "musculature","breast","bone marrow","lymph node","esophagus","uterus","placenta"]
N=4000; CAP=200_000


def one(t):
    import cellxgene_census; from scipy.sparse import diags
    random.seed(hash(t)%9999)
    gf="feature_name in ["+",".join(f"'{g}'" for g in GENES)+"]"
    with cellxgene_census.open_soma(census_version=CENSUS) as c:
        h=c["census_data"]["homo_sapiens"]
        cand=[]; tot=0
        for tb in h.obs.read(value_filter=f"tissue_general=='{t}' and is_primary_data==True",column_names=["soma_joinid"]):
            a=tb.column("soma_joinid").to_numpy(); cand.append(a); tot+=len(a)
            if tot>=CAP: break
        ids=np.concatenate(cand); samp=np.array(random.sample(list(ids),min(N,len(ids))))
        ad=cellxgene_census.get_anndata(c,organism="Homo sapiens",measurement_name="RNA",
            obs_coords=samp.tolist(),var_value_filter=gf,obs_column_names=["soma_joinid","raw_sum"])
        rs=ad.obs["raw_sum"].to_numpy().astype(float); rs[rs==0]=1
        m=np.asarray((diags(1e4/rs)@ad.X.tocsr()).mean(axis=0)).ravel()
        return t, pd.Series(m,index=ad.var["feature_name"].to_numpy())


def main():
    prof={}
    with ProcessPoolExecutor(max_workers=4) as ex:
        for t,s in ex.map(one,TISSUES):
            prof[t]=s; print(t,"done",flush=True)
    M=pd.DataFrame(prof).groupby(level=0).mean().reindex(GENES)
    M.to_csv(HERE/"data"/"data_matrix.csv"); print("saved",M.shape)


if __name__=="__main__":
    main()
