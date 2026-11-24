"""Estimate reasoning-judge token usage only, on exactly 50 original pilot pairs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

from api_judge import JUDGES, PROVIDERS, _post, load_keys
from llm_judge import build_messages
from pilot_score import build_pairs

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    inp=ROOT/"runs/pilot_v1/items.jsonl"
    expected=json.loads((ROOT/"docs/sampling_manifest.json").read_text())["files"]["runs/pilot_v1/items.jsonl"]
    if hashlib.sha256(inp.read_bytes()).hexdigest()!=expected:
        raise ValueError("Unexpected pilot inputs")
    items=list(map(json.loads,inp.read_text(encoding="utf-8").splitlines()))
    pairs=[p for p in build_pairs(items) if p["premise_cond"]=="abstract"]
    pairs.sort(key=lambda p:hashlib.sha256(f"P10-cost50:{p['doc_id']}:{p['edit']}".encode()).digest())
    keys=load_keys()
    a.out.mkdir(exist_ok=True,parents=True)
    for judge,(provider,model) in JUDGES.items():
        cfg=PROVIDERS[provider]
        for prompt in ("generic","strength"):
            dest=a.out/(judge+"_"+prompt+".jsonl")
            done={r["index"] for r in map(json.loads,dest.read_text().splitlines())} if dest.exists() else set()
            def work(i):
                pair=pairs[i]
                body=dict(model=model,messages=build_messages(prompt,pair["premise"],pair["claim"]),
                          max_tokens=2048,temperature=0)
                body.update({"thinking":{"type":"enabled"}} if provider=="deepseek" else {"enable_thinking":True})
                record=dict(index=i,doc_id=pair["doc_id"],edit=pair["edit"])
                try:
                    reply=_post(cfg["base"]+"/chat/completions",keys[cfg["key"]],body,tries=2)
                    choice=reply["choices"][0]
                    answer=(choice["message"].get("content") or "").strip().lower().rstrip(".")
                    record.update(usage=reply["usage"],served_model=reply.get("model"),
                                  finish=choice.get("finish_reason"),parsed=answer in ("yes","no"))
                except (ValueError,KeyError,OSError,RuntimeError) as exc:
                    record["error"]=type(exc).__name__
                return record
            with dest.open("a",encoding="utf-8") as f,ThreadPoolExecutor(4) as pool:
                for r in pool.map(work,[i for i in range(50) if i not in done]):
                    f.write(json.dumps(r)+"\n")
                    f.flush()
            print(judge,prompt,"complete",flush=True)


if __name__=="__main__":
    main()
