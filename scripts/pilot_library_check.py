"""End-to-end real-library check of 50 fixed, public SciFact v1 pilot edits per workflow."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path

os.environ.update(RAGAS_DO_NOT_TRACK="true", DEEPEVAL_TELEMETRY_OPT_OUT="YES", OTEL_SDK_DISABLED="true")
from api_judge import JUDGES, PROVIDERS, load_keys
from deployed_judge import CONFIGS, QUERY
from pilot_score import build_pairs

ROOT = Path(__file__).resolve().parents[1]
MODEL = JUDGES["qwen3_7_max"][1]
BASE = PROVIDERS["bailian"]["base"]
EXTRA = {"extra_body":{"enable_thinking":False}}


def native(cfg, doc, claim, key):
    if cfg == "ragas":
        from openai import AsyncOpenAI
        from ragas.llms.base import llm_factory
        from ragas.metrics.collections import Faithfulness
        async def score():
            async with AsyncOpenAI(base_url=BASE,api_key=key,max_retries=1) as client:
                model = llm_factory(MODEL,client=client,temperature=0,**EXTRA)
                return (await Faithfulness(llm=model).ascore(user_input=QUERY,response=claim,retrieved_contexts=[doc])).value
        return asyncio.run(score())
    if cfg == "deepeval":
        from deepeval.metrics import FaithfulnessMetric
        from deepeval.models.llms.local_model import LocalModel
        from deepeval.test_case import LLMTestCase
        model = LocalModel(model=MODEL,base_url=BASE,api_key=key,temperature=0,generation_kwargs=EXTRA)
        metric = FaithfulnessMetric(model=model,async_mode=False)
        metric.measure(LLMTestCase(input=QUERY,actual_output=claim,retrieval_context=[doc]))
        return metric.score
    if cfg == "trulens":
        from trulens.providers.openai import OpenAI
        model = OpenAI(model_engine=MODEL)
        return model.groundedness_measure_with_cot_reasons(source=doc,statement=claim)[0]
    if cfg == "llamaindex":
        from llama_index.llms.openai_like import OpenAILike
        from llama_index.core.evaluation import FaithfulnessEvaluator
        model = OpenAILike(model=MODEL,api_base=BASE,api_key=key,is_chat_model=True,
                           context_window=8192,temperature=0,additional_kwargs=EXTRA)
        return FaithfulnessEvaluator(llm=model).evaluate(response=claim,contexts=[doc]).score
    from phoenix.evals import LLM
    from phoenix.evals.metrics import FaithfulnessEvaluator, HallucinationEvaluator
    model = LLM(provider="openai",model=MODEL,sync_client_kwargs={"api_key":key,"base_url":BASE},
                async_client_kwargs={"api_key":key,"base_url":BASE})
    if cfg=="phoenix_faithfulness":
        evaluator=FaithfulnessEvaluator(llm=model,temperature=0,**EXTRA)
        return evaluator.evaluate({"input":"What does this abstract say?","context":doc,"output":claim})[0].score
    evaluator=HallucinationEvaluator(llm=model,temperature=0,**EXTRA)
    return 1-evaluator.evaluate({"input":f"User request: {QUERY}\n\nRetrieved document:\n{doc}","output":claim})[0].score


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--configs",nargs="+",choices=CONFIGS,default=CONFIGS)
    ap.add_argument("--limit",type=int,choices=[1,50],required=True)
    ap.add_argument("--workers",type=int,default=3)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    key=load_keys()[PROVIDERS["bailian"]["key"]]
    # The TruLens OpenAI SDK adapter reads these standard options at construction.
    os.environ.update(OPENAI_BASE_URL=BASE,OPENAI_API_KEY=key)
    inp=ROOT/"runs/pilot_v1/items.jsonl"
    frozen=json.loads((ROOT/"docs/sampling_manifest.json").read_text())
    if hashlib.sha256(inp.read_bytes()).hexdigest()!=frozen["files"]["runs/pilot_v1/items.jsonl"]:
        raise ValueError("The native pilot check requires the original v1 pilot input.")
    pairs=[p for p in build_pairs(list(map(json.loads,inp.read_text(encoding="utf-8").splitlines()))) if p["premise_cond"]=="abstract"]
    pairs.sort(key=lambda r:hashlib.sha256(f"P10-library-50:{r['doc_id']}:{r['edit']}".encode()).digest())
    sample=pairs[:50]
    a.out.mkdir(parents=True,exist_ok=True)
    for cfg in a.configs:
        base="deployed_q2_qm" if cfg=="phoenix_faithfulness" else "deployed_v1_qm"
        path=ROOT/"runs"/base/"scores.jsonl"
        refs={(r["doc_id"],r["edit"]):r["p"] for r in map(json.loads,path.read_text(encoding="utf-8").splitlines())
              if r["verifier"]==cfg+"__qwen3_7_max"}
        def work(row):
            d,e=row["doc_id"],row["edit"]
            ref=refs.get((d,e))
            out=dict(doc_id=d,edit=e,replay=ref,official=None,agree=False)
            try:
                value=float(native(cfg,row["premise"],row["claim"],key))
                if not math.isfinite(value) or not 0<=value<=1:
                    raise ValueError("Missing or invalid score")
                out["official"]=value
                if ref is not None:
                    # Report the native decision for binary/thresholded flows. Graded
                    # libraries have no default passing threshold; compare full credit.
                    threshold=1 if cfg in ("ragas","trulens") else .5
                    out["agree"]=(value>=threshold)==(ref>=threshold)
                    out["absolute_delta"]=abs(value-ref)
            except Exception as exc:
                out["error"]=type(exc).__name__
                # Keep credentials out of all public records.
                import re
                detail=re.sub(r"sk-[A-Za-z0-9_-]+","[redacted]",str(exc).replace(key,"[redacted]"))
                print(cfg,d,type(exc).__name__,detail[:180],flush=True)
            return out
        dest=a.out/(cfg+".jsonl")
        completed={(r["doc_id"],r["edit"]):r for r in map(json.loads,dest.read_text().splitlines())} if dest.exists() else {}
        todo=[r for r in sample[:a.limit] if (r["doc_id"],r["edit"]) not in completed]
        with dest.open("a",encoding="utf-8") as f, ThreadPoolExecutor(a.workers) as pool:
            for obj in pool.map(work,todo):
                f.write(json.dumps(obj)+"\n")
                f.flush()
                completed[obj["doc_id"],obj["edit"]]=obj
        print(cfg,sum(r["agree"] for r in completed.values()),"/",len(completed),flush=True)


if __name__ == "__main__":
    main()
