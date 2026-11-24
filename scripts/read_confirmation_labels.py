"""Verify a blinded workbook against the exact issued roster, then export human labels."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook
from confirmation_sample import TARGETS

SHEETS = {"modal_strengthen":"Modal", "hedge_adverb_drop":"Hedge", "scope_drop":"Scope",
          "causal_upgrade":"Causal", "quantifier_inflate":"Quantifier", "weaken":"Weaken", "negate":"Negate"}


def read(wb, roster):
    grouped = defaultdict(list)
    for row in roster:
        grouped[row["edit"]].append(row)
    labels = []
    if set(wb.sheetnames) != {"填写说明", *SHEETS.values()}:
        raise ValueError("Workbook sheets differ from the issued packet")
    for edit, sheet in SHEETS.items():
        ws = wb[sheet]
        if ws.max_row != 1+len(grouped[edit]):
            raise ValueError(f"{sheet}: row count differs from the issued packet")
        valid = 0
        for r, row in zip(grouped[edit], ws.iter_rows(min_row=2,values_only=True), strict=True):
            id_, pair, abstract, q1, q2, q3, q4, _, note = row[:9]
            if (id_, pair, abstract) != (r["id"], "原句\n"+r["source"]+"\n\n改写\n"+r["edited"], r["abstract"]):
                raise ValueError(f"{sheet} {r['id']}: ID, order or text differs")
            if valid == TARGETS.get(edit, -1):
                if any(v is not None for v in (q1,q2,q3,q4,note)):
                    raise ValueError(f"{id_}: unexpected label beyond stop")
                continue
            entry = {k:r[k] for k in ("id","edit","doc_id","sent_idx")}
            if edit in ("weaken","negate"):
                if q1 not in ("as_intended","not_as_intended","broken") or any((q2,q3,q4)):
                    raise ValueError(f"{id_}: incomplete or invalid C1")
                entry["C1"] = q1
            else:
                if q1 not in ("ok","minor","broken"):
                    raise ValueError(f"{id_}: incomplete or invalid Q1")
                if q1 == "broken":
                    if any((q2,q3,q4)):
                        raise ValueError(f"{id_}: fill only Q1 when broken")
                elif (q2 not in ("yes","no","contested") or q3 not in ("yes","no","unclear")
                      or (q4 not in ("generic","existential","ambiguous") if edit=="scope_drop" else q4 is not None)):
                    raise ValueError(f"{id_}: incomplete or invalid Q2/Q3/Q4")
                eligible = q1 in ("ok","minor") and q2=="yes" and q3=="no" and (edit!="scope_drop" or q4=="generic")
                valid += int(eligible)
                entry.update(Q1=q1,Q2=q2,Q3=q3,Q4=q4,valid=eligible)
            labels.append(entry)
    return labels


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ("roster","workbook","out"):
        ap.add_argument(key,type=Path)
    ap.add_argument("--roster-sha256", required=True)
    a = ap.parse_args()
    if hashlib.sha256(a.roster.read_bytes()).hexdigest() != a.roster_sha256:
        raise ValueError("Wrong roster")
    wb = load_workbook(a.workbook,read_only=True,data_only=False)
    labels = read(wb, [json.loads(l) for l in a.roster.read_text(encoding="utf-8").splitlines()])
    with a.out.open("x",encoding="utf-8",newline="\n") as f:
        for label in labels:
            f.write(json.dumps(label)+"\n")
    print("workbook", hashlib.sha256(a.workbook.read_bytes()).hexdigest(), "labels", hashlib.sha256(a.out.read_bytes()).hexdigest())
