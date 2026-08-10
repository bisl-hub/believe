"""Clean, organized ablation figure (context contribution).
A0 full | A1 -alteration(generalized) | A2 -cancer | A3 gene-only.
Saves figures/ablation_summary.png
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = Path(__file__).parent; REPO = HERE.parent.parent
ASSOC = {str(o["row_id"]): o for o in json.loads((HERE/"data"/"associations.json").read_text())}
A0 = json.loads((HERE/"runs"/"jobs.json").read_text())          # row_id -> {job_id, category, expected}
ABL = json.loads((HERE/"runs"/"ablation_jobs.json").read_text())# arm -> hyp -> {job_id,row_ids}
K = 1000


def fetch(ids):
    sql=(f"COPY (SELECT job_id,qwen_rank,verdict FROM job_results WHERE job_id IN ({','.join(map(str,ids))}) "
         f"ORDER BY job_id,qwen_rank NULLS LAST,id) TO STDOUT WITH CSV")
    out=subprocess.run(["docker","compose","exec","-T","hypothesis-db","psql","-U","user","-d","hypothesis_db","-c",sql],
                       cwd=str(REPO),capture_output=True,text=True,check=True).stdout
    by=defaultdict(list)
    for l in out.splitlines():
        if l.strip(): j,_,v=l.split(",",2); by[int(j)].append(v)
    return by


def maj(vs):
    t=vs[:K]; s=t.count("support"); r=t.count("reject")
    return "support" if s>r else ("reject" if r>s else "none")
def net(vs):
    t=vs[:K]; s=t.count("support"); r=t.count("reject")
    return (s-r)/(s+r)*100 if s+r else 0.0


def arm_rowjob(arm):
    m={}
    for h in ABL[arm].values():
        for rid in h["row_ids"]: m[str(rid)]=h["job_id"]
    return m


def main():
    a1,a2,a3=arm_rowjob("A1"),arm_rowjob("A2"),arm_rowjob("A3")
    rowjob={"A0":{r:A0[r]["job_id"] for r in A0},"A1":a1,"A2":a2,"A3":a3}
    allids=set()
    for d in rowjob.values(): allids|=set(d.values())
    by=fetch(list(allids))

    rows=list(A0)  # row_ids
    cat={r:A0[r]["category"] for r in rows}; exp={r:A0[r]["expected"] for r in rows}
    gene={r:ASSOC[r]["gene"] for r in rows}
    arms=["A0","A1","A2","A3"]; armlab={"A0":"A0\nfull","A1":"A1\n-alteration","A2":"A2\n-cancer","A3":"A3\ngene-only"}

    fig,ax=plt.subplots(1,3,figsize=(21,6.4))

    # Panel A: correct-direction majority % by arm, per category
    for cat_name,c in [("therapeutic","#2d6a4f"),("resistance","#9d4edd")]:
        ys=[]
        for arm in arms:
            rr=[r for r in rows if cat[r]==cat_name]
            ok=tot=0
            for r in rr:
                vs=by.get(rowjob[arm].get(r))
                if not vs: continue
                m=maj(vs)
                if m!="none":
                    tot+=1; ok+= (m==exp[r])
            ys.append(ok/tot*100 if tot else 0)
        ax[0].plot(range(4),ys,"-o",color=c,lw=2.5,ms=8,
                   label=f"{cat_name} (correct = {'SUPPORT' if cat_name=='therapeutic' else 'REJECT'})")
        for i,y in enumerate(ys): ax[0].text(i,y+2,f"{y:.0f}",ha="center",fontsize=9,color=c)
    ax[0].set_xticks(range(4)); ax[0].set_xticklabels([armlab[a] for a in arms])
    ax[0].set_ylabel("correct-direction majority %  (evidence-bearing)"); ax[0].set_ylim(0,105)
    ax[0].set_title("(A) Removing the specific MUTATION breaks the verdict\n(cancer removal barely matters)")
    ax[0].grid(alpha=.3); ax[0].legend(fontsize=9)

    # Panel B: per-gene resistance reject% A0 vs A1 (top genes by count)
    rgenes=defaultdict(lambda:{"A0":[0,0],"A1":[0,0]})  # reject, n
    for r in rows:
        if cat[r]!="resistance": continue
        g=gene[r]
        for arm in ("A0","A1"):
            vs=by.get(rowjob[arm].get(r))
            if vs: rgenes[g][arm][1]+=1; rgenes[g][arm][0]+= (maj(vs)=="reject")
    items=sorted(rgenes.items(),key=lambda kv:-kv[1]["A0"][1])[:10]
    names=[g for g,_ in items]
    a0p=[d["A0"][0]/d["A0"][1]*100 for _,d in items]
    a1p=[d["A1"][0]/d["A1"][1]*100 if d["A1"][1] else 0 for _,d in items]
    x=np.arange(len(names)); w=0.4
    ax[1].bar(x-w/2,a0p,w,color="#264653",label="A0: keeps mutation")
    ax[1].bar(x+w/2,a1p,w,color="#e9c46a",label="A1: mutation generalized")
    ax[1].set_xticks(x); ax[1].set_xticklabels([f"{g}\n(n={d['A0'][1]})" for g,d in items],fontsize=8)
    ax[1].set_ylabel("resistance correctly REJECTED %"); ax[1].set_ylim(0,105)
    ax[1].set_title("(B) Resistance detection collapses per gene\nwhen the mutation is removed"); ax[1].legend(fontsize=9)

    # Panel C: feature importance |Δnet| alteration vs cancer, per category
    imp={"therapeutic":{"alt":[],"can":[]},"resistance":{"alt":[],"can":[]}}
    for r in rows:
        v0=by.get(rowjob["A0"].get(r)); v1=by.get(a1.get(r)); v2=by.get(a2.get(r))
        if not (v0 and v1 and v2): continue
        n0=net(v0); imp[cat[r]]["alt"].append(abs(net(v1)-n0)); imp[cat[r]]["can"].append(abs(net(v2)-n0))
    cats=["therapeutic","resistance"]; x=np.arange(2); w=0.38
    altm=[np.mean(imp[c]["alt"]) for c in cats]; canm=[np.mean(imp[c]["can"]) for c in cats]
    ax[2].bar(x-w/2,altm,w,color="#e76f51",label="remove mutation")
    ax[2].bar(x+w/2,canm,w,color="#457b9d",label="remove cancer")
    ax[2].set_xticks(x); ax[2].set_xticklabels(cats); ax[2].set_ylabel("mean |change in net verdict|")
    ax[2].set_title("(C) Feature importance: which context matters\n(mutation >> cancer, esp. resistance)")
    ax[2].legend(fontsize=9)
    for xi,v in zip(x-w/2,altm): ax[2].text(xi,v+0.5,f"{v:.0f}",ha="center",fontsize=9)
    for xi,v in zip(x+w/2,canm): ax[2].text(xi,v+0.5,f"{v:.0f}",ha="center",fontsize=9)

    fig.suptitle("biomarker ablation — which biological context does believe rely on?",fontsize=15)
    fig.tight_layout(rect=[0,0,1,0.93]); fig.savefig(HERE/"figures"/"ablation_summary.png",dpi=150); plt.close(fig)
    print("saved figures/ablation_summary.png")


if __name__ == "__main__":
    main()
