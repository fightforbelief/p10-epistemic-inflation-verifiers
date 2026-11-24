import sys
import unittest
from pathlib import Path
from openpyxl import Workbook
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from read_confirmation_labels import SHEETS, read


def fixture():
    wb=Workbook()
    wb.active.title="填写说明"
    rows=[]
    for e,s in SHEETS.items():
        ws=wb.create_sheet(s)
        ws.append(list("ABCDEFGHI"))
        is_ctrl=e in ("weaken","negate")
        for i in range(201 if s=="Modal" else 1):
            id_=f"{e}-{i}"
            rows.append(dict(id=id_,doc_id=len(rows),edit=e,sent_idx=0,source="Text A",edited="Text B",abstract="Text C"))
            vals=["as_intended",None,None,None] if is_ctrl else ["ok","yes","no","generic" if s=="Scope" else None]
            if s=="Modal" and i==200: vals=[None]*4
            ws.append([id_,"原句\nText A\n\n改写\nText B","Text C",*vals,None,None])
    return wb,rows


class TestReturn(unittest.TestCase):
    def test_stop_and_context(self):
        wb,rows=fixture()
        self.assertEqual(len(read(wb,rows)),len(rows)-1)
        wb["Modal"]["D202"]="ok"
        with self.assertRaisesRegex(ValueError,"beyond stop"):read(wb,rows)
        wb["Modal"]["D202"]=None
        wb["Causal"]["C2"]="Changed abstract"
        with self.assertRaisesRegex(ValueError,"text differs"):read(wb,rows)
    def test_scope_and_controls(self):
        wb,rows=fixture()
        wb["Scope"]["G2"]="existential"
        self.assertFalse(next(r["valid"] for r in read(wb,rows) if r["edit"]=="scope_drop"))
        wb["Negate"]["D2"]=None
        with self.assertRaisesRegex(ValueError,"C1"):read(wb,rows)
