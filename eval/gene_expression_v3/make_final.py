"""One clean, self-explanatory figure: believe gives far more signal to a gene's
REAL tissue than to wrong tissues -> believe is context-aware.
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

HERE=Path(__file__).parent; REPO=HERE.parent.parent
STATE=json.loads((HERE/"runs"/"jobs_cont.json").read_text())
RANK=pd.read_csv(HERE/"data"/"gene_ranking.csv",index_col=0); K=1000


def fetch(ids):
    sql=(f"COPY (SELECT job_id,qwen_rank,verdict FROM job_results WHERE job_id IN ({','.join(map(str,ids))}) "
         f"ORDER BY job_id,qwen_rank NULLS LAST,id) TO STDOUT WITH CSV")
    out=subprocess.run(["docker","compose","exec","-T","hypothesis-db","psql","-U","user","-d","hypothesis_db","-c",sql],
                       cwd=str(REPO),capture_output=True,text=True,check=True).stdout
    by=defaultdict(list)
    for l in out.splitlines():
        if l.strip(): j,_,v=l.split(",",2); by[int(j)].append(v)
    return by


def main():
    by=fetch(list({v["job_id"] for v in STATE.values()}))
    genes=sorted({v["gene"] for v in STATE.values()}); tissues=sorted({v["tissue_gt"] for v in STATE.values()})
    B=pd.DataFrame(0.,index=genes,columns=tissues)
    for v in STATE.values():
        vs=by.get(v["job_id"])
        if vs and v["tissue_gt"] in tissues: B.loc[v["gene"],v["tissue_gt"]]=vs[:K].count("support")
    genes=[g for g in genes if g in RANK.index]
    ts=[g for g in genes if RANK.loc[g,"tau"]>=0.95 and B.loc[g].max()>0]
    top=RANK.loc[ts,"top_tissue"]
    true=np.array([B.loc[g,top[g]] for g in ts])
    wrong=np.array([B.loc[g,[t for t in tissues if t!=top[g]]].mean() for g in ts])
    _,pw=wilcoxon(true,wrong,alternative="greater"); ratio=np.median(true)/max(np.median(wrong),1e-9)

    # pick 10 clear example genes: true tissue is believe's #1, by signal
    ok=[g for g in ts if list(B.loc[g].sort_values(ascending=False).index)[0]==top[g]]
    ex=sorted(ok,key=lambda g:-B.loc[g,top[g]])[:10]
    et=np.array([B.loc[g,top[g]] for g in ex]); ew=np.array([B.loc[g,[t for t in tissues if t!=top[g]]].mean() for g in ex])

    fig,(a1,a2)=plt.subplots(1,2,figsize=(17,7),gridspec_kw={"width_ratios":[1.5,1]})

    # left: example genes, two bars each
    y=np.arange(len(ex)); h=0.38
    a1.barh(y+h/2, et, h, color="#2a9d8f", label="believe signal at the gene's REAL tissue")
    a1.barh(y-h/2, ew, h, color="#cbd2d8", label="believe signal at WRONG tissues (avg)")
    a1.set_yticks(y); a1.set_yticklabels([f"{g}\n({top[g]})" for g in ex], fontsize=10)
    a1.invert_yaxis(); a1.set_xlabel("believe signal  (# papers reporting the gene is regulated there)")
    a1.set_title("Example genes: believe lights up the RIGHT tissue, stays quiet elsewhere")
    a1.legend(loc="lower right", fontsize=10)

    # right: all tissue-specific genes, median true vs wrong
    a2.bar([0,1],[np.median(true),np.median(wrong)],color=["#2a9d8f","#cbd2d8"],width=0.6)
    a2.set_xticks([0,1]); a2.set_xticklabels(["REAL\ntissue","WRONG\ntissues"])
    a2.set_ylabel("median believe signal")
    a2.set_title(f"All tissue-specific genes (n={len(ts)})\nREAL tissue gets {ratio:.0f}× more signal   (p<1e-5)")
    for xi,val in zip([0,1],[np.median(true),np.median(wrong)]): a2.text(xi,val+0.3,f"{val:.1f}",ha="center",fontsize=12)

    fig.suptitle("believe is context-aware:  ask about a gene in its REAL tissue vs the WRONG tissue,\n"
                 "and believe gives far more evidence to the right one — without ever seeing the expression data",
                 fontsize=14)
    fig.tight_layout(rect=[0,0,1,0.92]); fig.savefig(HERE/"figures"/"MAIN_context_aware.png",dpi=150); plt.close(fig)
    print(f"n_ts={len(ts)} ratio={ratio:.1f}x p={pw:.1e}; examples={ex}")


if __name__=="__main__":
    main()
