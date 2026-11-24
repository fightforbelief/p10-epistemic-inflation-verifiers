"""Create the blinded P10 sampling roster from the pinned corpus. No scoring dependencies."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
import perturb_v2 as rules

CAPS = {"scope_drop": 150, "hedge_adverb_drop": 220, "causal_upgrade": 150,
        "quantifier_inflate": 60, "modal_strengthen": 330}
TARGETS = {"hedge_adverb_drop": 150, "modal_strengthen": 200}
CORPUS = "11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be"


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def draw(docs, excluded, caps=CAPS, targets=TARGETS, control_n=60):
    pools = {edit: [] for edit in caps}
    for doc in docs:
        d = doc["doc_id"]
        if d in excluded:
            continue
        sentences = [s.strip() for s in doc["abstract"]]
        for i, s in enumerate(sentences):
            if not 8 <= len(s.split()) <= 60:
                continue
            rank = digest(f"P10-CONFIRM-v1:{d}:{i}")
            for e in pools:
                edited = rules.INFLATIONS[e](s)
                if edited and edited != s:
                    pools[e].append((rank, {"doc_id": d, "sent_idx": i, "source": s, "edited": edited,
                                            "abstract": " ".join(sentences), "edit": e}))
    used, focal, core = set(excluded), [], []
    for e, cap in caps.items():
        taken = 0
        for _, r in sorted(pools[e], key=lambda pair: pair[0]):
            if r["doc_id"] in used:
                continue
            used.add(r["doc_id"])
            taken += 1
            r["order"] = taken
            r["id"] = f"{e}-{taken:03d}"
            focal.append(r)
            if taken <= targets.get(e, cap):
                core.append(r)
            if taken == cap:
                break
    controls = []
    for edit in ("weaken", "negate"):
        candidates = sorted(core, key=lambda r: digest(f"P10-control:{edit}:{r['doc_id']}"))
        take = []
        for r in candidates:
            text = rules.CONTROLS[edit](r["source"])
            if text:
                take.append(dict(r, id=f"{edit}-{len(take)+1:03d}", edit=edit, edited=text,
                                 order=len(take)+1))
                if len(take) == control_n:
                    break
        if len(take) != control_n:
            raise ValueError(f"Insufficient {edit} controls")
        controls.extend(take)
    return focal + controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    tar = ROOT / "data/scifact_data.tar.gz"
    if hashlib.sha256(tar.read_bytes()).hexdigest() != CORPUS:
        raise ValueError("Unexpected SciFact corpus")
    excluded = set()
    for version in ("v0","v1"):
        file = ROOT/f"runs/pilot_{version}/items.jsonl"
        ids = {r["doc_id"] for r in map(json.loads, file.read_text(encoding="utf-8").splitlines())}
        if len(ids) != 300:
            raise ValueError("Unexpected pilot size")
        excluded.update(ids)
    if len(excluded) != 339:
        raise ValueError("Unexpected pilot union")
    with tarfile.open(tar) as tf:
        member = next(m for m in tf.getmembers() if m.name.endswith("/corpus.jsonl"))
        docs = [json.loads(line) for line in tf.extractfile(member) if line.strip()]
    rows = draw(docs, excluded)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="\n") as out:
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("pilot exclusions", len(excluded), "records", len(rows), "sha256", hashlib.sha256(args.out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
