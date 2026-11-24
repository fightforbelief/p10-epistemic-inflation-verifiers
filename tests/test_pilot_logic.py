"""Synthetic-fixture tests for selection, pairing and summary maths (no torch, no downloads)."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pilot_score as S  # noqa: E402

CORPUS = [
    {"doc_id": 1, "abstract": ["We studied mice.", "These data suggest that drug A may lower glucose in mice."]},
    {"doc_id": 2, "abstract": ["Obesity was strongly associated with insulin resistance in this cohort of adults."]},
    {"doc_id": 3, "abstract": ["The sky is blue and nothing here is hedged at all today."]},
]


class TestLogic(unittest.TestCase):
    def test_select_is_deterministic_and_filters(self):
        a, b = S.select(CORPUS, 10), S.select(CORPUS, 10)
        self.assertEqual(a, b)
        self.assertEqual({r["doc_id"] for r in a}, {1, 2})

    def test_pairs_have_both_premises(self):
        pairs = S.build_pairs(S.select(CORPUS, 10))
        conds = {(p["doc_id"], p["edit"], p["premise_cond"]) for p in pairs}
        self.assertIn((1, "identity", "abstract"), conds)
        self.assertIn((2, "causal_upgrade", "sentence"), conds)

    def test_auroc(self):
        self.assertAlmostEqual(S.auroc(np.array([.9, .8]), np.array([.1, .2])), 1.0)
        self.assertAlmostEqual(S.auroc(np.array([.5, .5]), np.array([.5, .5])), 0.5)

    def test_summary_blind_verifier(self):
        pairs = S.build_pairs(S.select(CORPUS, 10))
        rows = [{**p, "verifier": "blind", "p": 0.0 if p["edit"] == "negate" else 0.95} for p in pairs]
        summ = S.summarise(rows, "blind", n_boot=50)
        infl = [r for r in summ if r["edit"] in S.P.INFLATIONS]
        self.assertTrue(infl and all(r["support_rate_drop_vs_identity"] == 0 for r in infl))
        neg = [r for r in summ if r["edit"] == "negate"]
        self.assertTrue(all(r["support_rate_drop_vs_identity"] == 1 for r in neg))


if __name__ == "__main__":
    unittest.main()
