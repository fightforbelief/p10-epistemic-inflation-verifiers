import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from confirmation_sample import draw


class TestSampling(unittest.TestCase):
    def test_exclusion_core_and_stability(self):
        docs = [{"doc_id": i, "abstract": ["The station may record a larger change during summer.",
                                            "The station is open every day in this cohort."]} for i in range(25)]
        args = ({0,1}, {"modal_strengthen": 12}, {"modal_strengthen": 4}, 2)
        rows = draw(docs, *args)
        self.assertEqual(rows, draw(list(reversed(docs)), *args))
        ids = [r["doc_id"] for r in rows[:12]]
        self.assertEqual(len(set(ids)),12)
        self.assertFalse({0,1}.intersection(ids))
        self.assertTrue(all(r["doc_id"] in ids[:4] for r in rows[12:]))
