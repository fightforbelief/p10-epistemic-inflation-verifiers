import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from primary_ledger import schedule, combine, fingerprint


class TestLedger(unittest.TestCase):
    def test_completion_and_separation(self):
        item = dict(id="x",edit="modal_strengthen",sent_idx=0,doc_id=4,source="The morning service may arrive early tomorrow.",edited="The morning service will arrive early tomorrow.",abstract="The morning service may arrive early tomorrow.")
        docs,calls = schedule([item],[dict(item,valid=True)])
        self.assertEqual(sum(c["repeat"] for c in calls)*2,len(calls))
        rows=[dict(id=c["id"],schedule_sha256=fingerprint(calls),p=None) for c in calls]
        self.assertFalse(any(h["met"] for h in combine(docs,calls,rows)["hypotheses"].values()))
        for bad in (rows[:-1],rows+rows[:1],[dict(rows[0],schedule_sha256="wrong")]+rows[1:]):
            with self.assertRaises(ValueError):
                combine(docs,calls,bad)
