"""Build the biomarker association eval set (unified framing).

From all_biomarker_flat.csv keep rows with a drug (therapeutic + resistance
levels). EVERY association is phrased uniformly as a *response* claim:

    "In {cancer}, {gene} {alteration} predicts response to {drug}."

Ground truth (`expected`):
  therapeutic (levels 1,2,3A,4) -> SUPPORT  (the drug does work)
  resistance  (levels R1,R2)    -> REJECT   (the drug does NOT work; it's a
                                             resistance marker, so the response
                                             claim is false)

Output: data/associations.json — ordered list (stable row_id = index) of
{row_id, category, level, gene, alteration, cancer_type, drug, pmids[],
 hypothesis, expected}.
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
CSV = HERE / "data" / "all_biomarker_flat.csv"
OUT = HERE / "data" / "associations.json"

THERAPEUTIC = {"1", "2", "3A", "4"}
RESISTANCE = {"R1", "R2"}


def main() -> None:
    rows = list(csv.DictReader(CSV.open()))
    out = []
    for r in rows:
        level = r["level"].strip()
        drug = r["drug"].strip()
        if not drug:
            continue
        if level in THERAPEUTIC:
            category, expected = "therapeutic", "support"
        elif level in RESISTANCE:
            category, expected = "resistance", "reject"
        else:
            continue

        gene, alt, cancer = r["gene"].strip(), r["alteration"].strip(), r["cancer_type"].strip()
        pmids = [p.strip() for p in r["pmids"].split("|") if p.strip()]
        out.append({
            "row_id": len(out),
            "category": category,
            "level": level,
            "expected": expected,
            "setting": r["setting"].strip(),
            "gene": gene,
            "alteration": alt,
            "cancer_type": cancer,
            "drug": drug,
            "pmids": pmids,
            "hypothesis": f"In {cancer}, {gene} {alt} predicts response to {drug}.",
        })

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    from collections import Counter
    print(f"{len(out)} associations -> {OUT}")
    print(f"  by category: {dict(Counter(o['category'] for o in out))}")
    print(f"  by expected: {dict(Counter(o['expected'] for o in out))}")
    print("\nsamples:")
    for o in out[:1] + [o for o in out if o["category"] == "resistance"][:1]:
        print(f"  [{o['category']}/{o['level']} -> {o['expected']}] {o['hypothesis']}")


if __name__ == "__main__":
    main()
