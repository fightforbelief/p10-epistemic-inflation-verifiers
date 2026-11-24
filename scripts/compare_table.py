"""Print support-rate drop vs identity (and AUROC) for every verifier/judge, per premise condition.
Stdlib only; reads summary.json files.

    python scripts/compare_table.py runs/pilot_v1/summary.json runs/judge_v1/summary.json
"""
import json
import sys

ORDER = ["identity", "weaken", "negate", "modal_strengthen", "report_verb_upgrade",
         "hedge_adverb_drop", "causal_upgrade", "scope_drop", "quantifier_inflate"]

rows = [r for f in sys.argv[1:] for r in json.load(open(f, encoding="utf-8"))]
vs = list(dict.fromkeys(r["verifier"] for r in rows))
for cond in ("sentence", "abstract"):
    for metric in ("support_rate_drop_vs_identity", "auroc_identity_vs_edit"):
        print(f"\n### premise={cond}  metric={metric} (identity row = supported rate)\n")
        print("| edit | n | " + " | ".join(vs) + " |")
        print("|---|---:|" + "---:|" * len(vs))
        for e in ORDER:
            cells, n = [], ""
            for v in vs:
                r = next((x for x in rows if x["verifier"] == v and x["premise_cond"] == cond
                          and x["edit"] == e), None)
                if r is None:
                    cells.append("")
                    continue
                n = r["n"]
                val = r["rate_supported@0.5"] if e == "identity" else r.get(metric)
                cells.append(f"{val:.2f}")
            print(f"| {e} | {n} | " + " | ".join(cells) + " |")
