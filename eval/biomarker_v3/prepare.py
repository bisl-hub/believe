"""biomarker_v3: same OncoKB associations as v1/v2, unified 'predicts response to'
framing, but to be run with 10,000 articles per hypothesis (n=10000).

therapeutic(1,2,3A,4) -> expect SUPPORT ; resistance(R1,R2) -> expect REJECT.
Output: data/associations.json
"""
import csv, json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
CSV = HERE / "data" / "all_biomarker_flat.csv"
OUT = HERE / "data" / "associations.json"
THERAPEUTIC = {"1", "2", "3A", "4"}
RESISTANCE = {"R1", "R2"}


def main():
    rows = list(csv.DictReader(CSV.open()))
    out = []
    for r in rows:
        level, drug = r["level"].strip(), r["drug"].strip()
        if not drug:
            continue
        if level in THERAPEUTIC: category, expected = "therapeutic", "support"
        elif level in RESISTANCE: category, expected = "resistance", "reject"
        else: continue
        gene, alt, cancer = r["gene"].strip(), r["alteration"].strip(), r["cancer_type"].strip()
        out.append({
            "row_id": len(out), "category": category, "level": level, "expected": expected,
            "gene": gene, "alteration": alt, "cancer_type": cancer, "drug": drug,
            "biomarker": f"{gene} {alt}",
            "pmids": [p.strip() for p in r["pmids"].split("|") if p.strip()],
            "hypothesis": f"In {cancer}, {gene} {alt} predicts response to {drug}.",
        })
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"{len(out)} associations -> {OUT}")
    print("category:", dict(Counter(o["category"] for o in out)))
    print("sample:", out[0]["hypothesis"])


if __name__ == "__main__":
    main()
