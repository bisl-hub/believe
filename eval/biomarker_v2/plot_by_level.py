"""biomarker_v2: detailed OncoKB-level analysis (no-evidence cases excluded).

Hypothesis "predicts response to": therapeutic(1,2,3A,4)->SUPPORT, resistance(R1,R2)->REJECT.
4 panels + detailed per-level table.
  A accuracy by level @top-1000 (none excluded)
  B accuracy vs K by level
  C verdict composition by level @top-1000 (support/reject/none)
  D per-association signal strength: net = (support-reject)/topK distribution, by level
"""
import json, subprocess
from collections import defaultdict
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE=Path(__file__).parent; REPO=HERE.parent.parent
STATE=json.loads((HERE/"runs"/"jobs.json").read_text())
KS=[1,10,100,1000]; ORDER=["1","2","3A","4","R1","R2"]


def fetch(ids):
    sql=(f"COPY (SELECT job_id,qwen_rank,verdict FROM job_results WHERE job_id IN ({','.join(map(str,ids))}) "
         f"ORDER BY job_id,qwen_rank NULLS LAST,id) TO STDOUT WITH CSV")
    out=subprocess.run(["docker","compose","exec","-T","hypothesis-db","psql","-U","user","-d","hypothesis_db","-c",sql],
                       cwd=str(REPO),capture_output=True,text=True,check=True).stdout
    by=defaultdict(list)
    for l in out.splitlines():
        if l.strip(): j,_,v=l.split(",",2); by[int(j)].append(v)
    return by


def counts(vs,k):
    t=vs[:k]; return t.count("support"), t.count("reject")


def maj(s,r):
    if s==0 and r==0: return "none"
    return "support" if s>r else ("reject" if r>s else "tie")


def main():
    by=fetch(list({v["job_id"] for v in STATE.values()}))
    lv=defaultdict(list)
    for v in STATE.values():
        vs=by.get(v["job_id"])
        if vs: lv[v["level"]].append((vs, v["expected"]))
    levels=[l for l in ORDER if l in lv]
    n={l:len(lv[l]) for l in levels}
    exp={l:("reject" if l.startswith("R") else "support") for l in levels}
    col={l:("#9d4edd" if l.startswith("R") else "#2d6a4f") for l in levels}

    dec={l:{} for l in levels}; comp={}; netdist={}
    table=[]
    for l in levels:
        for k in KS:
            cor=dec_n=0
            for vs,e in lv[l]:
                s,r=counts(vs,k); m=maj(s,r)
                if m!="none":
                    dec_n+=1; cor+= (m==e)
            dec[l][k]=cor/dec_n*100 if dec_n else 0
        # K=1000 composition + net distribution + table row
        c=defaultdict(int); nets=[]; sups=[]; rejs=[]
        for vs,e in lv[l]:
            s,r=counts(vs,1000); m=maj(s,r); c[m]+=1
            nets.append((s-r)/len(vs[:1000])); sups.append(s); rejs.append(r)
        comp[l]=c; netdist[l]=np.array(nets)
        dec_n=n[l]-c["none"]; cor=c[exp[l]]
        table.append((l,n[l],c["none"],c["support"],c["reject"],c.get("tie",0),
                      cor/dec_n*100 if dec_n else 0, np.median(sups), np.median(rejs)))

    fig,ax=plt.subplots(2,2,figsize=(16,11))

    # A
    y=[dec[l][1000] for l in levels]
    bA=ax[0,0].bar(range(len(levels)),y,color=[col[l] for l in levels])
    ax[0,0].set_xticks(range(len(levels))); ax[0,0].set_xticklabels([f"L{l}\n(n={n[l]}, ->{exp[l][:3]})" for l in levels])
    ax[0,0].set_ylabel("correct% (evidence-bearing cases)"); ax[0,0].set_ylim(0,105); ax[0,0].axhline(50,ls=":",c="gray")
    ax[0,0].set_title("(A) Accuracy by OncoKB level @top-1000 (no-evidence excluded)")
    for b,val in zip(bA,y): ax[0,0].text(b.get_x()+b.get_width()/2,val+1.5,f"{val:.0f}%",ha="center",fontsize=10)

    # B
    for l in levels:
        ax[0,1].plot(range(len(KS)),[dec[l][k] for k in KS],"-o",color=col[l],lw=2,label=f"L{l} (->{exp[l][:3]})")
    ax[0,1].set_xticks(range(len(KS))); ax[0,1].set_xticklabels(KS); ax[0,1].set_xlabel("top-K")
    ax[0,1].set_ylabel("correct% (none excluded)"); ax[0,1].set_ylim(0,105); ax[0,1].grid(alpha=.3)
    ax[0,1].legend(fontsize=9,ncol=2); ax[0,1].set_title("(B) Accuracy vs K, by level")

    # C
    sup=[comp[l]["support"]/n[l]*100 for l in levels]; rej=[comp[l]["reject"]/n[l]*100 for l in levels]
    non=[comp[l]["none"]/n[l]*100 for l in levels]; tie=[comp[l].get("tie",0)/n[l]*100 for l in levels]
    x=np.arange(len(levels))
    ax[1,0].bar(x,sup,color="#2a9d8f",label="SUPPORT majority")
    ax[1,0].bar(x,rej,bottom=sup,color="#e76f51",label="REJECT majority")
    base=np.array(sup)+np.array(rej)
    ax[1,0].bar(x,tie,bottom=base,color="#f4a261",label="tie")
    ax[1,0].bar(x,non,bottom=base+np.array(tie),color="#cccccc",label="none (no evidence)")
    ax[1,0].set_xticks(x); ax[1,0].set_xticklabels([f"L{l}" for l in levels]); ax[1,0].set_ylabel("% of associations")
    ax[1,0].set_title("(C) Verdict composition by level @top-1000"); ax[1,0].legend(fontsize=9)

    # D net distribution (box)
    data=[netdist[l] for l in levels]
    bp=ax[1,1].boxplot(data,tick_labels=[f"L{l}" for l in levels],showfliers=False,patch_artist=True)
    for patch,l in zip(bp["boxes"],levels): patch.set_facecolor(col[l]); patch.set_alpha(.6)
    ax[1,1].axhline(0,ls=":",c="gray"); ax[1,1].set_ylabel("net signal = (support - reject) / top-K")
    ax[1,1].set_title("(D) believe net signal strength by level @top-1000\n(>0 = leans SUPPORT, <0 = leans REJECT)")

    fig.suptitle("biomarker_v2 x OncoKB: detailed accuracy by evidence level (no-evidence cases excluded)",fontsize=15)
    fig.tight_layout(rect=[0,0,1,0.95]); fig.savefig(HERE/"figures"/"by_level_detailed.png",dpi=145); plt.close(fig)

    print(f"{'lvl':>4}{'n':>5}{'none':>6}{'sup':>5}{'rej':>5}{'tie':>5}{'correct%':>10}{'medSup':>8}{'medRej':>8}")
    for l,N,no,s,r,t,acc,ms,mr in table:
        print(f"{l:>4}{N:>5}{no:>6}{s:>5}{r:>5}{t:>5}{acc:>9.0f}%{ms:>8.0f}{mr:>8.0f}")
    print("saved figures/by_level_detailed.png")


if __name__=="__main__":
    main()
