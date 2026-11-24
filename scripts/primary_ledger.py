"""Build the primary call schedule from frozen labels and join a scored ledger.

A scored cell carries its stable call ID, the schedule fingerprint, and p (or null).
Duplicate, absent and unexpected entries are errors. Replicate calls remain separate.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
from confirmation_sample import rules
from primary_analysis import configurations, MINICHECK, decide


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def schedule(roster, labels):
    items = {r["id"]:r for r in roster}
    if len(items)!=len(roster) or len({l["id"] for l in labels})!=len(labels):
        raise ValueError("Duplicated roster/label ID")
    docs, calls = [], []
    for lab in labels:
        r = items[lab["id"]]
        if (r["doc_id"],r["edit"],r["sent_idx"]) != (lab["doc_id"],lab["edit"],lab["sent_idx"]):
            raise ValueError(f"Label join mismatch: {r['id']}")
        if r["edit"] in ("weaken","negate"):
            continue
        edits = {k:rules.CONTROLS[k](r["source"]) for k in ("identity","negate","weaken")}
        meta = {"doc_id":r["doc_id"], "edit":r["edit"], "valid":lab["valid"],
                "has_negate":bool(edits["negate"]), "has_weaken":bool(edits["weaken"])}
        docs.append(meta)
        if lab["valid"]:
            edits["focal"] = r["edited"]
        else:
            edits.pop("weaken")
        for cfg in configurations():
            model, condition = cfg.split("/")
            premise = r["source"] if condition=="sentence" else r["abstract"]
            for variant, claim in edits.items():
                if claim is None:
                    continue
                calls.append(dict(id=f"{r['doc_id']}|{cfg}|{variant}", config=cfg, variant=variant,
                                  doc_id=r["doc_id"], premise=premise, source=r["source"], claim=claim, repeat=False))
    ids = {r["doc_id"] for r in docs}
    if len(ids)!=len(docs) or not ids:
        raise ValueError("Duplicate or empty document roster")
    repeat_ids = set(sorted(ids, key=lambda d:sha(f"P10-repeat:{d}"))[:math.ceil(.10*len(ids))])
    calls.extend([dict(c, id=c["id"]+"|repeat",repeat=True) for c in calls if c["doc_id"] in repeat_ids])
    return docs,calls


def fingerprint(calls):
    return sha(json.dumps(calls,sort_keys=True,ensure_ascii=False,separators=(",",":")))


def combine(docs,calls,scores):
    expected = {c["id"]:c for c in calls}
    fp = fingerprint(calls)
    result = {}
    for s in scores:
        id_ = s["id"]
        if id_ not in expected or id_ in result or s["schedule_sha256"] != fp:
            raise ValueError(f"Unknown, duplicated or stale score {id_}")
        p = s["p"]
        if p is not None and (type(p) not in (float,int) or not 0<=p<=1):
            raise ValueError(f"Invalid probability {id_}")
        result[id_] = p
    if result.keys()!=expected.keys():
        raise ValueError("Missing cells must be recorded explicitly")
    table = {d["doc_id"]:{**d,"scores":defaultdict(dict)} for d in docs}
    stability = defaultdict(lambda:dict(planned=0,complete=0,agree=0))
    for c in calls:
        p = result[c["id"]]
        if not c["repeat"]:
            table[c["doc_id"]]["scores"][c["config"]][c["variant"]] = p
        else:
            first = result[c["id"].removesuffix("|repeat")]
            st = stability[c["config"]]
            st["planned"]+=1
            if p is not None and first is not None:
                above = (lambda x:x>.5) if c["config"].split("/")[0] in MINICHECK else (lambda x:x>=.5)
                st["complete"]+=1
                st["agree"]+=int(above(first)==above(p))
    return dict(decide(list(table.values())), repeat_counts=stability)


def lines(file):
    return [json.loads(l) for l in file.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ("roster","labels","output"):
        ap.add_argument(key,type=Path)
    ap.add_argument("--labels-sha256",required=True)
    ap.add_argument("--roster-sha256",required=True)
    ap.add_argument("--scores",type=Path,help="If supplied, emit decisions instead of a schedule")
    a=ap.parse_args()
    for p,h in ((a.labels,a.labels_sha256),(a.roster,a.roster_sha256)):
        if hashlib.sha256(p.read_bytes()).hexdigest()!=h:
            raise ValueError(f"Input digest mismatch: {p}")
    docs,calls=schedule(lines(a.roster),lines(a.labels))
    output = (json.dumps(combine(docs,calls,lines(a.scores)),indent=2) if a.scores else
              "\n".join(json.dumps(r,ensure_ascii=False) for r in calls))
    with a.output.open("x",encoding="utf-8",newline="\n") as f:
        f.write(output+"\n")
    print("schedule_sha256",fingerprint(calls),"primary_documents",len(docs),"requests",len(calls))
