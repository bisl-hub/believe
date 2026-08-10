"""biomarker_v2 — does believe READ CONTEXT, or just match the template?

Every one of the 1122 hypotheses has the SAME template:
    "In {cancer}, {biomarker} predicts response to {drug}."
Only the biological entities change. So any swing in believe's verdict is
driven by what it read about those entities — i.e. context.

Sharpest demonstration (A0 only, no new runs):
  Hold the DRUG fixed, vary only the biomarker → believe FLIPS sign.
  A keyword/template matcher would give the drug one verdict regardless.

Panels:
  (A) Same drug, sensitizing vs resistance biomarker -> net verdict flips
  (B) Level monotonicity (pooled net, evidence-weighted): L1 -> R2
  (C) Feature importance: biomarker (gene+mutation) >> drug, cancer
Figure -> figures_context/context_aware.png
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance

HERE=Path(__file__).parent; REPO=HERE.parent.parent
FIG=HERE/"figures_context"; FIG.mkdir(exist_ok=True)
STATE=json.loads((HERE/"runs"/"jobs.json").read_text())
K=1000
FEATURES=["biomarker","cancer_type","drug"]
LEVEL_ORDER=["1","2","3A","4","R1","R2"]


def fetch(ids):
    sql=(f"COPY (SELECT job_id,verdict FROM job_results WHERE job_id IN ({','.join(map(str,ids))})) TO STDOUT WITH CSV")
    out=subprocess.run(["docker","compose","exec","-T","hypothesis-db","psql","-U","user","-d","hypothesis_db","-c",sql],
                       cwd=str(REPO),capture_output=True,text=True,check=True).stdout
    by=defaultdict(lambda:[0,0])  # job_id -> [support, reject]
    for l in out.splitlines():
        if not l.strip(): continue
        j,v=l.split(",",1); j=int(j)
        if v=="support": by[j][0]+=1
        elif v=="reject": by[j][1]+=1
    return by


def main():
    by=fetch(sorted({v["job_id"] for v in STATE.values()}))
    rec=[]
    for v in STATE.values():
        s,r=by.get(v["job_id"],[0,0]); tot=s+r
        if tot==0: continue
        rec.append({"biomarker":v["biomarker"],"drug":v["drug"],"cancer_type":v["cancer_type"],
                    "level":v["level"],"category":v["category"],"expected":v["expected"],
                    "support":s,"reject":r,"evidence":tot,"net":(s-r)/tot*100})
    df=pd.DataFrame(rec)
    df.to_csv(FIG/"associations_scored.csv",index=False)
    print(f"{len(df)} associations with evidence")

    # pooled net helper (evidence-weighted = inverse-variance)
    def pooled(sub):
        S,R=sub.support.sum(),sub.reject.sum()
        return (S-R)/(S+R)*100 if S+R else np.nan

    fig=plt.figure(figsize=(20,6.6))
    gs=fig.add_gridspec(1,3,width_ratios=[1.25,1,1])

    # ---- (A) same drug, biomarker flips verdict ----
    axA=fig.add_subplot(gs[0,0])
    pairs=[]
    for d,sub in df.groupby("drug"):
        ther=sub[sub.category=="therapeutic"]; resi=sub[sub.category=="resistance"]
        if len(ther) and len(resi):
            pairs.append((d,pooled(ther),pooled(resi),
                          ther.evidence.sum(),resi.evidence.sum(),
                          pooled(ther)-pooled(resi)))
    pd.DataFrame(pairs,columns=["drug","net_ther","net_resi","ev_ther","ev_resi","gap"]
                 ).sort_values("gap",ascending=False).to_csv(FIG/"same_drug_flip.csv",index=False)
    pairs.sort(key=lambda x:x[5],reverse=True)
    pairs=pairs[:12]
    y=np.arange(len(pairs))
    nt=[p[1] for p in pairs]; nr=[p[2] for p in pairs]
    axA.barh(y+0.2,nt,0.4,color="#2d6a4f",label="sensitizing biomarker (therapeutic)")
    axA.barh(y-0.2,nr,0.4,color="#9d4edd",label="resistance biomarker (R1/R2)")
    axA.set_yticks(y); axA.set_yticklabels([p[0][:22] for p in pairs],fontsize=8)
    axA.invert_yaxis(); axA.axvline(0,color="gray",lw=1)
    axA.set_xlabel("pooled net verdict %  (support vs reject)")
    axA.set_title("(A) SAME DRUG, biomarker context flips the verdict\n"
                  "believe is not matching the drug — it reads the biomarker",fontsize=11)
    axA.legend(fontsize=8,loc="lower right")

    # ---- (B) level monotonicity, pooled net ----
    axB=fig.add_subplot(gs[0,1])
    lv=[]
    for L in LEVEL_ORDER:
        sub=df[df.level==L]
        if len(sub): lv.append((L,pooled(sub),sub.evidence.sum()))
    Ls=[x[0] for x in lv]; ns=[x[1] for x in lv]
    cols=["#9d4edd" if L.startswith("R") else "#2d6a4f" for L in Ls]
    axB.bar(range(len(Ls)),ns,color=cols)
    axB.set_xticks(range(len(Ls))); axB.set_xticklabels([f"L{L}" for L in Ls])
    axB.axhline(0,color="gray",lw=1)
    axB.set_ylabel("pooled net verdict %")
    axB.set_title("(B) believe tracks evidence strength\nsensitizing (green) -> resistance (purple)",fontsize=11)
    for i,v in enumerate(ns): axB.text(i,v+(3 if v>=0 else -8),f"{v:+.0f}",ha="center",fontsize=9)

    # ---- (C) feature importance (reliability-weighted) ----
    axC=fig.add_subplot(gs[0,2])
    def weta2(y,w,g):
        y=np.asarray(y,float); w=np.asarray(w,float)
        yb=np.sum(w*y)/np.sum(w); sst=np.sum(w*(y-yb)**2); ssb=0.0
        for k in pd.unique(g):
            m=g==k; wg=w[m].sum()
            if wg>0: ssb+=wg*(np.sum(w[m]*y[m])/wg-yb)**2
        return ssb/sst if sst>0 else 0.0
    eta={f:weta2(df.net,df.evidence,df[f].values) for f in FEATURES}
    X=pd.DataFrame({f:df[f].astype("category").cat.codes for f in FEATURES})
    rf=RandomForestRegressor(n_estimators=400,random_state=0,n_jobs=-1,min_samples_leaf=5)
    rf.fit(X,df.net,sample_weight=df.evidence)
    pi=permutation_importance(rf,X,df.net,sample_weight=df.evidence,n_repeats=20,random_state=0)
    perm=dict(zip(FEATURES,pi.importances_mean))
    order=sorted(FEATURES,key=lambda f:perm[f])
    yv=np.arange(len(order)); wd=0.4
    axC.barh(yv+0.2,[eta[f] for f in order],wd,color="#2a9d8f",label="univariate weighted eta^2")
    mx=max(perm.values()) or 1
    axC.barh(yv-0.2,[perm[f]/mx for f in order],wd,color="#457b9d",label="RF perm. importance (norm)")
    axC.set_yticks(yv); axC.set_yticklabels([{"biomarker":"biomarker\n(gene+mutation)","cancer_type":"cancer","drug":"drug"}[f] for f in order])
    axC.set_xlabel("share of verdict variance explained")
    axC.set_title("(C) Which context drives the verdict?\nthe biomarker, far above drug or cancer",fontsize=11)
    axC.legend(fontsize=8,loc="lower right")

    fig.suptitle("biomarker_v2 — believe reads biological context (identical sentence template across all 1122 hypotheses)",fontsize=13)
    fig.tight_layout(rect=[0,0,1,0.94]); fig.savefig(FIG/"context_aware.png",dpi=130); plt.close(fig)

    print("\n(A) same-drug flips (top):")
    for p in pairs[:8]: print(f"  {p[0][:26]:26} ther {p[1]:+6.1f}  resi {p[2]:+6.1f}  gap {p[5]:5.0f}")
    print("\n(B) pooled net by level:", {L:round(v,1) for L,v in zip(Ls,ns)})
    print("\n(C) weighted eta^2:", {f:round(eta[f],3) for f in FEATURES})
    print("    perm importance:", {f:round(perm[f],3) for f in FEATURES})
    print("saved -> figures_context/context_aware.png")


if __name__=="__main__":
    main()
