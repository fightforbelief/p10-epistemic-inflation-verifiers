"""Build the student hand-audit workbook for the pilot_v1 edits (Gate 0 condition 6).

Rows are regenerated from runs/pilot_v1/items.jsonl with src/perturb.py (the same deterministic
rules the pilot scored), so every audit row is exactly one scored pair.  No verifier or judge
output appears in the workbook: annotators are blind to model behaviour.

    .\\.venv\\Scripts\\python.exe scripts\\build_audit_sheet.py
      -> audit/P10_edit_audit_v1.xlsx, audit/edit_audit_v1.jsonl (same rows, for joins)
"""
from __future__ import annotations

import difflib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import perturb as P  # noqa: E402

SEED = 20261119
N_CONTROL_EACH = 40          # weaken / negate rows sampled for a validity check
DOUBLE_CODE_FRAC = 0.20      # share of rows flagged for a second annotator

EDIT_NAMES = {
    "modal_strengthen": "modal: may/might → will",
    "report_verb_upgrade": "reporting verb: suggest/indicate → demonstrate/prove",
    "hedge_adverb_drop": "hedge removed (possibly, likely, appears to …)",
    "causal_upgrade": "association → causation",
    "scope_drop": "scope qualifier removed (in mice, in vitro …)",
    "quantifier_inflate": "quantifier: some → all",
    "weaken": "control: weakened (It is possible that …)",
    "negate": "control: negated",
}

LISTS = {
    "edit_ok": ["ok", "minor", "broken"],
    "stronger": ["yes", "no", "contested"],
    "warrants": ["no", "yes", "unclear"],
    "scope": ["generic", "existential", "ambiguous"],
    "control_rel": ["as_intended", "not_as_intended", "broken"],
}


def change_summary(src: str, dst: str) -> str:
    tok = lambda s: re.findall(r"[\w'-]+|[^\w\s]", s)  # punctuation as its own token
    a, b = tok(src), tok(dst)
    parts = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            continue
        old, new = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        parts.append(f"{old} → {new}" if old and new else (f"[removed] {old}" if old else f"[added] {new}"))
    return " ; ".join(parts)


def build_rows() -> tuple[list[dict], list[dict]]:
    items = [json.loads(l) for l in (ROOT / "runs/pilot_v1/items.jsonl").read_text(encoding="utf-8").splitlines()]
    infl, ctrl = [], []
    for it in items:
        for edit, claim in P.variants(it["sentence"]).items():
            if edit == "identity":
                continue
            row = {"doc_id": it["doc_id"], "sent_idx": it["sent_idx"], "edit": edit, "source": it["sentence"],
                   "edited": claim, "change": change_summary(it["sentence"], claim), "abstract": it["abstract"]}
            (infl if edit in P.INFLATIONS else ctrl).append(row)
    rng = random.Random(SEED)
    rng.shuffle(infl)
    controls = []
    for e in ("weaken", "negate"):
        pool = [r for r in ctrl if r["edit"] == e]
        controls += rng.sample(pool, N_CONTROL_EACH)
    rng.shuffle(controls)
    for prefix, rows in (("I", infl), ("C", controls)):
        flagged = set(rng.sample(range(len(rows)), round(DOUBLE_CODE_FRAC * len(rows))))
        for k, r in enumerate(rows):
            r["audit_id"] = f"{prefix}{k + 1:03d}"
            r["double_code"] = "yes" if k in flagged else ""
    return infl, controls


def write_workbook(infl: list[dict], controls: list[dict], out: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    F = "Arial"
    head = Font(name=F, bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="305496")
    input_fill = PatternFill("solid", fgColor="FFF2CC")   # cells the annotator fills in
    na_fill = PatternFill("solid", fgColor="E7E6E6")
    body = Font(name=F, size=10)
    wrap = Alignment(wrap_text=True, vertical="top")
    thin = Border(*(Side(style="thin", color="BFBFBF"),) * 4)

    wb = Workbook()
    rd = wb.active
    rd.title = "README"

    # ---------------- lists (hidden) for dropdowns
    ls = wb.create_sheet("Lists")
    for c, (name, vals) in enumerate(LISTS.items(), start=1):
        ls.cell(1, c, name).font = Font(name=F, bold=True)
        for r, v in enumerate(vals, start=2):
            ls.cell(r, c, v).font = body
    ls.sheet_state = "hidden"

    def dv_for(ws, list_idx: int, n: int, rng: str) -> None:
        col = "ABCDE"[list_idx]
        dv = DataValidation(type="list", formula1=f"=Lists!${col}$2:${col}${n + 1}", allow_blank=True,
                            showErrorMessage=True, errorTitle="Use the dropdown",
                            error="Pick one of the listed values (see README).")
        ws.add_data_validation(dv)
        dv.add(rng)

    def sheet(title, cols, rows, fill_cols, validations, na_rule=None):
        ws = wb.create_sheet(title)
        for c, (h, w, _) in enumerate(cols, start=1):
            cell = ws.cell(1, c, h)
            cell.font, cell.fill, cell.alignment, cell.border = head, head_fill, wrap, thin
            ws.column_dimensions[cell.column_letter].width = w
        for r, row in enumerate(rows, start=2):
            for c, (h, _, key) in enumerate(cols, start=1):
                cell = ws.cell(r, c, row.get(key, "") if key else None)
                cell.font, cell.alignment, cell.border = body, wrap, thin
                if h in fill_cols:
                    cell.fill = input_fill
                    if na_rule and na_rule(h, row):
                        cell.value, cell.fill = "n/a", na_fill
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = f"A1:{ws.cell(1, len(cols)).column_letter}{len(rows) + 1}"
        for col_name, list_idx in validations.items():
            c = next(i for i, (h, _, _) in enumerate(cols, start=1) if h == col_name)
            L = ws.cell(1, c).column_letter
            dv_for(ws, list_idx, len(list(LISTS.values())[list_idx]), f"{L}2:{L}{len(rows) + 1}")
        return ws

    for r in infl + controls:
        r["edit_label"] = EDIT_NAMES[r["edit"]]

    icols = [("audit_id", 9, "audit_id"), ("edit type", 22, "edit_label"), ("source sentence", 48, "source"),
             ("edited sentence", 48, "edited"), ("what changed", 26, "change"),
             ("Q1 edit_ok", 11, None), ("Q2 stronger_than_source", 13, None), ("Q3 abstract_warrants_edited", 14, None),
             ("Q4 scope_reading (scope rows only)", 14, None), ("notes", 30, None),
             ("double_code", 9, "double_code"), ("doc_id", 10, "doc_id"), ("full abstract (for Q3)", 110, "abstract")]
    sheet("Inflations", icols, infl, {"Q1 edit_ok", "Q2 stronger_than_source", "Q3 abstract_warrants_edited",
                                      "Q4 scope_reading (scope rows only)", "notes"},
          {"Q1 edit_ok": 0, "Q2 stronger_than_source": 1, "Q3 abstract_warrants_edited": 2,
           "Q4 scope_reading (scope rows only)": 3},
          na_rule=lambda h, row: h.startswith("Q4") and row["edit"] != "scope_drop")

    ccols = [("audit_id", 9, "audit_id"), ("edit type", 24, "edit_label"), ("source sentence", 55, "source"),
             ("edited sentence", 55, "edited"), ("what changed", 26, "change"), ("C1 control_ok", 14, None),
             ("notes", 30, None), ("double_code", 9, "double_code"), ("doc_id", 10, "doc_id")]
    sheet("Controls", ccols, controls, {"C1 control_ok", "notes"}, {"C1 control_ok": 4})

    # ---------------- README
    text = [
        ("P10 edit hand-audit (pilot v1) — instructions", "title"),
        ("Purpose", "h"),
        ("The pilot generated these edits with rules (src/perturb.py). Before any number can be read as an effect "
         "size, a person has to confirm that each edit is well-formed and really makes the claim stronger than the "
         "source. You are NOT judging any model: no model output appears in this workbook, on purpose.", "p"),
        ("What to fill in", "h"),
        ("Only the yellow cells. Use the dropdowns; write anything else in 'notes'. Grey 'n/a' cells need nothing.", "p"),
        ("Sheet 'Inflations': 329 rows (all strengthening edits). Sheet 'Controls': 80 rows (40 weakened, 40 negated).", "p"),
        ("Rows marked double_code = yes will also be labelled by a second person to measure agreement — label them "
         "exactly like the others and do not discuss them before both are done.", "p"),
        ("Inflations: questions", "h"),
        ("Q1 edit_ok — Is the edited sentence a well-formed sentence whose only change is the intended edit?\n"
         "  ok: grammatical, and only the intended words changed.\n"
         "  minor: small fluency or grammar glitch, but the intended change is intact and the meaning is clear.\n"
         "  broken: ungrammatical, or the edit changed something other than intended "
         "(e.g. 'in animal model studies' → 'observations model studies'). Broken rows are excluded; skip Q2–Q4.", "p"),
        ("Q2 stronger_than_source — Judged from the two sentences alone: does the edited sentence claim MORE than the "
         "source (more certain, causal instead of associational, or more general), so that the source does not license it?\n"
         "  yes: clearly stronger.\n"
         "  no: equivalent or weaker (e.g. the removed word was not a hedge, or 'likely' was a probability estimate the "
         "sentence still conveys).\n"
         "  contested: depends on reading — say why in notes.", "p"),
        ("Q3 abstract_warrants_edited — Now read the full abstract (last column). Does anything in the abstract warrant "
         "the EDITED sentence as stated (same certainty, causal force and generality)?\n"
         "  no: nothing in the abstract supports the stronger version.\n"
         "  yes: another sentence states it at that strength (or gives evidence that clearly licenses it) — note which.\n"
         "  unclear: explain in notes.", "p"),
        ("Q4 scope_reading — scope-removal rows only. Read the edited sentence as a typical reader of a RAG answer "
         "would.\n"
         "  generic: they would take it as holding in general (e.g. for humans / in vivo).\n"
         "  existential: they would take it as 'shown somewhere', which is still true.\n"
         "  ambiguous: either reading is natural.", "p"),
        ("Controls: question", "h"),
        ("C1 control_ok — weakened rows: as_intended = the edit is no stronger than the source (the source still "
         "supports it). negated rows: as_intended = the edit contradicts the source. not_as_intended = otherwise. "
         "broken = ungrammatical.", "p"),
        ("Example (format only — not a real row)", "h"),
        ("source: 'These data suggest that IL-6 drives fibrosis in mice.'  edited: 'These data demonstrate that IL-6 "
         "drives fibrosis in mice.'  →  Q1 ok · Q2 yes · Q3 no · Q4 n/a · notes: (empty)", "p"),
        ("Practicalities", "h"),
        ("Expect about 30–40 seconds per row (≈4 hours for both sheets). Work row by row; do not sort by edit type "
         "while labelling (order is shuffled to avoid fatigue effects within a type). Save often. Do not edit the "
         "white columns.", "p"),
        ("Provenance", "h"),
        (f"Built by scripts/build_audit_sheet.py from runs/pilot_v1/items.jsonl (300 SciFact sentences, seed {SEED}) "
         "with the v1 rules. Row order, control sample and double-code flags use the same seed. The same rows are "
         "in audit/edit_audit_v1.jsonl for joining labels back to scores.", "p"),
    ]
    rd.column_dimensions["A"].width = 130
    for r, (t, kind) in enumerate(text, start=1):
        c = rd.cell(r, 1, t)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        c.font = Font(name=F, size=14 if kind == "title" else 11, bold=kind in ("title", "h"))
        if kind == "p":
            rd.row_dimensions[r].height = 15 * (t.count("\n") + 1 + len(t) // 140)
    leg = len(text) + 2
    rd.cell(leg, 1, "Legend: yellow = fill in · grey n/a = leave · white = given, do not edit").font = Font(name=F, italic=True)
    rd.cell(leg, 1).fill = input_fill

    wb.move_sheet("Lists", offset=10)
    wb.save(out)


def main() -> None:
    infl, controls = build_rows()
    out_dir = ROOT / "audit"
    out_dir.mkdir(exist_ok=True)
    with (out_dir / "edit_audit_v1.jsonl").open("w", encoding="utf-8") as f:
        for r in infl + controls:
            f.write(json.dumps({k: r[k] for k in ("audit_id", "doc_id", "sent_idx", "edit", "source", "edited",
                                                  "change", "double_code")}, ensure_ascii=False) + "\n")
    write_workbook(infl, controls, out_dir / "P10_edit_audit_v1.xlsx")
    print(f"inflations {len(infl)}, controls {len(controls)}, "
          f"double-coded {sum(r['double_code'] == 'yes' for r in infl + controls)}")


if __name__ == "__main__":
    main()
