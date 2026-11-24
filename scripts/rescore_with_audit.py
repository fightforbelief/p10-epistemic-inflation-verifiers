"""Join the hand-audit labels to every scored arm and recompute the tables.

    .\\.venv\\Scripts\\python.exe scripts\\rescore_with_audit.py --labels audit\\P10_edit_audit_v1_edited.xlsx --out runs\\audit_rescore_v1

Label sets (chosen AFTER the model scores were known; README only fixed "drop Q1=broken and
recompute by Q2/Q3/Q4", so all sets are reported and none is confirmatory):
  all       every scored edit
  nb        Q1 != broken
  valid     nb & Q2 == yes & Q3 == no              (abstract premise)
  valid_s   nb & Q2 == yes                         (sentence premise: the abstract is not shown, Q3 is moot)
  lenient   nb & Q2 in {yes, contested} & Q3 == no
  warranted nb & Q2 == yes & Q3 == yes             (contrast: accepting these is correct)
Two decision rules: p >= 0.5 (as before) and 'full' p >= 0.999.  'full' matters only for graded
pipelines (ragas / deepeval / trulens), where 0.5 hides partial deductions such as TruLens 3 -> 2.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import perturb as P  # noqa: E402

SEED, N_BOOT = 20261119, 1000
ARMS = ["pilot_v1", "judge_v1", "judge_api_v1", "deployed_v1_ds", "deployed_v1_qm", "deployed_q2_ds", "deployed_q2_qm"]
ALLOWED = {"Q1": {"ok", "minor", "broken"}, "Q2": {"yes", "no", "contested"}, "Q3": {"yes", "no", "unclear"},
           "Q4": {"generic", "existential", "ambiguous", "n/a", ""}, "C1": {"as_intended", "not_as_intended", "broken"}}
RULES = {"t0.5": 0.5, "full": 0.999}


def in_set(name: str, r: dict) -> bool:
    if name == "all":
        return True
    if r["Q1"] == "broken":
        return False
    return {"nb": True,
            "valid": r["Q2"] == "yes" and r["Q3"] == "no",
            "valid_s": r["Q2"] == "yes",
            "lenient": r["Q2"] in ("yes", "contested") and r["Q3"] == "no",
            "warranted": r["Q2"] == "yes" and r["Q3"] == "yes"}[name]


def read_labels(xlsx: Path, key: Path) -> tuple[dict, dict]:
    from openpyxl import load_workbook

    rows = {d["audit_id"]: d for d in map(json.loads, key.read_text(encoding="utf-8").splitlines())}
    wb = load_workbook(xlsx, read_only=True)
    infl, ctrl = {}, {}
    for sheet, out, cols in (("Inflations", infl, {"Q1": 5, "Q2": 6, "Q3": 7, "Q4": 8}), ("Controls", ctrl, {"C1": 5})):
        for row in wb[sheet].iter_rows(min_row=2, values_only=True):
            if not row[0]:
                continue
            k = rows[row[0]]
            if (row[2], row[3]) != (k["source"], k["edited"]):
                raise ValueError(f"{row[0]}: sentence text differs from the audit key")
            lab = {q: str(row[c] or "").strip() for q, c in cols.items()}
            for q, v in lab.items():
                if v not in ALLOWED[q]:
                    raise ValueError(f"{row[0]} {q}: unexpected label {v!r}")
            out[(k["doc_id"], k["edit"])] = {**lab, "audit_id": row[0]}
    return infl, ctrl


def stats(pairs: list[tuple[float, float]], thr: float, seed: int = SEED) -> dict:
    """pairs = (p_identity, p_edit), one per document."""
    import numpy as np

    pi = np.array([a for a, _ in pairs]) >= thr
    pe = np.array([b for _, b in pairs]) >= thr
    d = pi.astype(float) - pe.astype(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), (N_BOOT, len(d)))
    q = lambda x: [round(float(v), 3) for v in np.quantile(x[idx].mean(1), [.025, .975])]
    return {"n": len(d), "identity_rate": float(pi.mean()), "accepted": float(pe.mean()), "accepted_ci95": q(pe.astype(float)),
            "drop": float(d.mean()), "drop_ci95": q(d),
            "score_lower_than_identity": float(np.mean([b < a - 1e-9 for a, b in pairs]))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    infl, ctrl = read_labels(a.labels, ROOT / "audit/edit_audit_v1.jsonl")

    table, flips, missing = [], [], []
    for arm in ARMS:
        f = ROOT / "runs" / arm / "scores.jsonl"
        if not f.exists():
            missing.append(arm)
            continue
        S: dict = collections.defaultdict(dict)
        for r in map(json.loads, f.read_text(encoding="utf-8").splitlines()):
            S[(r["verifier"], r["premise_cond"])][(r["doc_id"], r["edit"])] = r["p"]
        for (ver, cond), sc in S.items():
            for edit in P.INFLATIONS:
                for s in ("all", "nb", "valid", "valid_s", "lenient", "warranted"):
                    ks = [k for k, lab in infl.items() if k[1] == edit and in_set(s, lab) and k in sc]
                    pr = [(sc[(d, "identity")], sc[(d, e)]) for d, e in ks if (d, "identity") in sc]
                    for rn, thr in RULES.items():
                        if pr:
                            table.append({"arm": arm, "verifier": ver, "cond": cond, "edit": edit, "set": s, "rule": rn, **stats(pr, thr)})
                if edit == "scope_drop":
                    for s4 in ("generic", "existential"):
                        pr = [(sc[(d, "identity")], sc[(d, e)]) for (d, e), lab in infl.items()
                              if e == edit and lab["Q1"] != "broken" and lab["Q4"] == s4 and (lab["Q3"] == "no" or s4 == "existential") and (d, e) in sc]
                        for rn, thr in RULES.items():
                            if pr:
                                table.append({"arm": arm, "verifier": ver, "cond": cond, "edit": edit, "set": f"Q4_{s4}", "rule": rn, **stats(pr, thr)})
            for edit in ("weaken", "negate"):
                groups = {"all": [k for k in sc if k[1] == edit],
                          "audited_ok": [k for k, lab in ctrl.items() if k[1] == edit and lab["C1"] == "as_intended" and k in sc]}
                for s, ks in groups.items():
                    pr = [(sc[(d, "identity")], sc[(d, e)]) for d, e in ks if (d, "identity") in sc]
                    for rn, thr in RULES.items():
                        if pr:
                            table.append({"arm": arm, "verifier": ver, "cond": cond, "edit": edit, "set": s, "rule": rn, **stats(pr, thr)})
        for ver in {v for v, _ in S}:  # context leniency: rejected given the sentence -> accepted given the abstract?
            A, B = S.get((ver, "sentence")), S.get((ver, "abstract"))
            if not A or not B:
                continue
            for edit in P.INFLATIONS:
                for q3 in ("no", "yes"):
                    ks = [k for k, lab in infl.items() if k[1] == edit and lab["Q1"] != "broken" and lab["Q2"] == "yes" and lab["Q3"] == q3]
                    rej = [k for k in ks if A[k] < 0.5]
                    flips.append({"verifier": ver, "edit": edit, "Q3": q3, "n": len(ks), "rejected_sentence": len(rej),
                                  "flipped_to_accepted_with_abstract": sum(B[k] >= 0.5 for k in rej)})
    (a.out / "table.jsonl").write_text("\n".join(map(json.dumps, table)), encoding="utf-8")
    (a.out / "flips.json").write_text(json.dumps(flips, indent=1), encoding="utf-8")
    (a.out / "labels.jsonl").write_text("\n".join(json.dumps({"doc_id": d, "edit": e, **v}) for (d, e), v in {**infl, **ctrl}.items()), encoding="utf-8")
    import hashlib
    (a.out / "manifest.json").write_text(json.dumps({"labels_sha256": hashlib.sha256(a.labels.read_bytes()).hexdigest(), "seed": SEED,
        "n_infl": len(infl), "n_ctrl": len(ctrl), "missing_arms": missing, "label": "PILOT_ONLY_NOT_CONFIRMATORY"}, indent=1), encoding="utf-8")
    print(f"labels {len(infl)}+{len(ctrl)}, table rows {len(table)}, missing arms {missing}")


if __name__ == "__main__":
    main()
