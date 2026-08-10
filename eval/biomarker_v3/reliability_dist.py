"""biomarker_v3 — distribution of 'reliability' (= evidence = support+reject)
per association, pooled across ALL OncoKB levels.

Shows how much judgeable evidence believe actually accumulates per hypothesis
(out of ~8.8k papers read), independent of level. Saves figures/reliability_distribution.png
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE=Path(__file__).parent; REPO=HERE.parent.parent; FIG=HERE/"figures"; FIG.mkdir(exist_ok=True)
STATE=json.loads((HERE/"runs"/"jobs.json").read_text())


def fetch_counts(ids):
    sql=("COPY (SELECT job_id, count(*) FILTER (WHERE verdict IN ('support','reject')) "
         f"FROM job_results WHERE job_id IN ({','.join(map(str,ids))}) GROUP BY job_id) TO STDOUT WITH CSV")
    out=subprocess.run(["docker","compose","exec","-T","hypothesis-db","psql","-U","user","-d","hypothesis_db","-c",sql],
                       cwd=str(REPO),capture_output=True,text=True,check=True).stdout
    ev={}
    for l in out.splitlines():
        if l.strip(): j,c=l.split(","); ev[int(j)]=int(c)
    return ev


def main():
    ids=sorted({v["job_id"] for v in STATE.values()})
    evmap=fetch_counts(ids)
    ev=np.array([evmap.get(v["job_id"],0) for v in STATE.values()])  # one per association
    n=len(ev); nz=ev[ev>0]
    none=int((ev==0).sum())

    q=np.percentile(nz,[25,50,75,90,95])
    print(f"associations: {n}  | none(ev=0): {none} ({none/n*100:.1f}%)")
    print(f"evidence>0 (n={len(nz)}): median={np.median(nz):.0f}  mean={nz.mean():.1f}  max={nz.max()}")
    print(f"  quartiles 25/50/75/90/95 = {q.round(0)}")
    for t in (5,10,20,30,50):
        print(f"  ev < {t:>2}: {(ev<t).mean()*100:5.1f}% of all   |  >= {t}: {(ev>=t).mean()*100:5.1f}%")

    fig,ax=plt.subplots(1,2,figsize=(15,5.6))

    # (A) histogram on log scale (evidence>0), with knee markers
    bins=np.logspace(0,np.log10(nz.max()),40)
    ax[0].hist(nz,bins=bins,color="#2a9d8f",alpha=.8,edgecolor="white")
    ax[0].set_xscale("log")
    for t,lab in [(10,"10"),(20,"20"),(30,"30")]:
        ax[0].axvline(t,ls=":",c="gray"); ax[0].text(t,ax[0].get_ylim()[1]*.95,lab,ha="center",fontsize=8,color="gray")
    ax[0].axvline(np.median(nz),color="#d00000",lw=2,label=f"median = {np.median(nz):.0f}")
    ax[0].set_xlabel("reliability = evidence = support + reject  (log)")
    ax[0].set_ylabel("number of associations")
    ax[0].set_title(f"(A) Evidence per association, all levels pooled\n(evidence>0: n={len(nz)}; {none} more have zero evidence)")
    ax[0].legend()

    # (B) cumulative fraction (ECDF) including zeros
    xs=np.sort(ev); cdf=np.arange(1,n+1)/n
    ax[1].plot(xs,cdf*100,color="#264653",lw=2)
    ax[1].set_xscale("symlog")
    for t in (10,20,30,50):
        f=(ev<t).mean()*100
        ax[1].axvline(t,ls=":",c="gray",alpha=.6)
        ax[1].annotate(f"{f:.0f}% < {t}",(t,f),fontsize=8,color="gray",xytext=(t*1.1,f-4))
    ax[1].axhline((none/n*100),ls="--",c="#9d4edd",alpha=.7,label=f"zero-evidence floor = {none/n*100:.0f}%")
    ax[1].set_xlabel("reliability = evidence (symlog, includes 0)")
    ax[1].set_ylabel("cumulative % of associations  (<= x)")
    ax[1].set_ylim(0,100)
    ax[1].set_title("(B) Cumulative distribution of reliability\n(how many hypotheses are evidence-poor)")
    ax[1].legend(loc="lower right")

    fig.suptitle(f"biomarker_v3 — reliability (evidence) distribution across all {n} associations, level-agnostic",fontsize=13)
    fig.tight_layout(rect=[0,0,1,0.94]); fig.savefig(FIG/"reliability_distribution.png",dpi=130); plt.close(fig)
    print("saved -> figures/reliability_distribution.png")


if __name__=="__main__":
    main()
