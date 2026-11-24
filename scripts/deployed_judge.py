"""P10 'deployed configuration' arm: the default faithfulness pipelines of five RAG-eval
libraries, replayed with the exact prompt text frozen in specs/default_prompts_20261119.json
(extracted from the released wheels, see scripts/extract_default_prompts.py), on the
pilot_v1 pairs with the abstract as retrieved context.

The libraries themselves are not installed; each pipeline is re-implemented step by step:
  ragas        statements = StatementGenerator(question, answer); verdicts = NLIStatement(context, statements);
               score = mean(verdict)
  deepeval     truths = generate_truths(context) [cached per doc]; claims = generate_claims(answer);
               verdicts = generate_verdicts(claims, truths); score = frac(yes|borderline)
               (default penalize_ambiguous_claims=False); deepeval_strict = frac(yes)
  trulens      Groundedness system+user, JSON {"score": 0..3}; score = score/3
  llamaindex   DEFAULT_EVAL_TEMPLATE(query_str=answer, context_str=context); score = 'yes' in text
  phoenix_faithfulness / phoenix_hallucination
               template + forced tool call extract_structured_data{explanation, label}
Supported = score >= 0.5, as in every other arm.

    .\\.venv\\Scripts\\python.exe scripts\\deployed_judge.py --judges qwen3_7_max --limit 8 --out runs\\deployed_smoke
    .\\.venv\\Scripts\\python.exe scripts\\deployed_judge.py --out runs\\deployed_v1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from api_judge import JUDGES, PROVIDERS, _post, load_keys  # noqa: E402

SPEC_PATH = ROOT / "specs" / "default_prompts_20261119.json"
QUERY = "What does this study find?"
CONFIGS = ["ragas", "deepeval", "trulens", "llamaindex", "phoenix_faithfulness", "phoenix_hallucination"]
TOOL_NAME = "extract_structured_data"


# ---------------------------------------------------------------- rendering helpers
def jinja_lite(tmpl: str, **vars) -> str:
    """The subset of jinja used by deepeval's faithfulness templates, with multimodal=False:
    {% if multimodal %}A{% else %}B{% endif %}, {% if multimodal %}A{% endif %}, {{ name }}, {{ _fragments.x }}."""
    mm = bool(vars.get("multimodal"))
    tmpl = re.sub(r"{%\s*if (not )?multimodal\s*%}(.*?)(?:{%\s*else\s*%}(.*?))?{%\s*endif\s*%}",
                  lambda m: (m.group(2) if (mm != bool(m.group(1))) else (m.group(3) or "")), tmpl, flags=re.S)

    def var(m):
        path = m.group(1).split(".")
        v = vars
        for p in path:
            v = v[p]
        return str(v)
    return re.sub(r"{{\s*([\w.]+)\s*}}", var, tmpl)


def mustache(tmpl: str, **vars) -> str:
    return re.sub(r"{{\s*(\w+)\s*}}", lambda m: str(vars[m.group(1)]), tmpl)


def parse_json(text: str):
    """First JSON object in a model reply (handles ```json fences and leading prose)."""
    if text is None:
        return None
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start = t.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        c = t[i]
        if in_str:
            esc = (c == "\\") and not esc
            if c == '"' and not esc:
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except json.JSONDecodeError:
                    return None
    if depth > 0 and not in_str:  # reply ended without its closing brace(s), e.g. '{"verdicts": [...]'
        try:
            return json.loads(t[start:] + "}" * depth)
        except json.JSONDecodeError:
            return None
    return None


def jdump(obj) -> str:
    return json.dumps(obj, indent=4, ensure_ascii=False)


# ---------------------------------------------------------------- API
class Client:
    def __init__(self, provider: str, model: str, key: str):
        self.provider, self.model, self.key = provider, model, key
        self.tokens = {"prompt": 0, "completion": 0}
        self.local = threading.local()  # per-thread usage, so each pair records its own tokens
        self.lock = threading.Lock()

    def chat(self, messages, max_tokens=2048, tools=None, tool_choice=None) -> dict:
        cfg = PROVIDERS[self.provider]
        body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": max_tokens,
                **cfg["extra"]}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice
        r = _post(cfg["base"] + "/chat/completions", self.key, body)
        u = r.get("usage") or {}
        with self.lock:
            self.tokens["prompt"] += u.get("prompt_tokens", 0) or 0
            self.tokens["completion"] += u.get("completion_tokens", 0) or 0
        acc = getattr(self.local, "usage", None)
        if acc is not None:
            acc["prompt"] += u.get("prompt_tokens", 0) or 0
            acc["completion"] += u.get("completion_tokens", 0) or 0
        return r["choices"][0]["message"]

    def text(self, prompt: str, system: str | None = None, max_tokens=2048) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        return self.chat(msgs, max_tokens=max_tokens).get("content") or ""


# ---------------------------------------------------------------- pipelines
class Pipelines:
    def __init__(self, spec: dict, client: Client, query: str = QUERY):
        self.query = query
        self.S, self.c = spec, client
        self.truths_cache: dict[str, list] = {}
        self.truths_lock = threading.Lock()

    def ragas(self, context: str, answer: str) -> dict:
        R = self.S["ragas"]
        m = R["input_marker"]
        r1 = self.c.text(R["statement_generator"].replace(m, jdump({"question": self.query, "answer": answer})))
        st = (parse_json(r1) or {}).get("statements")
        if not st:
            return {"p": None, "fail": "statements", "raw": r1[:500]}
        r2 = self.c.text(R["nli_statement"].replace(m, jdump({"context": context, "statements": st})))
        vs = (parse_json(r2) or {}).get("statements")
        if not vs:
            return {"p": None, "fail": "verdicts", "raw": r2[:500], "statements": st}
        v = [int(x.get("verdict", 0)) for x in vs]
        return {"p": sum(v) / len(v), "statements": st, "verdicts": vs}

    def _deepeval_truths(self, doc_key: str, context: str) -> list:
        with self.truths_lock:
            if doc_key in self.truths_cache:
                return self.truths_cache[doc_key]
        D = self.S["deepeval"]
        T = D["templates"]["FaithfulnessMetric"]
        prompt = jinja_lite(T["generate_truths"], multimodal=False, retrieval_context=context,
                            limit=" FACTUAL, undisputed truths", multimodal_instruction="")
        truths = (parse_json(self.c.text(prompt)) or {}).get("truths") or []
        with self.truths_lock:
            self.truths_cache[doc_key] = truths
        return truths

    def deepeval(self, context: str, answer: str, doc_key: str) -> dict:
        D = self.S["deepeval"]
        T = D["templates"]["FaithfulnessMetric"]
        truths = self._deepeval_truths(doc_key, context)
        claims = (parse_json(self.c.text(jinja_lite(T["generate_claims"], multimodal=False, actual_output=answer,
                                                    multimodal_instruction=""))) or {}).get("claims")
        if claims is None:
            return {"p": None, "fail": "claims"}
        if not claims:  # deepeval: no claims -> score 1
            return {"p": 1.0, "p_strict": 1.0, "claims": [], "truths_n": len(truths)}
        r = self.c.text(jinja_lite(T["generate_verdicts"], multimodal=False, claims=repr(claims),
                                   retrieval_context="\n\n".join(truths), _fragments=D["fragments"]))
        vs = (parse_json(r) or {}).get("verdicts")
        if not vs:
            return {"p": None, "fail": "verdicts", "raw": r[:500]}
        lab = [str(v.get("verdict", "")).strip().lower() for v in vs]
        return {"p": sum(x in ("yes", "borderline") for x in lab) / len(lab),
                "p_strict": sum(x == "yes" for x in lab) / len(lab),
                "claims": claims, "verdicts": vs, "truths_n": len(truths)}

    def trulens(self, context: str, answer: str) -> dict:
        T = self.S["trulens"]
        r = self.c.text(T["user"].format(premise=context, hypothesis=answer), system=T["system"], max_tokens=1024)
        j = parse_json(r)
        if not j or "score" not in j:
            m = re.search(r"\b([0-3])\b", r or "")
            if not m:
                return {"p": None, "fail": "score", "raw": (r or "")[:500]}
            sc = int(m.group(1))
        else:
            sc = int(j["score"])
        sc = max(0, min(3, sc))
        return {"p": sc / 3, "score": sc, "evidence": (j or {}).get("supporting_evidence")}

    def llamaindex(self, context: str, answer: str) -> dict:
        L = self.S["llamaindex"]
        r = self.c.text(L["template"].format(query_str=answer, context_str=context), max_tokens=256)
        return {"p": 1.0 if "yes" in r.lower() else 0.0, "raw": r[:200]}

    def _phoenix(self, key: str, **vars) -> dict:
        P = self.S["phoenix"][key]
        labels = list(P["choices"])
        schema = {"type": "object",
                  "properties": {"explanation": {"type": "string", "description": "A brief explanation of your reasoning."},
                                 "label": {"type": "string", "enum": labels}},
                  "required": ["explanation", "label"]}
        tools = [{"type": "function", "function": {"name": TOOL_NAME, "description": "Extract structured data",
                                                   "parameters": schema}}]
        msg = self.c.chat([{"role": "user", "content": mustache(P["template"], **vars)}], max_tokens=2048,
                          tools=tools, tool_choice={"type": "function", "function": {"name": TOOL_NAME}})
        calls = msg.get("tool_calls") or []
        args = parse_json(calls[0]["function"]["arguments"]) if calls else parse_json(msg.get("content"))
        label = str((args or {}).get("label", "")).strip().lower()
        if label not in P["choices"]:
            return {"p": None, "fail": "label", "raw": json.dumps(msg)[:500]}
        return {"label": label, "explanation": (args or {}).get("explanation", "")[:600]}

    def phoenix_faithfulness(self, context: str, answer: str) -> dict:
        r = self._phoenix("faithfulness", input=self.query, context=context, output=answer)
        if "label" in r:
            r["p"] = self.S["phoenix"]["faithfulness"]["choices"][r["label"]]  # faithful = 1
        return r

    def phoenix_hallucination(self, context: str, answer: str) -> dict:
        record = f"User request: {self.query}\n\nRetrieved document:\n{context}"
        r = self._phoenix("hallucination", input=record, output=answer)
        if "label" in r:
            r["p"] = 1.0 - self.S["phoenix"]["hallucination"]["choices"][r["label"]]  # grounded -> 1
        return r


# ---------------------------------------------------------------- main
def main() -> None:
    import pilot_score as PS

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "deployed_v1")
    ap.add_argument("--cache", type=Path, default=ROOT / "data")
    ap.add_argument("--judges", nargs="*", default=list(JUDGES))
    ap.add_argument("--configs", nargs="*", default=CONFIGS)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--query", default=QUERY)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    keys = load_keys()

    t0 = time.time()
    corpus, sha = PS.load_corpus(a.cache)
    pairs = [p for p in PS.build_pairs(PS.select(corpus, a.n)) if p["premise_cond"] == "abstract"]
    if a.limit:
        pairs = pairs[: a.limit]
    manifest = {"scifact_sha256": sha, "seed": PS.SEED, "n_pairs": len(pairs), "premise_cond": "abstract",
                "spec": str(SPEC_PATH.relative_to(ROOT)), "spec_provenance": spec["provenance"], "query": a.query,
                "label": "PILOT_ONLY_NOT_CONFIRMATORY", "same_pairs_as": "runs/pilot_v1 (abstract premise)", "runs": {}}
    all_rows, summary = [], []
    for jn in a.judges:
        prov, model = JUDGES[jn]
        client = Client(prov, model, keys[PROVIDERS[prov]["key"]])
        pipes = Pipelines(spec, client, a.query)
        # restore deepeval truths cache (one per doc) so resumed runs reuse the same truths
        tc = a.out / f"truths_{jn}.json"
        if tc.exists():
            pipes.truths_cache = json.loads(tc.read_text(encoding="utf-8"))
        for cfg in a.configs:
            tag = f"{cfg}__{jn}"
            raw = a.out / f"raw_{tag}.jsonl"
            done = {}
            if raw.exists():
                for line in raw.read_text(encoding="utf-8").splitlines():
                    d = json.loads(line)
                    done[d["i"]] = d
            lock = threading.Lock()
            fh = raw.open("a", encoding="utf-8")

            def work(i: int) -> None:
                p = pairs[i]
                client.local.usage = {"prompt": 0, "completion": 0}
                try:
                    if cfg == "deepeval":
                        res = pipes.deepeval(p["premise"], p["claim"], str(p["doc_id"]))
                    else:
                        res = getattr(pipes, cfg)(p["premise"], p["claim"])
                except Exception as e:  # noqa: BLE001 -- record and continue; counted as failure
                    res = {"p": None, "fail": f"error: {str(e)[:300]}"}
                with lock:
                    rec = {"i": i, **res, "usage": client.local.usage}
                    done[i] = rec
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()

            ts = time.time()
            todo = [i for i in range(len(pairs)) if i not in done or done[i].get("p") is None]
            if cfg == "deepeval":  # one truths extraction per document, shared by all its edits
                docs = {str(pairs[i]["doc_id"]): pairs[i]["premise"] for i in todo}
                with ThreadPoolExecutor(a.workers) as ex:
                    list(ex.map(lambda kv: pipes._deepeval_truths(*kv), docs.items()))
                tc.write_text(json.dumps(pipes.truths_cache, ensure_ascii=False), encoding="utf-8")
            with ThreadPoolExecutor(a.workers) as ex:
                list(ex.map(work, todo))
            fh.close()
            if cfg == "deepeval":
                tc.write_text(json.dumps(pipes.truths_cache, ensure_ascii=False), encoding="utf-8")
            res = [done[i] for i in range(len(pairs))]
            fails = sum(r.get("p") is None for r in res)
            variants = [(tag, "p")] + ([(f"deepeval_strict__{jn}", "p_strict")] if cfg == "deepeval" else [])
            for vtag, field in variants:
                rows = [{**{k: p[k] for k in ("doc_id", "edit", "premise_cond", "expected_supported")},
                         "verifier": vtag, "p": float(r[field])}
                        for p, r in zip(pairs, res) if r.get(field) is not None]
                all_rows += rows
                if not a.limit:
                    # summarise needs an identity score for every doc that has an edit row
                    ident = {r["doc_id"] for r in rows if r["edit"] == "identity"}
                    summary += PS.summarise([r for r in rows if r["doc_id"] in ident], vtag)
            us = [r["usage"] for r in res if r.get("usage")]
            usage = {"prompt": sum(u["prompt"] for u in us), "completion": sum(u["completion"] for u in us),
                     "pairs_with_usage": len(us)}  # pairs scored before 2026-11-19 PM have no record
            manifest["runs"][tag] = {"provider": prov, "model": model, "n": len(res), "failures": fails, "usage": usage,
                                     "seconds_this_session": round(time.time() - ts, 2)}
            print(f"{tag}: {len(res)} pairs, failures {fails}, {round(time.time() - ts)}s", flush=True)
        manifest["runs"][f"tokens__{jn}"] = dict(client.tokens)

    (a.out / "scores.jsonl").write_text("\n".join(json.dumps(r) for r in all_rows), encoding="utf-8")
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    manifest["total_seconds"] = round(time.time() - t0, 2)
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (a.out / "run_complete.json").write_text(json.dumps({"ok": True}), encoding="utf-8")


if __name__ == "__main__":
    main()
