"""Context-awareness figure (honest + intuitive). Robust evidence only.
Tissue-specific genes (tau>=0.95) from the full-range run.

P1  believe's RANK of the true tissue (1 = believe's top pick). Concentrated
    at #1 => context-aware (vs context-blind uniform baseline).
P2  counterfactual: same gene, believe at TRUE vs WRONG tissue (log-log).
P3  scramble the context => believe's correct signal collapses (tissue + mutation).
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

HERE=Path(__file__).parent; REPO=HERE.parent.parent; FIG=HERE/"figures"
STATE=json.loads((HERE/"runs"/"jobs_cont.json").read_text())
RANK=pd.read_csv(HERE/"data"/"gene_ranking.csv",index_col=0)
ABL=json.loads((HERE.parent/"biomarker"/"runs"/"ablation_scores.json").read_text())["1000"]
TAU_CUT=0.95; K=1000


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
    ts=[g for g in genes if RANK.loc[g,"tau"]>=TAU_CUT and B.loc[g].max()>0]
    top=RANK.loc[ts,"top_tissue"]
    nT=len(tissues)

    ranks=np.array([list(B.loc[g].sort_values(ascending=False).index).index(top[g])+1 for g in ts])
    tr=np.array([B.loc[g,top[g]] for g in ts])
    wr=np.array([B.loc[g,[t for t in tissues if t!=top[g]]].mean() for g in ts])

    plt.rcParams.update({"font.size":11})
    fig,ax=plt.subplots(1,3,figsize=(20,6))

    # P1 rank-of-true-tissue distribution
    buckets=["#1","#2-3","#4-5","#6-10","#11-20"]
    def b(r): return 0 if r==1 else 1 if r<=3 else 2 if r<=5 else 3 if r<=10 else 4
    cnt=np.bincount([b(r) for r in ranks],minlength=5)
    ax[0].bar(range(5),cnt/len(ranks)*100,color=["#1a7f37","#52b788","#95d5b2","#bcbcbc","#d99"])
    ax[0].axhline(100/nT,ls="--",color="red",label=f"context-blind baseline ({100/nT:.0f}% each)")
    ax[0].set_xticks(range(5)); ax[0].set_xticklabels(buckets)
    ax[0].set_xlabel("believe's rank of the gene's TRUE tissue")
    ax[0].set_ylabel("% of genes")
    ax[0].set_title(f"(1) believe ranks the TRUE tissue near the top\n"
                    f"{cnt[0]}/{len(ranks)} ranked #1 (tissue-specific genes, tau≥{TAU_CUT})")
    ax[0].legend(fontsize=8)

    # P2 counterfactual
    _,pw=wilcoxon(tr,wr,alternative="greater")
    ax[1].scatter(wr+0.3,tr+0.3,c="#e76f51",s=46,edgecolor="white",lw=.5)
    lim=[0.3,max(tr.max(),wr.max())*1.4]; ax[1].plot(lim,lim,"--",color="gray")
    ax[1].set_xscale("log");ax[1].set_yscale("log");ax[1].set_xlim(lim);ax[1].set_ylim(lim)
    ax[1].set_xlabel("believe signal at WRONG tissues (avg)")
    ax[1].set_ylabel("believe signal at the TRUE tissue")
    ax[1].set_title(f"(2) same gene, change the context\nTRUE tissue gets {np.median(tr)/max(np.median(wr),1e-9):.0f}× more signal · p={pw:.0e}")
    ax[1].text(0.05,0.92,"each dot = one gene\nabove line = believe favors TRUE context",
               transform=ax[1].transAxes,fontsize=9,va="top")

    # P3 scramble context -> collapse (tissue + mutation), as % of correct-context
    def rej(d): n=sum(d.get(k,0) for k in("support","reject","none","split")); return d.get("reject",0)/n*100
    tissue_collapse=np.median(wr)/max(np.median(tr),1e-9)*100
    mut_collapse=rej(ABL["A3"]["resistance"])/rej(ABL["A0"]["resistance"])*100
    x=np.arange(2); w=0.36
    ax[2].bar(x-w/2,[100,100],w,color="#2a9d8f",label="correct context")
    ax[2].bar(x+w/2,[tissue_collapse,mut_collapse],w,color="#c44",label="scrambled context")
    ax[2].set_xticks(x); ax[2].set_xticklabels(["TISSUE\n(gene-expression eval)","MUTATION\n(biomarker eval)"])
    ax[2].set_ylabel("believe correct signal (correct context = 100%)")
    ax[2].set_title("(3) scramble the context → signal collapses\n(same finding on an independent eval)")
    for xi,v in zip(x-w/2,[100,100]):ax[2].text(xi,v+1,"100%",ha="center",fontsize=9)
    for xi,v in zip(x+w/2,[tissue_collapse,mut_collapse]):ax[2].text(xi,v+1,f"{v:.0f}%",ha="center",fontsize=9)
    ax[2].legend()

    fig.suptitle("believe is context-aware: its conclusions are conditioned on biological context",fontsize=15,y=1.0)
    fig.tight_layout(rect=[0,0,1,0.93]); fig.savefig(FIG/"context_aware.png",dpi=145); plt.close(fig)
    print(f"P1 #1={cnt[0]}/{len(ranks)} ({cnt[0]/len(ranks)*100:.0f}%), buckets {cnt.tolist()}")
    print(f"P2 ratio {np.median(tr)/max(np.median(wr),1e-9):.1f}x p={pw:.1e}")
    print(f"P3 tissue collapse->{tissue_collapse:.0f}%, mutation->{mut_collapse:.0f}%")


if __name__=="__main__":
    main()
