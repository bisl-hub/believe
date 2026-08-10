"""biomarker_v2 — classify OncoKB rows along three axes:

    drug  +  biomarker (gene+mutation, combined)  +  cancer type

Unlike v1, gene and mutation are NOT separated — the biomarker is the single
unit "{gene} {alteration}". Keeps drug-present rows (therapeutic + resistance),
since a (drug, biomarker, cancer) triple needs a drug.

Output: data/triples.json — list of
{triple_id, drug, biomarker, gene, alteration, cancer_type, level, category,
 expected, pmids}.
"""

import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
CSV = HERE / "data" / "all_biomarker_flat.csv"
OUT = HERE / "data" / "triples.json"

THERAPEUTIC = {"1", "2", "3A", "4"}
RESISTANCE = {"R1", "R2"}


def main():
    rows = list(csv.DictReader(CSV.open()))
    out = []
    for r in rows:
        level, drug = r["level"].strip(), r["drug"].strip()
        if not drug:
            continue
        if level in THERAPEUTIC:
            category, expected = "therapeutic", "support"
        elif level in RESISTANCE:
            category, expected = "resistance", "reject"
        else:
            continue
        gene, alt, cancer = r["gene"].strip(), r["alteration"].strip(), r["cancer_type"].strip()
        out.append({
            "triple_id": len(out),
            "drug": drug,
            "biomarker": f"{gene} {alt}",
            "gene": gene,
            "alteration": alt,
            "cancer_type": cancer,
            "level": level,
            "category": category,
            "expected": expected,
            "pmids": [p.strip() for p in r["pmids"].split("|") if p.strip()],
        })

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"{len(out)} triples -> {OUT}")
    print(f"  unique biomarkers: {len({o['biomarker'] for o in out})}")
    print(f"  unique drugs:      {len({o['drug'] for o in out})}")
    print(f"  unique cancers:    {len({o['cancer_type'] for o in out})}")
    print(f"  category: {dict(Counter(o['category'] for o in out))}")


if __name__ == "__main__":
    main()
