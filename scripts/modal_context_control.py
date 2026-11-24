"""Score the planned matched-filler condition or summarize its three paired contexts.

Run at the Windows project root with the frozen private inputs in audit/confirmatory.
The score step uses the same pinned encoders and checkpoint writer as the primary run.
The report step makes no model calls. Only its aggregate JSON is intended for release.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from confirmation_sample import CORPUS
from primary_analysis import MINICHECK, cp_lower
from primary_ledger import fingerprint, lines
from secondary_contrasts import matched_filler

BASE = Path("audit/confirmatory")
OUT = BASE / "modal_context_control"
CONTEXTS = ("sentence", "filler", "abstract")
ROSTER = "a1cc701bbe406099ae464a2a8de8d0e5acb586e5283f15183b9180452977343d"
LABELS = "d274c5c83f174a2269f9272d85ba14b50aebb282bbd5586ea8d9b3e096a1490c"
PRIMARY = "6ec6a1d8f733560d8cb9cb5698f155771a75051473aab8835f01b99c4b6fb338"


def checked(path, expected):
    if sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"Unexpected file digest for {path}")
    return path


def build():
    from pilot_score import load_corpus

    checked(Path("data/scifact_data.tar.gz"), CORPUS)
    corpus, _ = load_corpus(Path("data"))
    docs = {r["doc_id"]: [s.strip() for s in r["abstract"]] for r in corpus}
    labels = lines(checked(BASE / "labels.jsonl", LABELS))
    roster = lines(checked(BASE / "roster.jsonl", ROSTER))
    hashes = json.loads(Path("docs/sampling_manifest.json").read_text())["files"]
    pilots = set()
    for v in ("v0", "v1"):
        key = f"runs/pilot_{v}/items.jsonl"
        pilots.update(r["doc_id"] for r in lines(checked(Path(key), hashes[key])))
    reserved = {r["doc_id"] for r in roster}
    donors = {k:v for k,v in docs.items() if k not in pilots and k not in reserved}
    assert len(docs) == 5183 and len(pilots) == 339 and len(reserved) == 910 and len(donors) == 3934
    eligible = {r["id"] for r in labels if r.get("valid") and r["edit"] == "modal_strengthen"}
    rows = []
    for r in roster:
        if r["id"] not in eligible:
            continue
        doc = r["doc_id"]
        sentences = docs[doc]
        assert r["abstract"] == " ".join(sentences)
        filler, used = matched_filler(r["source"], sentences, r["sent_idx"], donors, doc)
        offset = sum(len(s.split()) for s in sentences[:r["sent_idx"]])
        words = filler.split()
        assert words[offset:offset+len(r["source"].split())] == r["source"].split()
        assert len(words) == len(r["abstract"].split()) and set(used) <= donors.keys()
        rows.append(dict(doc=doc, claim=r["edited"], sentence=r["source"], abstract=r["abstract"],
                         filler=filler, donors=used, source_word_offset=offset))
    assert len({r["doc"] for r in rows}) == len(rows) == 200
    return rows


def calls_for(rows, model):
    cfg = model + "/filler"
    return [dict(id=f"{r['doc']}|{cfg}|focal", config=cfg, premise=r["filler"], claim=r["claim"],
                 donor_ids=r["donors"], source_word_offset=r["source_word_offset"]) for r in rows]


def score(rows):
    from score_primary import run, scorer
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer
    from minicheck_format_check import MODELS

    OUT.mkdir(parents=True, exist_ok=True)
    for model in MINICHECK:
        calls = calls_for(rows, model)
        repo, revision, _ = MODELS[model]
        tokenizer = AutoTokenizer.from_pretrained(snapshot_download(repo, revision=revision, local_files_only=True))
        diagnostics = {}
        for row in rows:
            lengths = {c:len(tokenizer(tokenizer.eos_token.join([row[c],row["claim"]]), truncation=False)["input_ids"]) for c in CONTEXTS}
            diagnostics[str(row["doc"])] = dict(tokens=lengths, donor_ids=row["donors"], offset=row["source_word_offset"])
        (OUT / (model + "_inputs.json")).write_text(json.dumps(diagnostics),encoding="utf-8")
        cfg = model + "/filler"
        run(calls, cfg, fingerprint(calls), OUT, scorer(cfg))


def compare(left, right, threshold=.5):
    """Paired left-minus-right verdicts and descriptive 95% document-bootstrap limits."""
    n = len(left)
    if n == 0:
        return {"n":0}
    a, b = np.asarray(left) > threshold, np.asarray(right) > threshold
    g, l = int(sum(a & ~b)), int(sum(~a & b))
    if max(g,l,n-g-l) == n:
        lo = cp_lower(g,n,.0125) + cp_lower(n-l,n,.0125) - 1
        hi = 1 - cp_lower(n-g,n,.0125) - cp_lower(l,n,.0125)
    else:
        counts = np.array([g,l,n-g-l])
        draws = np.random.default_rng(20261124).multinomial(n,counts/n,size=10000)
        lo,hi = np.quantile((draws[:,0]-draws[:,1])/n,[.025,.975])
    return dict(n=n, left=int(a.sum()), right=int(b.sum()), gains=g, losses=l,
                difference=(g-l)/n, interval95=[float(lo),float(hi)])


def report(rows):
    primary = {s["id"]:s for s in lines(checked(BASE / "scores.jsonl", PRIMARY))}
    out = {}
    residual_by_document = {}
    for model in MINICHECK:
        calls = calls_for(rows, model)
        added = lines(OUT / (model + "__filler.jsonl"))
        assert len(added) == 200 and {r["id"] for r in added} == {c["id"] for c in calls}
        schedule_hash = fingerprint(calls)
        assert all(s["schedule_sha256"] == schedule_hash for s in added)
        filler = {s["id"]:s for s in added}
        d = json.loads((OUT / (model + "_inputs.json")).read_text())
        residual_by_document[model] = {}
        matched = []
        clipped = Counter()
        for r in rows:
            row = {c:(filler if c=="filler" else primary)[f"{r['doc']}|{model}/{c}|focal"] for c in CONTEXTS}
            clipped.update(c for c in CONTEXTS if row[c]["p"] is None)
            if all(s["p"] is not None for s in row.values()):
                matched.append(row)
                residual_by_document[model][r["doc"]] = int(row["abstract"]["p"] > .5) - int(row["filler"]["p"] > .5)
        single = [r for r in matched if all(r[c]["chunks"]==1 for c in CONTEXTS)]
        effects = {}
        for name, group in (("complete",matched),("all_one_chunk",single)):
            effects[name] = {f"{a}_minus_{b}":compare([r[a]["p"] for r in group],[r[b]["p"] for r in group])
                             for a,b in (("abstract","sentence"),("filler","sentence"),("abstract","filler"))}
        delta = [v["tokens"]["filler"]-v["tokens"]["abstract"] for v in d.values()]
        sweep = {str(round(t/10,1)):compare([r["abstract"]["p"] for r in matched],[r["filler"]["p"] for r in matched],t/10)
                 for t in range(1,10)}
        out[model] = dict(schedule_sha256=schedule_hash, attempted=200, missing_by_context=dict(clipped),
                          comparisons=effects, threshold_sweep=sweep, filler_minus_real_tokens=dict(
                              median=float(np.median(delta)),min=min(delta),max=max(delta),median_absolute=float(np.median(np.abs(delta)))),
                          patterns=dict(Counter("".join(str(int(r[c]["p"]>.5)) for c in CONTEXTS) for r in matched)))
    # Keep the two encoders and both presentations paired within each document.
    roberta, deberta = (residual_by_document[model] for model in MINICHECK)
    ids = sorted(roberta.keys() & deberta.keys())
    values = np.array([deberta[i] - roberta[i] for i in ids])
    bins = np.arange(-2, 3)
    counts = np.array([(values == t).sum() for t in bins])
    draws = np.random.default_rng(20261124).multinomial(len(ids), counts/len(ids), size=10000)
    interval = np.quantile(draws @ bins / len(ids), [.025,.975])
    interaction = dict(n=len(ids), difference=float(values.mean()), interval95=interval.tolist(),
                       counts_at_minus2_through_plus2=counts.tolist(), status="post_hoc_descriptive")
    return dict(residual_deberta_minus_roberta=interaction, primary_scores_sha256=PRIMARY, roster_sha256=ROSTER, labels_sha256=LABELS, donor_pool=3934,
                eligible=len(rows), unique_donors=len({i for r in rows for i in r["donors"]}),
                pattern_order=list(CONTEXTS),models=out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("operation",choices=("score","report"))
    args = ap.parse_args()
    data = build()
    if args.operation == "score":
        score(data)
    else:
        print(json.dumps(report(data),indent=2,allow_nan=False))
