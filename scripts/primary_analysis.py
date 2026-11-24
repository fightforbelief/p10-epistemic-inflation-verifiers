"""Six prospective P10 decisions. Input is one joined record per processed document.

Each document has edit, valid (frozen human label), has_negate, has_weaken and
a scores dictionary. Each configuration expects identity, the eligible controls
and (for valid rows) the focal edit under 'focal'. A failed scheduled call is null.
Use the same scored document roster in every configuration. See the freeze note.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

ALPHA = .05 / 6
SEED = 20261124
NBOOT = 10000
MODAL = "modal_strengthen"
HEDGE = "hedge_adverb_drop"
MINICHECK = ("minicheck_roberta_large", "minicheck_deberta_v3_large")
JUDGES = ("deepseek", "qwen")


def cp_lower(k, n, alpha=ALPHA):
    """Invert P_bin(n,p)(X >= k) by bisection, including both boundary cases."""
    if not 0 <= k <= n or n < 1:
        raise ValueError("Invalid binomial count")
    if not k:
        return 0.
    if k == n:
        return alpha ** (1/n)
    j = np.arange(k, n+1)
    logcomb = np.array([math.lgamma(n+1)-math.lgamma(i+1)-math.lgamma(n-i+1) for i in j])
    lo, hi = 0., 1.
    for _ in range(52):
        p = (lo + hi)/2
        survival = np.exp(logcomb + j * math.log(p) + (n-j) * math.log1p(-p)).sum()
        if survival < alpha:
            lo = p
        else:
            hi = p
    return (lo+hi)/2


def paired(rows, left, right):
    vals = [(a, b) for r in rows if (a := left(r)) is not None and (b := right(r)) is not None]
    n = len(vals)
    out = {"scheduled": len(rows), "n": n, "mean": None, "lower": None}
    if not n:
        return out
    gains = sum(a > b for a, b in vals)
    losses = sum(a < b for a, b in vals)
    out.update(gains=gains, losses=losses, mean=(gains-losses)/n)
    if max(gains, losses, n-gains-losses) == n:
        # Simultaneous exact bounds on both discordant probabilities.
        out["lower"] = cp_lower(gains, n, ALPHA/2) + cp_lower(n-losses, n, ALPHA/2) - 1
        out["method"] = "simultaneous exact binomial bounds"
    else:
        rng = np.random.default_rng(SEED)
        draws = rng.multinomial(n, [gains/n, losses/n, (n-gains-losses)/n], size=NBOOT)
        out["lower"] = float(np.quantile((draws[:,0]-draws[:,1])/n, ALPHA, method="lower"))
        out["method"] = "paired document bootstrap"
    return out


def rate(rows, get):
    values = [v for r in rows if (v := get(r)) is not None]
    n, k = len(values), sum(values)
    return {"scheduled": len(rows), "n": n, "k": k, "mean": k/n if n else None,
            "lower": cp_lower(k, n) if n else None}


def configurations():
    return ([f"{m}/{c}" for m in MINICHECK for c in ("abstract", "sentence")] +
            [f"{m}/{p}" for m in JUDGES for p in ("generic", "strength")])


def decide(rows):
    if not rows or len(set(r["doc_id"] for r in rows)) != len(rows):
        raise ValueError("Expected one row per unique processed document")
    for r in rows:
        if any(type(r[k]) is not bool for k in ("valid", "has_negate", "has_weaken")):
            raise ValueError("Expected boolean eligibility flags")
        if r["edit"] not in {MODAL, HEDGE, "scope_drop", "causal_upgrade", "quantifier_inflate"}:
            raise ValueError("Unexpected edit")
    controls = [r for r in rows if r["has_negate"]]
    valid = [r for r in rows if r["valid"]]
    strata = {e: [r for r in valid if r["edit"] == e] for e in (MODAL, HEDGE)}
    guards = {}
    def getter(cfg, variant):
        def get(row):
            p = row["scores"][cfg][variant]
            if p is None:
                return None
            if type(p) not in (float, int) or not 0 <= p <= 1:
                raise ValueError("Invalid probability")
            return int(p > .5 if cfg.split("/")[0] in MINICHECK else p >= .5)
        return get
    for cfg in configurations():
        expected = [(r, v) for r in rows for v, use in
                    (("identity", True), ("negate", r["has_negate"]), ("weaken", r["has_weaken"] and r["valid"]),
                     ("focal", r["valid"])) if use]
        missing = sum(getter(cfg, v)(r) is None for r, v in expected)
        identity = rate(controls, getter(cfg, "identity"))
        neg = paired(controls, getter(cfg, "identity"), getter(cfg, "negate"))
        ok = (missing/len(expected) <= .02 and neg["n"] >= 150 and
              identity["mean"] >= .9 and neg["mean"] >= .7)
        guards[cfg] = dict(ok=ok, missing=missing, scheduled=len(expected), identity=identity, negation=neg)
    result = {}
    for m in MINICHECK:
        a, s = m + "/abstract", m + "/sentence"
        rates = {e: rate(group, getter(a, "focal")) for e, group in strata.items()}
        result["H1/"+m] = {"rates": rates, "met": guards[a]["ok"] and all(
            x["n"] > 0 and x["lower"] > .70 for x in rates.values())}
        diff = paired(strata[MODAL], getter(a, "focal"), getter(s, "focal"))
        result["H2/"+m] = {"difference": diff, "met": bool(guards[a]["ok"] and guards[s]["ok"]
                                         and diff["n"] and diff["lower"] > .20)}
    for m in JUDGES:
        g, s = m + "/generic", m + "/strength"
        def diff(group, variant):
            return paired(group, getter(g, variant), getter(s, variant))
        modal = diff(strata[MODAL], "focal")
        preservation = [diff(valid, "identity"), diff([r for r in valid if r["has_weaken"]], "weaken")]
        result["H3/"+m] = {"modal": modal, "identity": preservation[0], "weaken": preservation[1],
                            "met": bool(guards[g]["ok"] and guards[s]["ok"] and modal["n"]
                                        and modal["lower"] > .10 and all(
                                            d["n"] and d["mean"] <= .05 for d in preservation))}
    return {"alpha": ALPHA, "guards": guards, "hypotheses": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("joined", type=Path)
    args = parser.parse_args()
    print(json.dumps(decide([json.loads(l) for l in args.joined.read_text(encoding="utf-8").splitlines()]), indent=2))
