"""Download the PubMedQA `pqa_labeled` split for evaluating believe.

Source: https://huggingface.co/datasets/qiaojin/PubMedQA (config `pqa_labeled`,
the 1,000 expert-annotated QA instances with yes/no/maybe final decisions).
"""

import json
import os
from pathlib import Path

# Redirect HF cache to a writable, project-local dir (the default ~/.cache is
# root-owned in this environment).
CACHE_DIR = Path(__file__).parent / ".hf_cache"
os.environ.setdefault("HF_HOME", str(CACHE_DIR))

from datasets import load_dataset

OUT_DIR = Path(__file__).parent / "data"
OUT_JSON = OUT_DIR / "pqa_labeled.json"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # pqa_labeled only ships a `train` split (1,000 instances).
    ds = load_dataset(
        "qiaojin/PubMedQA", "pqa_labeled", split="train", cache_dir=str(CACHE_DIR)
    )

    records = []
    for row in ds:
        ctx = dict(row["context"])
        # HF quirk: `reasoning_required_pred` / `reasoning_free_pred` are typed as
        # Sequence(string), so the single label "yes" comes back char-split as
        # ['y','e','s']. Rejoin into the intended yes/no/maybe string.
        for key in ("reasoning_required_pred", "reasoning_free_pred"):
            val = ctx.get(key)
            if isinstance(val, list):
                ctx[key] = "".join(val)

        records.append(
            {
                "pubid": row["pubid"],
                "question": row["question"],
                "context": ctx,                     # dict: contexts/labels/meshes/...
                "long_answer": row["long_answer"],
                "final_decision": row["final_decision"],  # yes / no / maybe
            }
        )

    OUT_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=2))

    dist: dict[str, int] = {}
    for r in records:
        dist[r["final_decision"]] = dist.get(r["final_decision"], 0) + 1

    print(f"saved {len(records)} instances -> {OUT_JSON}")
    print("final_decision distribution:", dist)


if __name__ == "__main__":
    main()
