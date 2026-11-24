"""P10 LLM-judge control, API half (Gate 0 condition 3).

Same pairs, system message and two prompts as scripts/llm_judge.py, sent to
OpenAI-compatible chat endpoints (DeepSeek, Alibaba Bailian/DashScope) with
temperature 0, max_tokens 1, logprobs on.  P(supported) is read from the first
token's top_logprobs: P(Yes-like) / (P(Yes-like) + P(No-like)).  If neither appears,
the sampled token is parsed (1.0 / 0.0) and the row is flagged.

Keys come from <portfolio root>/.apikey ("NAME = value" lines), never from argv,
and are never written to any output.  Stdlib only (no new dependencies).

    .\\.venv\\Scripts\\python.exe scripts\\api_judge.py --probe
    .\\.venv\\Scripts\\python.exe scripts\\api_judge.py --judges deepseek_v4_pro --limit 16 --out runs\\api_smoke
    .\\.venv\\Scripts\\python.exe scripts\\api_judge.py --out runs\\judge_api_v1
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from llm_judge import PROMPTS, build_messages  # noqa: E402

KEYFILE = ROOT.parent / ".apikey"
PROVIDERS = {
    "deepseek": {"base": "https://api.deepseek.com", "key": "DEEPSEEK_APIKEY",
                 "extra": {"thinking": {"type": "disabled"}}},
    "bailian": {"base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "key": "BAILIAN_APIKEY",
                "extra": {"enable_thinking": False}},
}
# name: (provider, model id) -- model ids confirmed with --probe before the run
JUDGES = {
    "deepseek_v4_pro": ("deepseek", "deepseek-v4-pro"),
    "qwen3_7_max": ("bailian", "qwen3.7-max-2026-06-08"),
}
YES = {"yes"}
NO = {"no"}


def load_keys(path: Path = KEYFILE) -> dict:
    keys = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip().strip('"').strip("'")
    return keys


def prob_from_top(top: list[dict], sampled: str) -> tuple[float, str]:
    """top: [{'token': str, 'logprob': float}, ...] for the first position."""
    y = sum(math.exp(t["logprob"]) for t in top if t["token"].strip().lower() in YES)
    n = sum(math.exp(t["logprob"]) for t in top if t["token"].strip().lower() in NO)
    if y + n > 0:
        return y / (y + n), "logprobs"
    s = sampled.strip().lower()
    if s.startswith("yes"):
        return 1.0, "parsed"
    if s.startswith("no"):
        return 0.0, "parsed"
    return float("nan"), "unparseable"


def _post(url: str, key: str, body: dict, tries: int = 6) -> dict:
    data = json.dumps(body).encode()
    for k in range(tries):
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and k < tries - 1:
                time.sleep(2 ** k * 3)
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}") from None
        except (urllib.error.URLError, TimeoutError):
            if k < tries - 1:
                time.sleep(2 ** k * 3)
                continue
            raise
    raise RuntimeError("unreachable")


def ask(provider: str, model: str, key: str, prompt: str, premise: str, claim: str) -> dict:
    cfg = PROVIDERS[provider]
    body = {"model": model, "messages": build_messages(prompt, premise, claim), "temperature": 0,
            "max_tokens": 1, "logprobs": True, "top_logprobs": 5, **cfg["extra"]}
    r = _post(cfg["base"] + "/chat/completions", key, body)
    ch = r["choices"][0]
    sampled = ch["message"].get("content") or ""
    lp = (ch.get("logprobs") or {}).get("content") or []
    top = lp[0].get("top_logprobs", []) if lp else []
    p, method = prob_from_top(top, sampled)
    return {"p": p, "method": method, "sampled": sampled, "served_model": r.get("model"),
            "usage": r.get("usage", {})}


def probe(keys: dict) -> None:
    for name, cfg in PROVIDERS.items():
        key = keys.get(cfg["key"])
        print(f"== {name}: key present: {bool(key)}")
        if not key:
            continue
        try:
            req = urllib.request.Request(cfg["base"] + "/models", headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=60) as r:
                ids = sorted(m["id"] for m in json.loads(r.read())["data"])
            print("models:", ", ".join(i for i in ids if any(s in i for s in ("deepseek", "qwen3", "qwen-max", "qwen-plus")))[:1500])
        except Exception as e:  # noqa: BLE001
            print("models list failed:", str(e)[:200])
    for jn, (prov, model) in JUDGES.items():
        key = keys.get(PROVIDERS[prov]["key"])
        if not key:
            continue
        try:
            out = ask(prov, model, key, "generic", "Mice given drug X had smaller tumours.",
                      "Drug X causes tumours to shrink in humans.")
            print(jn, {k: out[k] for k in ("p", "method", "sampled", "served_model")})
        except Exception as e:  # noqa: BLE001
            print(jn, "FAILED:", str(e)[:300])


def main() -> None:
    import pilot_score as PS

    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "judge_api_v1")
    ap.add_argument("--cache", type=Path, default=ROOT / "data")
    ap.add_argument("--judges", nargs="*", default=list(JUDGES))
    ap.add_argument("--prompts", nargs="*", default=list(PROMPTS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    keys = load_keys()
    if a.probe:
        probe(keys)
        return
    a.out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    corpus, sha = PS.load_corpus(a.cache)
    pairs = PS.build_pairs(PS.select(corpus, a.n))
    if a.limit:
        pairs = pairs[: a.limit]
    manifest = {"scifact_sha256": sha, "seed": PS.SEED, "n_pairs": len(pairs), "judges": {},
                "label": "PILOT_ONLY_NOT_CONFIRMATORY", "same_pairs_as": "runs/pilot_v1"}
    all_rows, summary = [], []
    for jn in a.judges:
        prov, model = JUDGES[jn]
        key = keys[PROVIDERS[prov]["key"]]
        for prompt in a.prompts:
            tag = f"{jn}__{prompt}"
            raw = a.out / f"raw_{tag}.jsonl"  # resumable cache, one line per pair index
            done = {}
            if raw.exists():
                for l in raw.read_text(encoding="utf-8").splitlines():
                    d = json.loads(l)
                    done[d["i"]] = d
            lock = threading.Lock()
            fh = raw.open("a", encoding="utf-8")

            def work(i: int) -> None:
                p = pairs[i]
                res = ask(prov, model, key, prompt, p["premise"], p["claim"])
                with lock:
                    rec = {"i": i, **res}
                    done[i] = rec
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()

            ts = time.time()
            todo = [i for i in range(len(pairs)) if i not in done]
            with ThreadPoolExecutor(a.workers) as ex:
                list(ex.map(work, todo))
            fh.close()
            res = [done[i] for i in range(len(pairs))]
            methods = {m: sum(r["method"] == m for r in res) for m in ("logprobs", "parsed", "unparseable")}
            usage = {k: sum((r.get("usage") or {}).get(k, 0) or 0 for r in res)
                     for k in ("prompt_tokens", "completion_tokens")}
            manifest["judges"][tag] = {"provider": prov, "model": model, "prompt": prompt,
                                       "base_url": PROVIDERS[prov]["base"],
                                       "served_models": sorted({str(r.get("served_model")) for r in res}),
                                       "methods": methods, "usage": usage,
                                       "seconds_this_session": round(time.time() - ts, 2)}
            rows = [{**{k: p[k] for k in ("doc_id", "edit", "premise_cond", "expected_supported")},
                     "verifier": tag, "p": r["p"]} for p, r in zip(pairs, res) if r["method"] != "unparseable"]
            all_rows += rows
            if not a.limit:
                summary += PS.summarise(rows, tag)
            print(f"{tag}: {len(res)} pairs, methods {methods}, tokens {usage}", flush=True)

    (a.out / "scores.jsonl").write_text("\n".join(json.dumps(r) for r in all_rows), encoding="utf-8")
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    manifest["total_seconds"] = round(time.time() - t0, 2)
    (a.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (a.out / "run_complete.json").write_text(json.dumps({"ok": True}), encoding="utf-8")


if __name__ == "__main__":
    main()
