"""Clear per-gene plot: for famous tissue-specific genes, show believe support
across tissues as bars; the gene's TRUE tissue (from CELLxGENE) is red.
If believe's tallest bar is red -> believe found the right tissue.
Also overlay actual expression (line) for visual confirmation.
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE=Path(__file__).parent; REPO=HERE.parent.parent
STATE=json.loads((HERE/"runs"/"jobs.json").read_text())
D=pd.read_csv(HERE/"data"/"data_matrix.csv",index_col=0)
K=1000


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
    tissues=list(D.columns); genes=sorted({v["gene"] for v in STATE.values()})
    B=pd.DataFrame(0.,index=genes,columns=tissues); label={}
    for v in STATE.values():
        vs=by.get(v["job_id"])
        if vs and v["tissue_gt"] in B.columns: B.loc[v["gene"],v["tissue_gt"]]=vs[:K].count("support")
        label[v["gene"]]=v["label"]
    ts=[g for g in genes if label[g]=="tissue_specific" and g in D.index]
    # pick 9 tissue-specific genes with strongest believe signal (so bars are visible)
    pick=B.loc[ts].max(axis=1).sort_values(ascending=False).head(9).index.tolist()

    TOPN=10
    fig,axes=plt.subplots(3,3,figsize=(18,13))
    correct=0
    for ax,g in zip(axes.flat,pick):
        bel=B.loc[g,tissues]; dat=D.loc[g,tissues]
        true_t=dat.idxmax()
        order=bel.sort_values(ascending=False)            # believe ranking
        rank_true=list(order.index).index(true_t)+1
        ok=(rank_true==1); correct+=ok
        show=order.head(TOPN)[::-1]                        # top-N, highest at top of barh
        colors=["#e63946" if t==true_t else "#9bb8cf" for t in show.index]
        ax.barh(range(len(show)),show.values,color=colors)
        ax.set_yticks(range(len(show)))
        ax.set_yticklabels([(f"★ {t}" if t==true_t else t) for t in show.index],fontsize=9)
        ax.set_xlabel("believe support (# papers reporting up/down regulation)",fontsize=8)
        ax.set_title(f"{g}   — true tissue: {true_t}  (believe rank #{rank_true})",
                     fontsize=11, color=("#1a7f37" if ok else "#b00"), fontweight="bold")
    fig.suptitle("For each gene: believe's tissue ranking (top-10).  RED ★ = the gene's TRUE tissue (CELLxGENE).\n"
                 f"If RED is at the TOP → believe ranked the right tissue #1.   [{correct}/9 ranked #1]",fontsize=13)
    fig.tight_layout(rect=[0,0,1,0.93])
    fig.savefig(HERE/"figures"/"examples.png",dpi=130); plt.close(fig)
    print(f"correct {correct}/9; genes: {pick}")


if __name__=="__main__":
    main()
