"""biomarker_v3 (n=10,000 articles/hypothesis) — reproduce the biomarker_v2 figure set.

Same OncoKB associations, unified "predicts response to" framing:
  therapeutic (1,2,3A,4) -> expect SUPPORT ; resistance (R1,R2) -> expect REJECT.

Figures (-> figures/):
  FINAL_biomarker_by_level.png  3-panel boxplot: net / reliability(evidence,log) / net*tanh(ev/20)
  biomarker_pooled_net_CI.png   pooled (evidence-weighted) net + 95% bootstrap CI per level
  biomarker_K_sweep.png         pooled net vs K (1..10000, log) per level, by qwen_rank
  reliability_curves.png        evidence -> 0..1 weight normalization options (illustration)

net per association computed over ALL papers believe read (~8.8k avg), not capped at 1000.
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE=Path(__file__).parent; REPO=HERE.parent.parent; FIG=HERE/"figures"; FIG.mkdir(exist_ok=True)
STATE=json.loads((HERE/"runs"/"jobs.json").read_text())
ORDER=["1","2","3A","4","R1","R2"]
COL={"1":"#1b4332","2":"#2d6a4f","3A":"#40916c","4":"#95d5b2","R1":"#9d4edd","R2":"#c77dff"}
np.random.seed(0)


def fetch_sr(ids):
    """Return job_id -> {'S':[ranks], 'R':[ranks]} for support/reject rows, ordered by rank."""
    sql=("COPY (SELECT job_id, qwen_rank, verdict FROM job_results "
         f"WHERE job_id IN ({','.join(map(str,ids))}) AND verdict IN ('support','reject') "
         "ORDER BY job_id, qwen_rank NULLS LAST, id) TO STDOUT WITH CSV")
    out=subprocess.run(["docker","compose","exec","-T","hypothesis-db","psql","-U","user","-d","hypothesis_db","-c",sql],
                       cwd=str(REPO),capture_output=True,text=True,check=True).stdout
    by=defaultdict(lambda:{"S":[],"R":[]})
    for l in out.splitlines():
        if not l.strip(): continue
        j,rk,v=l.split(",",2); j=int(j)
        r=int(rk) if rk else 10**9
        by[j]["S" if v=="support" else "R"].append(r)
    return by


def main():
    ids=sorted({v["job_id"] for v in STATE.values()})
    by=fetch_sr(ids)

    # per-association aggregates (full read depth)
    rows=[]
    for v in STATE.values():
        d=by.get(v["job_id"],{"S":[],"R":[]}); s=len(d["S"]); r=len(d["R"]); tot=s+r
        rows.append({"level":v["level"],"expected":v["expected"],"S":s,"R":r,"ev":tot,
                     "net":(s-r)/tot*100 if tot else None,"Sr":d["S"],"Rr":d["R"]})
    levels=[l for l in ORDER if any(x["level"]==l for x in rows)]
    none={l:sum(1 for x in rows if x["level"]==l and x["ev"]==0) for l in levels}
    nL={l:sum(1 for x in rows if x["level"]==l) for l in levels}
    netbylvl={l:[x["net"] for x in rows if x["level"]==l and x["net"] is not None] for l in levels}
    evbylvl={l:[x["ev"] for x in rows if x["level"]==l and x["ev"]>0] for l in levels}
    print(f"{len(rows)} associations; results loaded for {len(by)} jobs")
    for l in levels: print(f"  L{l}: n={nL[l]} none={none[l]} medianEv={int(np.median(evbylvl[l])) if evbylvl[l] else 0}")

    explab={l:("REJ" if l.startswith("R") else "SUP") for l in levels}
    xlab=[f"{'L'+l if not l.startswith('R') else 'L'+l}\n{explab[l]}\nnone={none[l]}" for l in levels]

    # ---------- FIG 1: FINAL 3-panel boxplot ----------
    fig,ax=plt.subplots(1,3,figsize=(21,6.2))
    def boxes(axi,data,logy=False):
        bp=axi.boxplot(data,tick_labels=xlab,showfliers=False,patch_artist=True,widths=0.6)
        for patch,l in zip(bp["boxes"],levels): patch.set_facecolor(COL[l]); patch.set_alpha(.55)
        for med in bp["medians"]: med.set_color("black")
        for i,(l,dd) in enumerate(zip(levels,data)):
            if len(dd):
                jit=(np.random.rand(len(dd))-.5)*0.35
                axi.scatter(np.full(len(dd),i+1)+jit,dd,s=6,color=COL[l],alpha=.35,edgecolors="none",zorder=3)
        if logy: axi.set_yscale("log")
    boxes(ax[0],[netbylvl[l] for l in levels]); ax[0].axhline(0,ls=":",c="gray")
    ax[0].set_ylabel("net verdict %  ( +100 SUP / -100 REJ )"); ax[0].set_ylim(-105,105)
    ax[0].set_title("(1) net verdict per association\n(unweighted)")
    boxes(ax[1],[evbylvl[l] for l in levels],logy=True)
    ax[1].set_ylabel("evidence = support + reject  (log)")
    ax[1].set_title("(2) reliability: evidence amount")
    scaled=[[n*np.tanh(e/20) for n,e in zip(netbylvl[l],evbylvl[l])] for l in levels]
    boxes(ax[2],scaled); ax[2].axhline(0,ls=":",c="gray")
    ax[2].set_ylabel("net x reliability  ( net x tanh(evidence/20) )"); ax[2].set_ylim(-105,105)
    ax[2].set_title("(3) reliability-scaled net per association\n(smooth: low-evidence shrinks toward 0)")
    fig.suptitle("biomarker_v3 (n=10,000) — believe vs OncoKB level:  net / reliability / reliability-scaled net (tanh)",fontsize=14)
    fig.tight_layout(rect=[0,0,1,0.93]); fig.savefig(FIG/"FINAL_biomarker_by_level.png",dpi=130); plt.close(fig)

    # ---------- FIG 2: pooled net + 95% bootstrap CI ----------
    fig,ax=plt.subplots(figsize=(13,6))
    B=2000
    for i,l in enumerate(levels):
        sub=[x for x in rows if x["level"]==l and x["ev"]>0]
        S=np.array([x["S"] for x in sub]); R=np.array([x["R"] for x in sub]); ev=S+R
        pooled=(S.sum()-R.sum())/(S.sum()+R.sum())*100
        # bootstrap over associations
        boot=[]
        n=len(sub)
        for _ in range(B):
            idx=np.random.randint(0,n,n); ss=S[idx].sum(); rr=R[idx].sum()
            boot.append((ss-rr)/(ss+rr)*100 if ss+rr else 0)
        lo,hi=np.percentile(boot,[2.5,97.5])
        # per-association dots (jitter, size ~ evidence)
        nets=(S-R)/ev*100; jit=(np.random.rand(n)-.5)*0.5
        ax.scatter(np.full(n,i)+jit,nets,s=np.clip(ev/ev.max()*120,6,120),color=COL[l],alpha=.22,edgecolors="none",zorder=2)
        ax.errorbar(i,pooled,yerr=[[pooled-lo],[hi-pooled]],fmt="D",color="#d00000",ms=10,capsize=6,lw=2,zorder=5)
        ax.text(i+0.12,pooled,f"{pooled:+.0f}",color="#d00000",fontsize=12,fontweight="bold",va="center")
    ax.axhline(0,color="gray",lw=1)
    ax.set_xticks(range(len(levels)))
    ax.set_xticklabels([f"L{l}\nexpect {explab[l]}\nn={nL[l]}" for l in levels])
    ax.set_ylabel("net verdict = (support-reject)/(support+reject) [%]\n-100 REJECT      +100 SUPPORT")
    ax.set_ylim(-108,108)
    ax.set_title("believe vs OncoKB level — evidence-weighted (pooled) net verdict with 95% CI\n"
                 "red = pooled estimate (reliability-weighted, statistically principled); dots = per-association (size=evidence)",fontsize=12)
    h=[plt.Line2D([],[],marker="D",color="#d00000",ls="",ms=9,label="pooled net + 95% CI"),
       plt.Line2D([],[],marker="o",color="gray",ls="",ms=7,alpha=.5,label="one association (size=evidence)")]
    ax.legend(handles=h,fontsize=9,loc="center right")
    fig.tight_layout(); fig.savefig(FIG/"biomarker_pooled_net_CI.png",dpi=130); plt.close(fig)

    # ---------- FIG 3: K-sweep (1..10000) ----------
    Ks=np.unique(np.round(np.logspace(0,4,60)).astype(int))
    fig,ax=plt.subplots(figsize=(13,6.4))
    for l in levels:
        sub=[x for x in rows if x["level"]==l]
        Sr=[np.array(x["Sr"]) for x in sub]; Rr=[np.array(x["Rr"]) for x in sub]
        ys=[]
        for K in Ks:
            S=sum(int(np.searchsorted(a,K,side="right")) for a in Sr)  # ranks < K (rank<K ~ side right on 0-index)
            R=sum(int(np.searchsorted(a,K,side="right")) for a in Rr)
            ys.append((S-R)/(S+R)*100 if S+R else np.nan)
        ls="--" if l.startswith("R") else "-"
        ax.plot(Ks,ys,ls,color=COL[l],lw=2,label=f"L{l} (->{explab[l]})")
    ax.set_xscale("log"); ax.axhline(0,color="gray",lw=1)
    ax.set_xlabel("K = number of top-ranked papers believe reads (log)")
    ax.set_ylabel("pooled net verdict % (+1 SUPPORT / -1 REJECT) using top-K papers")
    ax.set_ylim(-108,108); ax.legend(fontsize=9,ncol=2,loc="center left")
    ax.set_title("believe net verdict vs how many papers it reads (K), by OncoKB level — biomarker_v3 (up to 10,000)")
    fig.tight_layout(); fig.savefig(FIG/"biomarker_K_sweep.png",dpi=130); plt.close(fig)

    # ---------- FIG 4: reliability normalization curves (illustration) ----------
    fig,ax=plt.subplots(figsize=(9,6))
    e=np.linspace(0,120,400)
    ax.plot(e,np.minimum(1,e/30),label="linear min(1, ev/30)",lw=2)
    ax.plot(e,np.tanh(e/20),label="tanh(ev/20)",lw=2)
    ax.plot(e,np.log1p(e)/np.log1p(60),label="log: log1p(ev)/log1p(60)",lw=2)
    ax.plot(e,1/(1+np.exp(-(e-15)/6)),label="sigmoid mid=15,w=6",lw=2)
    for xv in (5,10,20,50): ax.axvline(xv,ls=":",c="gray",alpha=.5)
    ax.set_xlabel("evidence (support+reject)"); ax.set_ylabel("reliability (0-1)")
    ax.set_title("reliability normalization options (how evidence -> 0..1 weight)")
    ax.legend(loc="lower right"); fig.tight_layout(); fig.savefig(FIG/"reliability_curves.png",dpi=130); plt.close(fig)

    print("saved 4 figures -> figures/")


if __name__=="__main__":
    main()
