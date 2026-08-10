"""v2-unit ablation: treat biomarker (gene+mutation) as ONE unit and remove it.
New arms (A0 full and -cancer already exist and are reused in analysis):
  biomarker_removed : "In {cancer}, {drug} predicts treatment response."   (drug+cancer)
  both_removed      : "{drug} predicts treatment response."                (drug only)
Submitted to project 31 (v2 key), n=1000.  State: runs/ablation_unit_jobs.json
Usage: python ablation_unit_submit.py [--limit N] [--arm biomarker_removed|both_removed]
"""
import argparse, json
from collections import defaultdict
from pathlib import Path
import requests

HERE=Path(__file__).parent
TRIP=json.loads((HERE/"data"/"triples.json").read_text())
STATE_F=HERE/"runs"/"ablation_unit_jobs.json"
API="http://localhost:15001/api/v1"; KEY="blv_901165f3f25fd0cf893d56848bfbbdc7b9d61b1dc2bc8969"
N=1000
SP='''Classify whether the given ABSTRACT supports, contradicts, or is neutral toward the HYPOTHESIS.

OUTPUT FORMAT (JSON):
{
  "verdict": "SUPPORT" | "REJECT" | "NEUTRAL",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "rationale": "justification referencing the abstract, about 2-3 sentences"
}'''


def build():
    bm=defaultdict(list)   # (cancer,drug) -> triple_ids
    bo=defaultdict(list)   # drug -> triple_ids
    for o in TRIP:
        bm[(o["cancer_type"],o["drug"])].append(o["triple_id"])
        bo[o["drug"]].append(o["triple_id"])
    arms={"biomarker_removed":[],"both_removed":[]}
    for i,((c,d),tids) in enumerate(bm.items()):
        arms["biomarker_removed"].append({"key":f"bm-{i}","hyp":f"In {c}, {d} predicts treatment response.","triple_ids":tids})
    for i,(d,tids) in enumerate(bo.items()):
        arms["both_removed"].append({"key":f"bo-{i}","hyp":f"{d} predicts treatment response.","triple_ids":tids})
    return arms


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int); ap.add_argument("--arm")
    a=ap.parse_args()
    arms=build()
    state=json.loads(STATE_F.read_text()) if STATE_F.exists() else {}
    H={"X-Api-Key":KEY,"Content-Type":"application/json"}; sub=0
    for arm,items in arms.items():
        if a.arm and arm!=a.arm: continue
        state.setdefault(arm,{})
        for it in items:
            if it["key"] in state[arm]: continue
            if a.limit is not None and sub>=a.limit: break
            hyp=it["hyp"]
            body={"name":f"bmv2abl-{arm[:2]}-{it['key']}",
                  "query_term":json.dumps({"q":hyp,"n":N,"model_id":"Qwen__Qwen3-Embedding-0.6B"}),
                  "hypothesis":hyp,"max_articles":N,"source_type":"qwen_retriever",
                  "openai_model":"openai/gpt-oss-120b","openai_base_url":"http://143.248.74.105:11434/v1",
                  "openai_api_key":"bislaprom3#","system_prompt":SP,"llm_concurrency_limit":256,"llm_temperature":0.0}
            j=requests.post(f"{API}/jobs",headers=H,json=body,timeout=60).json()
            state[arm][it["key"]]={"job_id":j["id"],"hypothesis":hyp,"triple_ids":it["triple_ids"]}
            sub+=1
            if sub%50==0: STATE_F.write_text(json.dumps(state,ensure_ascii=False,indent=2))
        STATE_F.write_text(json.dumps(state,ensure_ascii=False,indent=2))
    print({k:len(v) for k,v in {**arms}.items()},"unique;  submitted this run:",sub,
          "; tracked:",{k:len(state.get(k,{})) for k in arms})


if __name__=="__main__":
    main()
