"""Restore the pilot texts locally from the original SciFact archive and released index."""
import json
import hashlib
from pathlib import Path
from pilot_score import load_corpus

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    docs, sha = load_corpus(ROOT/"data")
    if sha != "11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be":
        raise ValueError("Incorrect corpus")
    abstracts = {r["doc_id"]: r["abstract"] for r in docs}
    manifest = json.loads((ROOT/"docs/sampling_manifest.json").read_text())
    for v, indices in json.loads((ROOT/"specs/pilot_document_index.json").read_text()).items():
        rows = []
        for d, idx in indices:
            ss = [s.strip() for s in abstracts[d]]
            rows.append(dict(doc_id=d,sent_idx=idx,sentence=ss[idx],abstract=" ".join(ss)))
        rel = f"runs/pilot_{v}/items.jsonl"
        expected = manifest["files"][rel]
        text = "\n".join(json.dumps(r) for r in rows)
        # Original snapshots were written by a Windows text writer.
        candidates = [s.replace("\n", newline).encode() for s in (text, text+"\n") for newline in ("\r\n","\n")]
        payload = next((b for b in candidates if hashlib.sha256(b).hexdigest()==expected),None)
        if payload is None:
            raise ValueError(f"{v}: could not recreate pinned bytes")
        file = ROOT/rel
        if file.exists():
            if file.read_bytes()!=payload:
                raise ValueError(f"{rel} already exists with different bytes")
        else:
            file.parent.mkdir(parents=True,exist_ok=True)
            file.write_bytes(payload)
