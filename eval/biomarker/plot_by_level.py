"""OncoKB level별 정리 plot — 'none'(support=reject=0, 근거없음) 제외.

각 연관은 "predicts response to" 가설, 기대 verdict:
  therapeutic(1,2,3A,4) -> SUPPORT,  resistance(R1,R2) -> REJECT.
근거 있는 케이스(support+reject>0)만으로 level별 정답률(decided-correct%)을 그린다.

  panel1: level별 decided-correct% (K=1000, none 제외) + n
  panel2: level별 decided-correct% vs K (추세)
  panel3: level별 구성 (support-maj / reject-maj / none) 비율 (K=1000)
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


def maj(vs,k):
    t=vs[:k]; s=t.count("support"); r=t.count("reject")
    if s==0 and r==0: return "none"
    return "support" if s>r else ("reject" if r>s else "tie")


def main():
    by=fetch(list({v["job_id"] for v in STATE.values()}))
    # level -> list of (verdicts, expected)
    lv=defaultdict(list)
    for v in STATE.values():
        vs=by.get(v["job_id"])
        if vs: lv[v["level"]].append((vs, v["expected"]))
    levels=[l for l in ORDER if l in lv]
    n={l:len(lv[l]) for l in levels}
    exp={l:("reject" if l.startswith("R") else "support") for l in levels}
    col={l:("#9d4edd" if l.startswith("R") else "#2d6a4f") for l in levels}

    # decided-correct% per level per K
    dec={l:{} for l in levels}; none_pct={l:{} for l in levels}
    for l in levels:
        for k in KS:
            c=defaultdict(int)
            for vs,e in lv[l]:
                m=maj(vs,k); c[m]+=1;
                if m==e: c["__correct"]+=1
            decided=n[l]-c["none"]
            dec[l][k]= c["__correct"]/decided*100 if decided else 0
            none_pct[l][k]= c["none"]/n[l]*100

    fig,ax=plt.subplots(1,3,figsize=(21,6.2))

    # panel1: decided-correct% at K=1000
    y=[dec[l][1000] for l in levels]
    bars=ax[0].bar(range(len(levels)),y,color=[col[l] for l in levels])
    ax[0].set_xticks(range(len(levels))); ax[0].set_xticklabels([f"L{l}\n(n={n[l]})\n→{exp[l][:3]}" for l in levels])
    ax[0].set_ylabel("correct% (cases with evidence)")
    ax[0].set_title("(1) Accuracy by OncoKB level @top-1000\n(no-evidence cases excluded)")
    ax[0].set_ylim(0,100); ax[0].axhline(50,ls=":",color="gray")
    for b,val in zip(bars,y): ax[0].text(b.get_x()+b.get_width()/2,val+1,f"{val:.0f}%",ha="center",fontsize=10)

    # panel2: decided-correct% vs K
    for l in levels:
        ax[1].plot(range(len(KS)),[dec[l][k] for k in KS],"-o",color=col[l],lw=2,label=f"L{l} (→{exp[l][:3]})")
    ax[1].set_xticks(range(len(KS))); ax[1].set_xticklabels(KS)
    ax[1].set_xlabel("top-K"); ax[1].set_ylabel("correct% (none excluded)"); ax[1].set_ylim(0,105)
    ax[1].set_title("(2) accuracy vs K, by level"); ax[1].grid(alpha=.3); ax[1].legend(fontsize=9,ncol=2)

    # panel3: composition at K=1000 (support-maj / reject-maj / none)
    sup=[];rej=[];non=[]
    for l in levels:
        c=defaultdict(int)
        for vs,e in lv[l]: c[maj(vs,1000)]+=1
        tot=n[l]; sup.append((c["support"])/tot*100); rej.append((c["reject"])/tot*100); non.append(c["none"]/tot*100)
    x=np.arange(len(levels))
    ax[2].bar(x,sup,color="#2a9d8f",label="SUPPORT majority")
    ax[2].bar(x,rej,bottom=sup,color="#e76f51",label="REJECT majority")
    ax[2].bar(x,non,bottom=np.array(sup)+np.array(rej),color="#cccccc",label="none (no evidence, excluded in p1/2)")
    ax[2].set_xticks(x); ax[2].set_xticklabels([f"L{l}" for l in levels])
    ax[2].set_ylabel("% of associations"); ax[2].set_title("(3) verdict composition by level @top-1000"); ax[2].legend(fontsize=9)

    fig.suptitle("believe x OncoKB biomarker — accuracy by evidence level (no-evidence cases excluded)",fontsize=14)
    fig.tight_layout(rect=[0,0,1,0.93]); fig.savefig(HERE/"figures"/"by_level_clean.png",dpi=145); plt.close(fig)
    print("level | n | none%@1000 | decided-correct%@1000")
    for l in levels:
        print(f"  {l:>3} | {n[l]:>4} | {none_pct[l][1000]:5.0f}% | {dec[l][1000]:5.0f}%")
    print("saved figures/by_level_clean.png")


if __name__=="__main__":
    main()
