"""Pilot diagnostic: score the pilot_v1 pairs with MiniCheck's official input format.

Official (Liyan06/MiniCheck minicheck/inference.py, read 2026-11-24): eos_token.join([doc, claim]) as ONE
text; doc is packed into chunks of at most chunk_size tokens at sentence boundaries; score = max over chunks.
pilot_v1 used tokenizer(premise, claim) pair encoding, no chunking, max_length 512.
Difference from official here: sentence boundaries come from SciFact, not nltk.

    .\\.venv\\Scripts\\python.exe scripts\\minicheck_format_check.py --chunk_roberta 400 --chunk_deberta 400 --out runs\\minicheck_format_v1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
MODELS = {"minicheck_roberta_large": ("lytang/MiniCheck-RoBERTa-Large", "74c8919647e61ed0f71bc177d94f10930f090068", 512),
          "minicheck_deberta_v3_large": ("lytang/MiniCheck-DeBERTa-v3-Large", "2f2d01a54fa022a7ffadb76260e1ea8bc88c82bb", 2048)}


def pack(lens: list[int], size: int) -> list[list[int]]:
    """Greedy sentence packing as in MiniCheck's chunks(); returns sentence-index groups (empty groups dropped)."""
    out, cur, n = [], [], 0
    for i, k in enumerate(lens):
        if n + k > size:
            out.append(cur)
            cur, n = [i], k
        else:
            cur.append(i)
            n += k
    out.append(cur)
    return [c for c in out if c]


def main() -> None:
    import pilot_score as PS
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--chunk_roberta", type=int, required=True)
    ap.add_argument("--chunk_deberta", type=int, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    corpus, sha = PS.load_corpus(ROOT / "data")
    sents = {d["doc_id"]: [x.strip() for x in d["abstract"]] for d in corpus}
    pairs = PS.build_pairs(PS.select(corpus, 300))
    rows, summary, man = [], [], {"scifact_sha256": sha, "label": "PILOT_ONLY_NOT_CONFIRMATORY", "models": {}}
    for name, (hf, rev, maxlen) in MODELS.items():
        size = a.chunk_roberta if "roberta" in name else a.chunk_deberta
        tok = AutoTokenizer.from_pretrained(hf, revision=rev)
        model = AutoModelForSequenceClassification.from_pretrained(hf, revision=rev).to("cuda").eval().half()
        ntok = lambda s: len(tok(s, add_special_tokens=False)["input_ids"])
        texts, owner, n_chunked, pair_ids_differ = [], [], 0, 0
        for i, p in enumerate(pairs):
            ss = sents[p["doc_id"]] if p["premise_cond"] == "abstract" else [p["premise"]]
            groups = pack([ntok(s) for s in ss], size)
            n_chunked += len(groups) > 1
            for g in groups:
                texts.append(tok.eos_token.join([" ".join(ss[j] for j in g), p["claim"]]))
                owner.append(i)
            pair_ids_differ += tok(p["premise"], p["claim"])["input_ids"] != tok(tok.eos_token.join([p["premise"], p["claim"]]))["input_ids"]
        trunc = sum(len(tok(t)["input_ids"]) > maxlen for t in texts)
        pair_trunc = sum(len(tok(p["premise"], p["claim"])["input_ids"]) > 512 for p in pairs)
        best = [0.0] * len(pairs)
        with torch.no_grad():
            for b in range(0, len(texts), 16):
                enc = tok(texts[b:b + 16], max_length=maxlen, truncation=True, padding=True, return_tensors="pt").to("cuda")
                pr = torch.softmax(model(**enc).logits.float(), -1)[:, 1].cpu().tolist()
                for o, x in zip(owner[b:b + 16], pr):
                    best[o] = max(best[o], x)
        rr = [{**{k: p[k] for k in ("doc_id", "edit", "premise_cond", "expected_supported")}, "verifier": name + "__official", "p": x}
              for p, x in zip(pairs, best)]
        rows += rr
        summary += PS.summarise(rr, name + "__official")
        man["models"][name] = {"revision": rev, "chunk_size": size, "max_len": maxlen, "pairs_chunked": n_chunked, "inputs_truncated": trunc,
                               "pairs_truncated_in_pilot_format": pair_trunc, "pairs_where_token_ids_differ": pair_ids_differ, "n": len(pairs)}
        print(name, man["models"][name], flush=True)
        del model
    for f, o in (("summary.json", summary), ("manifest.json", man)):
        (a.out / f).write_text(json.dumps(o, indent=1), encoding="utf-8")
    (a.out / "scores.jsonl").write_text("\n".join(map(json.dumps, rows)), encoding="utf-8")


if __name__ == "__main__":
    main()
