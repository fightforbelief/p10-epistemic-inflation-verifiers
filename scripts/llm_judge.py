"""P10 LLM-judge control (Gate 0 condition 3).

Scores the exact pilot_v1 pairs with an open-weight instruct LLM used as a grounding
judge.  P(supported) = softmax over the next-token logits of " Yes" vs " No" after the
chat template, so the output is a continuous score comparable to the cross-encoders.

Two prompts:
  generic  - the usual grounding question ("is the claim supported by the evidence?"),
             i.e. how an LLM judge is deployed in RAG evaluation by default;
  strength - same, but explicitly says that a claim stated with more certainty, causal
             force or generality than the evidence warrants is NOT supported.
generic tells us the default behaviour; strength tells us whether the capability exists.

    .\\.venv\\Scripts\\python.exe scripts\\llm_judge.py --out runs\\judge_v1
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

JUDGES = {
    # name: (hf_id, pinned revision or None)
    "qwen3_4b_instruct_2507": ("Qwen/Qwen3-4B-Instruct-2507", None),
}

SYSTEM = "You are a careful fact-checking assistant. Answer with a single word: Yes or No."

PROMPTS = {
    "generic": (
        "Evidence:\n{premise}\n\nClaim:\n{claim}\n\n"
        "Is the claim supported by the evidence? Answer Yes or No."
    ),
    "strength": (
        "Evidence:\n{premise}\n\nClaim:\n{claim}\n\n"
        "Is the claim supported by the evidence? A claim counts as supported only if the "
        "evidence warrants it as stated, including its degree of certainty, whether it asserts "
        "causation or only association, and its scope (population, setting, quantifier). "
        "A claim stated more strongly or more generally than the evidence warrants is NOT "
        "supported. A claim stated more cautiously than the evidence is still supported. "
        "Answer Yes or No."
    ),
}


def build_messages(prompt: str, premise: str, claim: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": PROMPTS[prompt].format(premise=premise, claim=claim)}]


def yes_prob(logit_yes: float, logit_no: float) -> float:
    """Two-way softmax, numerically stable."""
    m = max(logit_yes, logit_no)
    ey, en = math.exp(logit_yes - m), math.exp(logit_no - m)
    return ey / (ey + en)


def answer_token_ids(tok) -> tuple[list[int], list[int]]:
    """All single-token spellings of Yes / No the model might emit first."""
    ids_yes, ids_no = set(), set()
    for w, bucket in (("Yes", ids_yes), ("No", ids_no)):
        for s in (w, " " + w, w.lower(), " " + w.lower()):
            t = tok.encode(s, add_special_tokens=False)
            if len(t) == 1:
                bucket.add(t[0])
    if not ids_yes or not ids_no:
        raise RuntimeError("tokenizer has no single-token Yes/No")
    return sorted(ids_yes), sorted(ids_no)


def judge(pairs: list[dict], hf_id: str, revision: str | None, prompt: str, bs: int = 8):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(hf_id, revision=revision)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(hf_id, revision=revision, dtype=torch.bfloat16).to("cuda").eval()
    ys, ns = answer_token_ids(tok)
    texts = [tok.apply_chat_template(build_messages(prompt, p["premise"], p["claim"]),
                                     tokenize=False, add_generation_prompt=True) for p in pairs]
    # sort by length for efficient batching, then restore order
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    out = [0.0] * len(texts)
    argmax_other = 0
    with torch.no_grad():
        for b in range(0, len(order), bs):
            idx = order[b:b + bs]
            enc = tok([texts[i] for i in idx], return_tensors="pt", padding=True).to("cuda")
            last = model(**enc).logits[:, -1, :].float()
            ly = torch.logsumexp(last[:, ys], -1)
            ln = torch.logsumexp(last[:, ns], -1)
            top = last.argmax(-1)
            argmax_other += int(sum(int(t) not in ys and int(t) not in ns for t in top))
            for j, i in enumerate(idx):
                out[i] = yes_prob(float(ly[j]), float(ln[j]))
    meta = {"hf_id": hf_id, "revision": revision or getattr(model.config, "_commit_hash", None),
            "prompt": prompt, "prompt_text": PROMPTS[prompt], "system": SYSTEM,
            "yes_ids": ys, "no_ids": ns, "n_argmax_not_yes_no": argmax_other,
            "dtype": "bfloat16", "max_len_tokens": None}
    del model
    torch.cuda.empty_cache()
    return out, meta


def main() -> None:
    import pilot_score as PS

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "judge_v1")
    ap.add_argument("--cache", type=Path, default=ROOT / "data")
    ap.add_argument("--judges", nargs="*", default=list(JUDGES))
    ap.add_argument("--prompts", nargs="*", default=list(PROMPTS))
    ap.add_argument("--limit", type=int, default=0, help="smoke test: score only the first k pairs")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    corpus, sha = PS.load_corpus(a.cache)
    pairs = PS.build_pairs(PS.select(corpus, a.n))
    if a.limit:
        pairs = pairs[: a.limit]
    manifest = {"scifact_sha256": sha, "seed": PS.SEED, "n_pairs": len(pairs), "judges": {},
                "label": "PILOT_ONLY_NOT_CONFIRMATORY", "same_pairs_as": "runs/pilot_v1"}
    all_rows, summary = [], []
    for name in a.judges:
        hf_id, rev = JUDGES[name]
        for prompt in a.prompts:
            ts = time.time()
            probs, meta = judge(pairs, hf_id, rev, prompt)
            meta["seconds"] = round(time.time() - ts, 2)
            key = f"{name}__{prompt}"
            manifest["judges"][key] = meta
            rows = [{**{k: p[k] for k in ("doc_id", "edit", "premise_cond", "expected_supported")},
                     "verifier": key, "p": float(x)} for p, x in zip(pairs, probs)]
            all_rows += rows
            if not a.limit:
                summary += PS.summarise(rows, key)
            print(f"{key}: {len(rows)} pairs in {meta['seconds']}s, "
                  f"argmax not Yes/No: {meta['n_argmax_not_yes_no']}", flush=True)

    (a.out / "scores.jsonl").write_text("\n".join(json.dumps(r) for r in all_rows), encoding="utf-8")
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    manifest["total_seconds"] = round(time.time() - t0, 2)
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (a.out / "run_complete.json").write_text(json.dumps({"ok": True}), encoding="utf-8")


if __name__ == "__main__":
    main()
