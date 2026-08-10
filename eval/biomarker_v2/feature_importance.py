"""Feature importance from A0 alone (no new believe runs), reliability-weighted.

Per association: target = net verdict (support-reject)/(support+reject) [%],
weight = evidence (support+reject). Which feature best explains believe's verdict?
  - weighted eta^2 (univariate variance explained)
  - RandomForest permutation importance (multivariate, sample_weight=evidence)
  - drill-down on the top feature
Figures -> figures_feature_importance/
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance

HERE=Path(__file__).parent; REPO=HERE.parent.parent; FIG=HERE/"figures_feature_importance"; FIG.mkdir(exist_ok=True)
STATE=json.loads((HERE/"runs"/"jobs.json").read_text()); K=1000
FEATURES=["biomarker","cancer_type","drug"]


def fetch(ids):
    sql=(f"COPY (SELECT job_id,qwen_rank,verdict FROM job_results WHERE job_id IN ({','.join(map(str,ids))}) "
         f"ORDER BY job_id,qwen_rank NULLS LAST,id) TO STDOUT WITH CSV")
    out=subprocess.run(["docker","compose","exec","-T","hypothesis-db","psql","-U","user","-d","hypothesis_db","-c",sql],
                       cwd=str(REPO),capture_output=True,text=True,check=True).stdout
    by=defaultdict(list)
    for l in out.splitlines():
        if l.strip(): j,_,v=l.split(",",2); by[int(j)].append(v)
    return by


def weighted_eta2(y,w,groups):
    y=np.asarray(y,float); w=np.asarray(w,float)
    ybar=np.sum(w*y)/np.sum(w); sst=np.sum(w*(y-ybar)**2)
    ssb=0.0
    for g in pd.unique(groups):
        m=groups==g; wg=w[m].sum()
        if wg>0: ssb+=wg*(np.sum(w[m]*y[m])/wg - ybar)**2
    return ssb/sst if sst>0 else 0.0


def main():
    by=fetch(list({v["job_id"] for v in STATE.values()}))
    rec=[]
    for v in STATE.values():
        vs=by.get(v["job_id"]);
        if not vs: continue
        t=vs[:K]; s=t.count("support"); r=t.count("reject"); tot=s+r
        if tot==0: continue
        rec.append({**{f:v[f] for f in FEATURES}, "level":v["level"], "net":(s-r)/tot*100, "evidence":tot})
    df=pd.DataFrame(rec)
    print(f"{len(df)} associations with evidence")

    # 1) weighted eta^2
    eta={f:weighted_eta2(df["net"],df["evidence"],df[f].values) for f in FEATURES}
    eta=pd.Series(eta).sort_values()
    # 2) RF permutation importance (ordinal-encode categoricals), weighted
    X=pd.DataFrame({f:df[f].astype("category").cat.codes for f in FEATURES})
    rf=RandomForestRegressor(n_estimators=400,random_state=0,n_jobs=-1,min_samples_leaf=5)
    rf.fit(X,df["net"],sample_weight=df["evidence"])
    pi=permutation_importance(rf,X,df["net"],sample_weight=df["evidence"],n_repeats=20,random_state=0)
    perm=pd.Series(pi.importances_mean,index=FEATURES).sort_values()

    fig,ax=plt.subplots(1,2,figsize=(12,5))
    ax[0].barh(range(len(eta)),eta.values,color="#2a9d8f")
    ax[0].set_yticks(range(len(eta)));ax[0].set_yticklabels(eta.index)
    ax[0].set_xlabel("weighted eta^2 (variance of net verdict explained)")
    ax[0].set_title("(1) Univariate: which feature alone\nexplains believe's verdict (evidence-weighted)")
    for i,val in enumerate(eta.values): ax[0].text(val,i,f" {val:.2f}",va="center",fontsize=9)
    ax[1].barh(range(len(perm)),perm.values,color="#457b9d")
    ax[1].set_yticks(range(len(perm)));ax[1].set_yticklabels(perm.index)
    ax[1].set_xlabel("permutation importance (drop in R^2)")
    ax[1].set_title("(2) Multivariate (RandomForest, weighted):\nunique contribution controlling for others")
    fig.suptitle("biomarker_v2 — feature importance for believe's verdict (A0 only, reliability-weighted)",fontsize=13)
    fig.tight_layout(rect=[0,0,1,0.92]); fig.savefig(FIG/"1_feature_importance.png",dpi=100); plt.close(fig)

    # 3) drill-down: net by level (ordinal) + top drugs/cancers (evidence-weighted mean)
    fig,ax=plt.subplots(1,3,figsize=(16,5))
    def wmean_by(col,topn=12,order=None):
        g=df.groupby(col).apply(lambda d:np.sum(d.net*d.evidence)/d.evidence.sum(),include_groups=False)
        n=df.groupby(col).size()
        g=g[n>=5]
        return (g.reindex(order) if order else g.sort_values())[-topn:]
    lv=wmean_by("level",order=["1","2","3A","4","R1","R2"]).dropna()
    ax[0].bar(range(len(lv)),lv.values,color=["#9d4edd" if str(i).startswith("R") else "#2d6a4f" for i in lv.index])
    ax[0].set_xticks(range(len(lv)));ax[0].set_xticklabels([f"L{i}" for i in lv.index]);ax[0].axhline(0,color="gray")
    ax[0].set_ylabel("evidence-weighted net verdict %");ax[0].set_title("net by LEVEL")
    for col,axi,ttl in [("drug",ax[1],"net by DRUG (top/bottom)"),("cancer_type",ax[2],"net by CANCER (top/bottom)")]:
        g=wmean_by(col,topn=999); sel=pd.concat([g.head(7),g.tail(7)])
        axi.barh(range(len(sel)),sel.values,color="#457b9d");axi.set_yticks(range(len(sel)));axi.set_yticklabels([s[:24] for s in sel.index],fontsize=7)
        axi.axvline(0,color="gray");axi.set_title(ttl);axi.set_xlabel("evidence-weighted net %")
    fig.suptitle("Drill-down: evidence-weighted net verdict by level / drug / cancer",fontsize=13)
    fig.tight_layout(rect=[0,0,1,0.93]); fig.savefig(FIG/"2_drilldown.png",dpi=100); plt.close(fig)

    print("\nweighted eta^2:");print(eta.sort_values(ascending=False).round(3).to_string())
    print("\npermutation importance:");print(perm.sort_values(ascending=False).round(3).to_string())
    print("saved -> figures_feature_importance/")


if __name__=="__main__":
    main()
