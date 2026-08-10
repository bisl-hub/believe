"""Generate ablation hypotheses for the context-contribution analysis.

Starting from data/associations.json (A0 full), build three generalized arms,
keeping the "predicts response to" framing. A specific alteration is generalized
to "alterations" rather than deleted, so the sentence stays well-formed.

  A1 -alteration : In {cancer}, {gene} alterations predict response to {drug}.
  A2 -cancer     : {gene} {alteration} predicts response to {drug}.
  A3 gene-only   : {gene} alterations predict response to {drug}.

Each arm dedups many original rows onto one hypothesis (e.g. all ABL1/CML/Imatinib
rows collapse under A1). We submit each unique hypothesis once and map results
back to every original row_id it covers.

Output: data/ablation.json = {arm: [{hyp_id, hypothesis, row_ids:[...]}]}
"""

import json
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).parent
ASSOC = HERE / "data" / "associations.json"
OUT = HERE / "data" / "ablation.json"


def hyp_text(arm, o):
    g, alt, c, d = o["gene"], o["alteration"], o["cancer_type"], o["drug"]
    if arm == "A1":   # generalize alteration, keep cancer
        return f"In {c}, {g} alterations predict response to {d}."
    if arm == "A2":   # drop cancer, keep specific alteration
        return f"{g} {alt} predicts response to {d}."
    if arm == "A3":   # generalize alteration, drop cancer
        return f"{g} alterations predict response to {d}."
    raise ValueError(arm)


def dedup_key(arm, o):
    g, alt, c, d = o["gene"], o["alteration"], o["cancer_type"], o["drug"]
    if arm == "A1":
        return (g, c, d)
    if arm == "A2":
        return (g, alt, d)
    if arm == "A3":
        return (g, d)


def main():
    assoc = json.loads(ASSOC.read_text())
    out = {}
    for arm in ("A1", "A2", "A3"):
        groups = OrderedDict()  # key -> {hypothesis, row_ids}
        for o in assoc:
            k = dedup_key(arm, o)
            if k not in groups:
                groups[k] = {"hypothesis": hyp_text(arm, o), "row_ids": []}
            groups[k]["row_ids"].append(o["row_id"])
        out[arm] = [
            {"hyp_id": f"{arm}-{i}", "hypothesis": g["hypothesis"], "row_ids": g["row_ids"]}
            for i, g in enumerate(groups.values())
        ]
        print(f"{arm}: {len(out[arm])} unique hypotheses (covers {len(assoc)} rows)")

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {OUT}")
    print("\nsamples:")
    for arm in ("A1", "A2", "A3"):
        print(f"  {arm}: {out[arm][0]['hypothesis']}  (rows={len(out[arm][0]['row_ids'])})")


if __name__ == "__main__":
    main()
