"""Select top-N values per axis (frequency) and build the full cross grid of
drug × biomarker × cancer triples for the grid cross-evaluation.

A grid cell is labeled:
  positive : the (drug, biomarker, cancer) triple exists in OncoKB
             -> expected SUPPORT (therapeutic) / REJECT (resistance)
  negative : not in OncoKB -> believe should NOT confirm (expect non-support)

Output: data/grid.json = {n, axes:{drugs,biomarkers,cancers},
                          cells:[{drug,biomarker,cancer,label,expected,...}]}
"""

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
T = json.loads((HERE / "data" / "triples.json").read_text())
OUT = HERE / "data" / "grid.json"
_ap = argparse.ArgumentParser()
_ap.add_argument("--n", type=int, default=25)
N = _ap.parse_args().n

bc = Counter(o["biomarker"] for o in T)
dc = Counter(o["drug"] for o in T)
cc = Counter(o["cancer_type"] for o in T)

drugs = [d for d, _ in dc.most_common(N)]
biomarkers = [b for b, _ in bc.most_common(N)]
cancers = [c for c, _ in cc.most_common(N)]

# real triples lookup -> (category, expected)
real = {(o["drug"], o["biomarker"], o["cancer_type"]): o for o in T}

cells = []
pos = 0
for d in drugs:
    for b in biomarkers:
        for c in cancers:
            key = (d, b, c)
            o = real.get(key)
            if o:
                label, expected, cat = "positive", o["expected"], o["category"]
                pos += 1
            else:
                label, expected, cat = "negative", "not_support", None
            cells.append({"drug": d, "biomarker": b, "cancer_type": c,
                          "label": label, "expected": expected, "category": cat})

OUT.write_text(json.dumps(
    {"n": N, "axes": {"drugs": drugs, "biomarkers": biomarkers, "cancers": cancers},
     "cells": cells}, ensure_ascii=False, indent=2))

print(f"grid: {len(drugs)}×{len(biomarkers)}×{len(cancers)} = {len(cells)} cells")
print(f"positives (real OncoKB triples): {pos}  ({pos/len(cells)*100:.1f}%)")
print(f"  therapeutic: {sum(1 for x in cells if x['category']=='therapeutic')}, "
      f"resistance: {sum(1 for x in cells if x['category']=='resistance')}")
print(f"\nselected drugs:      {drugs}")
print(f"selected cancers:    {cancers}")
print(f"selected biomarkers: {biomarkers}")
print(f"\nsample positives:")
for x in [c for c in cells if c["label"] == "positive"][:8]:
    print(f"  [{x['category']}] {x['biomarker']} + {x['drug']} + {x['cancer_type']}")
