"""Comprehensive figures: CELLxGENE data, believe, and their comparison.
Fresh set (clears old figures). Genes ordered by data tau (tissue-specific top).

  01_data_heatmap.png      CELLxGENE expression (row-normalized) gene x tissue
  02_believe_heatmap.png   believe up/down-regulation support (row-normalized)
  03_side_by_side.png      data | believe, readable 40-gene subset
  04_per_tissue_agreement  per-tissue Spearman(believe, data) across genes
  05_cell_scatter.png      all gene×tissue cells: expression vs believe support
  06_peak_vs_tau.png       per-gene believe peak vs tau (+AUC)
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).parent; REPO = HERE.parent.parent
FIG = HERE/"figures"
STATE = json.loads((HERE/"runs"/"jobs.json").read_text())
RANK = pd.read_csv(HERE/"data"/"gene_ranking.csv", index_col=0)
D = pd.read_csv(HERE/"data"/"data_matrix.csv", index_col=0)   # gene x tissue expression
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


def rownorm(M):
    mx=M.max(axis=1).replace(0,np.nan)
    return M.div(mx,axis=0).fillna(0)


def main():
    for p in FIG.glob("*.png"): p.unlink()
    by=fetch(list({v["job_id"] for v in STATE.values()}))
    genes=sorted({v["gene"] for v in STATE.values()}); tissues=list(D.columns)
    B=pd.DataFrame(0.,index=genes,columns=tissues); label={}
    for v in STATE.values():
        vs=by.get(v["job_id"])
        if vs and v["tissue_gt"] in B.columns: B.loc[v["gene"],v["tissue_gt"]]=vs[:K].count("support")
        label[v["gene"]]=v["label"]
    genes=[g for g in genes if g in D.index]
    B=B.loc[genes,tissues]; Dm=D.loc[genes,tissues]
    order=RANK.loc[genes,"tau"].sort_values(ascending=False).index.tolist()  # TS top
    B,Dm=B.loc[order],Dm.loc[order]
    tau=RANK.loc[order,"tau"]; y=np.array([1 if label[g]=="tissue_specific" else 0 for g in order])

    # 01 data heatmap
    fig,ax=plt.subplots(figsize=(10,16)); im=ax.imshow(rownorm(Dm).values,aspect="auto",cmap="viridis")
    ax.set_xticks(range(len(tissues)));ax.set_xticklabels(tissues,rotation=90,fontsize=8)
    ax.set_yticks(range(len(order)));ax.set_yticklabels(order,fontsize=5)
    fig.colorbar(im,ax=ax,label="expression (each gene ÷ its max)")
    ax.set_title("CELLxGENE actual expression\n(genes top=tissue-specific, bottom=housekeeping)")
    fig.tight_layout();fig.savefig(FIG/"01_data_heatmap.png",dpi=130);plt.close(fig)

    # 02 believe heatmap
    fig,ax=plt.subplots(figsize=(10,16)); im=ax.imshow(rownorm(B).values,aspect="auto",cmap="magma")
    ax.set_xticks(range(len(tissues)));ax.set_xticklabels(tissues,rotation=90,fontsize=8)
    ax.set_yticks(range(len(order)));ax.set_yticklabels(order,fontsize=5)
    fig.colorbar(im,ax=ax,label="believe support (each gene ÷ its max)")
    ax.set_title("believe up/down-regulation signal\n(same gene order as data)")
    fig.tight_layout();fig.savefig(FIG/"02_believe_heatmap.png",dpi=130);plt.close(fig)

    # 03 side by side, 40-gene readable subset (20 TS top + 20 HK bottom)
    sub=order[:20]+order[-20:]
    fig,axes=plt.subplots(1,2,figsize=(15,11),sharey=True)
    for ax,(M,ttl,cm) in zip(axes,[(rownorm(Dm.loc[sub]),"CELLxGENE expression","viridis"),
                                    (rownorm(B.loc[sub]),"believe support","magma")]):
        im=ax.imshow(M.values,aspect="auto",cmap=cm)
        ax.set_xticks(range(len(tissues)));ax.set_xticklabels(tissues,rotation=90,fontsize=8)
        ax.set_title(ttl)
        fig.colorbar(im,ax=ax,fraction=0.046)
    axes[0].set_yticks(range(len(sub)));axes[0].set_yticklabels(sub,fontsize=7)
    axes[0].axhline(19.5,color="red",lw=1.5)
    fig.suptitle("Same genes/tissues: do believe's bright cells match the data's?  (top20 tissue-specific / bottom20 housekeeping)")
    fig.tight_layout();fig.savefig(FIG/"03_side_by_side.png",dpi=140);plt.close(fig)

    # 04 per-tissue agreement
    rhos={t:spearmanr(B[t],Dm[t])[0] for t in tissues}
    s=pd.Series(rhos).sort_values()
    fig,ax=plt.subplots(figsize=(7,6))
    ax.barh(range(len(s)),s.values,color=["#457b9d" if x>=0 else "#c44" for x in s.values])
    ax.set_yticks(range(len(s)));ax.set_yticklabels(s.index,fontsize=8)
    ax.set_xlabel("Spearman(believe support, data expression) across 120 genes")
    ax.set_title("Per-tissue agreement: within each tissue,\ndoes believe rank genes like the real data?")
    ax.axvline(0,color="k",lw=.6)
    fig.tight_layout();fig.savefig(FIG/"04_per_tissue_agreement.png",dpi=140);plt.close(fig)

    # 05 cell-level scatter (all gene x tissue)
    xd=np.log1p(Dm.values.ravel()); yb=B.values.ravel()
    rho,_=spearmanr(xd,yb)
    fig,ax=plt.subplots(figsize=(7,6))
    ax.scatter(xd,yb,s=8,alpha=0.3,c="#444")
    ax.set_xlabel("log(1+ CELLxGENE expression)  [per gene×tissue cell]")
    ax.set_ylabel("believe support  [same cell]")
    ax.set_title(f"Cell-level: higher real expression → more believe signal?\nSpearman ρ = {rho:.3f} ({len(xd)} gene×tissue cells)")
    ax.grid(alpha=.3);fig.tight_layout();fig.savefig(FIG/"05_cell_scatter.png",dpi=140);plt.close(fig)

    # 06 peak vs tau
    peak=B.max(axis=1); auc=roc_auc_score(y,peak[order]); rs,_=spearmanr(peak[order],tau)
    fig,ax=plt.subplots(figsize=(7.5,6))
    cols=["#e76f51" if label[g]=="tissue_specific" else "#457b9d" for g in order]
    ax.scatter(tau,peak[order],c=cols,s=34)
    ax.set_xlabel("data tau (tissue-specificity)");ax.set_ylabel("believe peak support")
    ax.set_title(f"Per-gene summary: believe peak vs tau\nSpearman {rs:.3f}, AUC(HK/TS) {auc:.3f}")
    ax.grid(alpha=.3);fig.tight_layout();fig.savefig(FIG/"06_peak_vs_tau.png",dpi=140);plt.close(fig)

    print("per-tissue Spearman (believe vs data):")
    print(s.round(3).to_string())
    print(f"\ncell-level Spearman = {rho:.3f}; per-gene AUC = {auc:.3f}")
    print("saved 6 figures")


if __name__=="__main__":
    main()
