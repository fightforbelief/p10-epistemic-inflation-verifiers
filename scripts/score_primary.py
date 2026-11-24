"""Run one primary configuration on an approved, fingerprinted post-label schedule.

Persist each result in a single-writer SQLite checkpoint. An interruption can
only repeat the last uncommitted request. Exported JSONL contains no source text.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
from filelock import FileLock

from primary_ledger import fingerprint, lines
from primary_analysis import configurations, MINICHECK


def scorer(config):
    name, condition = config.split("/")
    if name not in MINICHECK:
        from api_judge import ask, load_keys, JUDGES, PROVIDERS
        provider, model = JUDGES[{"deepseek":"deepseek_v4_pro","qwen":"qwen3_7_max"}[name]]
        key = load_keys()[PROVIDERS[provider]["key"]]
        def api(c):
            try:
                r = ask(provider,model,key,condition,c["premise"],c["claim"])
            except (RuntimeError, OSError, ValueError) as exc:
                return {"p":None,"error_type":type(exc).__name__}
            return dict(r,p=r["p"] if math.isfinite(r["p"]) else None)
        return api
    os.environ["HF_HUB_OFFLINE"]="1"
    from huggingface_hub import snapshot_download
    from minicheck.minicheck import MiniCheck
    from minicheck_format_check import MODELS
    repo,rev,maxlen = MODELS[name]
    if Path(snapshot_download(repo,local_files_only=True,revision="main")).name!=rev:
        raise ValueError("Checkpoint revision differs from freeze")
    checker = MiniCheck(model_name={"minicheck_roberta_large":"roberta-large",
                                    "minicheck_deberta_v3_large":"deberta-v3-large"}[name])
    # The package's returned chunk strings use a literal RoBERTa separator.
    # Observe its actual text inputs before tokenization for both architectures.
    internal = checker.model
    original_tokenize = internal.batch_tokenize
    chunks = []
    def observe(docs, claims):
        chunks.extend(docs)
        return original_tokenize(docs,claims)
    internal.batch_tokenize = observe
    def local(c):
        chunks.clear()
        _, ps, _, chunk_probs = checker.score([c["premise"]],[c["claim"]])
        tok = internal.tokenizer
        cut = []
        for chunk in chunks:
            text=tok.eos_token.join((chunk,c["claim"]))
            cut.append(len(tok(text, truncation=False)["input_ids"])>maxlen)
        # Right truncation can remove part of the claim; the output no longer
        # corresponds to the requested contrast. Flag any such case for review.
        return dict(p=None if any(cut) else float(ps[0]), raw_p=float(ps[0]),checkpoint=rev,
                    chunks=len(chunks), truncated_chunks=sum(cut),
                    chunk_probabilities=[float(p) for p in chunk_probs[0]])
    return local


def run(calls, cfg, digest, out, fn):
    out.mkdir(exist_ok=True,parents=True)
    stem=cfg.replace("/","__")
    with FileLock(out/(stem+".lock"),timeout=0), closing(sqlite3.connect(out/(stem+".sqlite"))) as db:
        db.execute("create table if not exists result (id text primary key, payload text not null)")
        db.execute("create table if not exists provenance (schedule text primary key)")
        stored=db.execute("select schedule from provenance").fetchall()
        if stored and stored != [(digest,)]:
            raise ValueError("Checkpoint belongs to a different schedule")
        db.execute("insert or ignore into provenance values (?)",(digest,))
        db.commit()
        done={r[0] for r in db.execute("select id from result")}
        for c in calls:
            if c["config"]!=cfg or c["id"] in done:
                continue
            result=dict(fn(c),id=c["id"],schedule_sha256=digest,utc=datetime.now(timezone.utc).isoformat())
            raw=json.dumps(result,allow_nan=False,ensure_ascii=False)
            db.execute("insert into result values (?,?)",(c["id"],raw))
            db.commit()
        target=out/(stem+".jsonl")
        temp=target.with_suffix(".tmp")
        with temp.open("w",encoding="utf-8",newline="\n") as f:
            for (raw,) in db.execute("select payload from result order by rowid"):
                f.write(raw+"\n")
        temp.replace(target)


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("schedule",type=Path)
    ap.add_argument("out",type=Path)
    ap.add_argument("--config",choices=configurations(),required=True)
    ap.add_argument("--schedule-sha256",required=True)
    a=ap.parse_args()
    requests=lines(a.schedule)
    digest=fingerprint(requests)
    if digest!=a.schedule_sha256 or len({c["id"] for c in requests})!=len(requests):
        raise ValueError("Invalid or unexpected call schedule")
    run(requests,a.config,digest,a.out,scorer(a.config))
