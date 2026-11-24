"""Compare the immutable pilot replay with the upstream MiniCheck public scoring API."""
import argparse
import hashlib
import json
import os
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"

from huggingface_hub import snapshot_download
from minicheck.minicheck import MiniCheck
from minicheck_format_check import MODELS
from pilot_score import build_pairs

ROOT = Path(__file__).resolve().parents[1]


def key(row):
    return row["doc_id"], row["edit"], row["premise_cond"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    items = [json.loads(line) for line in (ROOT / "runs/pilot_v1/items.jsonl").read_text().splitlines()]
    assert len(items) == len({row["doc_id"] for row in items}) == 300
    pairs = build_pairs(items)
    selected = []
    for premise in ("sentence", "abstract"):
        candidates = [row for row in pairs if row["premise_cond"] == premise]
        candidates.sort(key=lambda row: hashlib.sha256(f"P10-package-pilot:{key(row)}".encode()).digest())
        selected.extend(candidates[:50])
    original = ROOT / "runs/minicheck_format_v1/scores.jsonl"
    refs = {(r["verifier"], key(r)): r["p"] for r in map(json.loads, original.read_text().splitlines())}
    result = {"phase": "pilot", "sample_per_premise": 50, "models": {}}
    for tag, upstream in (("minicheck_roberta_large", "roberta-large"),
                          ("minicheck_deberta_v3_large", "deberta-v3-large")):
        repo, revision, _ = MODELS[tag]
        if Path(snapshot_download(repo, revision="main", local_files_only=True)).name != revision:
            raise ValueError(f"Unexpected cached revision for {repo}")
        model = MiniCheck(model_name=upstream)
        verdicts, probs, chunks, _ = model.score([r["premise"] for r in selected], [r["claim"] for r in selected])
        rows = []
        for row, verdict, prob, chunk in zip(selected, verdicts, probs, chunks, strict=True):
            ref = refs[tag + "__official", key(row)]
            rows.append({"key": key(row), "upstream": float(prob), "replay": ref,
                         "agree": bool(verdict == (ref > .5)), "chunks": len(chunk)})
        result["models"][tag] = {"checkpoint": revision, "rows": rows,
                                 "agreement": sum(r["agree"] for r in rows) / len(rows),
                                 "max_probability_difference": max(abs(r["upstream"]-r["replay"]) for r in rows)}
        del model
    args.out.parent.mkdir(exist_ok=True, parents=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
