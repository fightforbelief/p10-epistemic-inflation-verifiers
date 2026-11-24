import collections
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_audit_sheet as B  # noqa: E402


class TestAuditSheet(unittest.TestCase):
    def test_change_summary(self):
        self.assertEqual(B.change_summary("X may reduce Y.", "X will reduce Y."), "may → will")
        self.assertEqual(B.change_summary("Y was associated with Z.", "Y caused Z."), "was associated with → caused")
        self.assertEqual(B.change_summary("X reduced Y in mice.", "X reduced Y."), "[removed] in mice")

    def test_rows_cover_every_scored_inflation(self):
        infl, ctrl = B.build_rows()
        c = collections.Counter(r["edit"] for r in infl)
        self.assertEqual(dict(c), {"modal_strengthen": 103, "report_verb_upgrade": 81, "hedge_adverb_drop": 32,
                                   "causal_upgrade": 42, "scope_drop": 44, "quantifier_inflate": 27})
        self.assertEqual(collections.Counter(r["edit"] for r in ctrl), {"weaken": 40, "negate": 40})
        ids = [r["audit_id"] for r in infl + ctrl]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(sum(r["double_code"] == "yes" for r in infl), round(0.2 * 329))
        self.assertEqual([r["audit_id"] for r in B.build_rows()[0]], [r["audit_id"] for r in infl])  # deterministic


if __name__ == "__main__":
    unittest.main()
