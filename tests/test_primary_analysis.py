import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import primary_analysis as p


def fixture():
    rows = []
    for i in range(350):
        row = dict(doc_id=i, edit=p.MODAL if i < 200 else p.HEDGE, valid=True, has_negate=True,
                   has_weaken=True, scores={})
        for c in p.configurations():
            limited = c.endswith(("sentence", "strength"))
            row["scores"][c] = dict(identity=1., negate=0., weaken=1., focal=float(i % 10 < (2 if limited else 9)))
        rows.append(row)
    return rows


class TestPrimary(unittest.TestCase):
    def test_h1_critical_counts(self):
        for n, critical in [(200,156), (150,119)]:
            self.assertLessEqual(p.cp_lower(critical-1,n), .70)
            self.assertGreater(p.cp_lower(critical,n), .70)
    def test_six_decisions(self):
        r = p.decide(fixture())
        self.assertEqual(len(r["hypotheses"]), 6)
        self.assertTrue(all(h["met"] for h in r["hypotheses"].values()))
    def test_guard_missing_and_duplicate(self):
        rows = fixture()
        for r in rows:
            r["scores"]["qwen/strength"]["identity"] = None
        self.assertFalse(p.decide(rows)["hypotheses"]["H3/qwen"]["met"])
        with self.assertRaises(ValueError):
            p.decide(rows + rows[:1])
    def test_bad_negative_control_and_prompt_cost(self):
        rows = fixture()
        for r in rows:
            r["scores"][p.MINICHECK[0]+"/sentence"]["negate"] = 1
            r["scores"]["deepseek/strength"]["weaken"] = 0
        h = p.decide(rows)["hypotheses"]
        self.assertFalse(h["H2/"+p.MINICHECK[0]]["met"])
        self.assertFalse(h["H3/deepseek"]["met"])
    def test_degenerate(self):
        r = p.paired(list(range(200)), lambda _: 1, lambda _: 1)
        self.assertLess(r["lower"],0)
        self.assertEqual(r["gains"],r["losses"])
