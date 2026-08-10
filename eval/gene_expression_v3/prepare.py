"""gene×tissue hypotheses for believe (change/differential framing).

Genes are DATA-DERIVED (rank_genes.py -> data/selected_genes.json):
  housekeeping = lowest cross-tissue tau, tissue-specific = highest tau.

Hypothesis (literature report of differential expression):
    "In human {tissue}, {gene} expression has been reported to be up- or down-regulated."

Output: data/genes.json, data/pairs.json
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
SEL = json.loads((DATA / "selected_genes.json").read_text())

TISSUES = [
    ("brain", "brain"), ("blood", "blood"), ("lung", "lung"), ("liver", "liver"),
    ("heart", "heart"), ("kidney", "kidney"), ("pancreas", "pancreas"),
    ("colon", "colon"), ("small intestine", "small intestine"),
    ("stomach", "stomach"), ("spleen", "spleen"), ("skin of body", "skin"),
    ("adipose tissue", "adipose tissue"), ("musculature", "skeletal muscle"),
    ("breast", "breast"), ("bone marrow", "bone marrow"),
    ("lymph node", "lymph node"), ("esophagus", "esophagus"),
    ("uterus", "uterus"), ("placenta", "placenta"),
]


def main():
    genes = [{"gene": g, "label": "housekeeping"} for g in SEL["housekeeping"]]
    genes += [{"gene": g, "label": "tissue_specific"} for g in SEL["sensitive"]]
    (DATA / "genes.json").write_text(json.dumps(genes, ensure_ascii=False, indent=2))

    pairs = []
    for gi, gobj in enumerate(genes):
        for ti, (gt_label, disp) in enumerate(TISSUES):
            pairs.append({
                "pair_id": f"{gi}_{ti}",
                "gene": gobj["gene"], "label": gobj["label"],
                "tissue_gt": gt_label, "tissue": disp,
                "hypothesis": f"In human {disp}, {gobj['gene']} expression has been reported to be up- or down-regulated.",
            })
    (DATA / "pairs.json").write_text(json.dumps(pairs, ensure_ascii=False, indent=2))
    print(f"genes: {len(genes)} (HK {len(SEL['housekeeping'])}, TS {len(SEL['sensitive'])})")
    print(f"tissues: {len(TISSUES)} | pairs: {len(pairs)}")
    print("sample:", pairs[0]["hypothesis"])


if __name__ == "__main__":
    main()
