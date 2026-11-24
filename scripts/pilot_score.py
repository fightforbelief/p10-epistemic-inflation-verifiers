"""P10 pilot: do grounding verifiers certify epistemically inflated claims?

Run on hanqing-win with an existing venv that already has torch + transformers
(no installs).  Downloads: SciFact release tarball (~3 MB) and the HF verifier
checkpoints listed in VERIFIERS.  Nothing here is a confirmatory result.

    $py scripts/pilot_score.py --n 300 --out runs/pilot_v0
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import perturb as P  # noqa: E402

SCIFACT_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"

# (name, hf_id, how to read P(supported))
VERIFIERS = [
    ("nli_deberta_v3_large", "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli", "label:entailment"),
    ("nli_deberta_v3_base", "cross-encoder/nli-deberta-v3-base", "label:entailment"),
    ("minicheck_roberta_large", "lytang/MiniCheck-RoBERTa-Large", "index:1"),
    ("minicheck_deberta_v3_large", "lytang/MiniCheck-DeBERTa-v3-Large", "index:1"),
]
SEED = 20261119


def load_corpus(cache: Path) -> tuple[list[dict], str]:
    cache.mkdir(parents=True, exist_ok=True)
    tgz = cache / "scifact_data.tar.gz"
    if not tgz.exists():
        urllib.request.urlretrieve(SCIFACT_URL, tgz)
    sha = hashlib.sha256(tgz.read_bytes()).hexdigest()
    with tarfile.open(tgz) as tf:
        member = next(m for m in tf.getmembers() if m.name.endswith("corpus.jsonl"))
        text = tf.extractfile(member).read().decode("utf-8")
    return [json.loads(l) for l in io.StringIO(text) if l.strip()], sha


def select(corpus: list[dict], n: int) -> list[dict]:
    """Deterministic, prediction-independent selection: rank eligible sentences by SHA-256."""
    pool = []
    for doc in corpus:
        sents = doc["abstract"]
        for i, s in enumerate(sents):
            s = s.strip()
            if not (8 <= len(s.split()) <= 60) or P.n_inflations(s) == 0:
                continue
            key = hashlib.sha256(f"{SEED}:{doc['doc_id']}:{i}".encode()).hexdigest()
            pool.append((key, {"doc_id": doc["doc_id"], "sent_idx": i, "sentence": s,
                               "abstract": " ".join(x.strip() for x in sents)}))
    pool.sort(key=lambda t: t[0])
    # at most one sentence per abstract, so the bootstrap unit is also the document
    seen, out = set(), []
    for _, row in pool:
        if row["doc_id"] in seen:
            continue
        seen.add(row["doc_id"])
        out.append(row)
        if len(out) == n:
            break
    return out


def build_pairs(items: list[dict]) -> list[dict]:
    pairs = []
    for it in items:
        for edit, claim in P.variants(it["sentence"]).items():
            for cond in ("sentence", "abstract"):
                pairs.append({"doc_id": it["doc_id"], "edit": edit, "premise_cond": cond,
                              "premise": it[cond], "claim": claim,
                              "expected_supported": P.EXPECTED_SUPPORTED[edit]})
    return pairs


def score(pairs: list[dict], hf_id: str, rule: str, bs: int = 32) -> tuple[np.ndarray, dict]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(hf_id)
    model = AutoModelForSequenceClassification.from_pretrained(hf_id).to(dev).eval()
    if dev == "cuda":
        model.half()
    id2label = {int(k): v for k, v in model.config.id2label.items()}
    if rule.startswith("label:"):
        want = rule.split(":", 1)[1]
        idx = next(i for i, l in id2label.items() if l.lower().startswith(want))
    else:
        idx = int(rule.split(":", 1)[1])
    probs = []
    with torch.no_grad():
        for b in range(0, len(pairs), bs):
            chunk = pairs[b:b + bs]
            enc = tok([p["premise"] for p in chunk], [p["claim"] for p in chunk], truncation="only_first",
                      max_length=512, padding=True, return_tensors="pt").to(dev)
            logits = model(**enc).logits.float()
            probs.append(torch.softmax(logits, -1)[:, idx].cpu().numpy())
    meta = {"hf_id": hf_id, "id2label": id2label, "support_index": idx, "rule": rule,
            "revision": getattr(model.config, "_commit_hash", None), "device": dev}
    del model
    return np.concatenate(probs), meta


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    """P(score_pos > score_neg) with ties counted 1/2 (Mann-Whitney)."""
    allv = np.concatenate([pos, neg])
    ranks = allv.argsort().argsort().astype(float) + 1
    # average ranks for ties
    _, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=ranks)
    ranks = (sums / cnt)[inv]
    rp = ranks[: len(pos)].sum()
    return float((rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def summarise(rows: list[dict], verifier: str, n_boot: int = 1000) -> list[dict]:
    rng = np.random.default_rng(SEED)
    out = []
    for cond in ("sentence", "abstract"):
        sub = [r for r in rows if r["premise_cond"] == cond]
        ident = {r["doc_id"]: r["p"] for r in sub if r["edit"] == "identity"}
        for edit in [*P.CONTROLS, *P.INFLATIONS]:
            er = [r for r in sub if r["edit"] == edit]
            if not er:
                continue
            p = np.array([r["p"] for r in er])
            rec = {"verifier": verifier, "premise_cond": cond, "edit": edit, "n": len(er),
                   "expected_supported": P.EXPECTED_SUPPORTED[edit],
                   "mean_p": float(p.mean()), "rate_supported@0.5": float((p >= 0.5).mean())}
            if edit != "identity":
                ids = [r["doc_id"] for r in er]
                pi = np.array([ident[d] for d in ids])
                diff = (pi >= 0.5).astype(float) - (p >= 0.5).astype(float)  # drop in support rate
                boots = [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n_boot)]
                rec.update({"support_rate_drop_vs_identity": float(diff.mean()),
                            "drop_ci95": [float(np.quantile(boots, .025)), float(np.quantile(boots, .975))],
                            "auroc_identity_vs_edit": auroc(pi, p)})
            out.append(rec)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "pilot_v0")
    ap.add_argument("--cache", type=Path, default=ROOT / "data")
    ap.add_argument("--verifiers", nargs="*", default=[v[0] for v in VERIFIERS])
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    corpus, sha = load_corpus(a.cache)
    items = select(corpus, a.n)
    pairs = build_pairs(items)
    (a.out / "items.jsonl").write_text("\n".join(json.dumps(i) for i in items), encoding="utf-8")
    # audit sheet: every edit of the first 40 items, for human validity checks
    audit = [{"doc_id": i["doc_id"], "source": i["sentence"], **P.variants(i["sentence"])} for i in items[:40]]
    (a.out / "edit_audit_sheet.jsonl").write_text("\n".join(json.dumps(x) for x in audit), encoding="utf-8")

    manifest = {"scifact_sha256": sha, "seed": SEED, "n_items": len(items), "n_pairs": len(pairs),
                "corpus_docs": len(corpus), "verifiers": {}, "label": "PILOT_ONLY_NOT_CONFIRMATORY"}
    all_rows, summary = [], []
    for name, hf_id, rule in VERIFIERS:
        if name not in a.verifiers:
            continue
        ts = time.time()
        probs, meta = score(pairs, hf_id, rule)
        meta["seconds"] = round(time.time() - ts, 2)
        manifest["verifiers"][name] = meta
        rows = [{**{k: p[k] for k in ("doc_id", "edit", "premise_cond", "expected_supported")},
                 "verifier": name, "p": float(x)} for p, x in zip(pairs, probs)]
        all_rows += rows
        summary += summarise(rows, name)
        print(f"{name}: {len(rows)} pairs in {meta['seconds']}s", flush=True)

    (a.out / "scores.jsonl").write_text("\n".join(json.dumps(r) for r in all_rows), encoding="utf-8")
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    manifest["total_seconds"] = round(time.time() - t0, 2)
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (a.out / "run_complete.json").write_text(json.dumps({"ok": True}), encoding="utf-8")


if __name__ == "__main__":
    main()
