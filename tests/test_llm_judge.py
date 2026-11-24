import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import llm_judge as J  # noqa: E402


class FakeTok:
    vocab = {"Yes": 1, " Yes": 2, "yes": 3, "No": 4, " No": 5, "no": 6}

    def encode(self, s, add_special_tokens=False):
        return [self.vocab[s]] if s in self.vocab else [9, 9]


class TestLLMJudge(unittest.TestCase):
    def test_yes_prob(self):
        self.assertAlmostEqual(J.yes_prob(0.0, 0.0), 0.5)
        self.assertGreater(J.yes_prob(3.0, -1.0), 0.95)
        self.assertAlmostEqual(J.yes_prob(1000.0, 0.0), 1.0)  # no overflow

    def test_answer_ids(self):
        ys, ns = J.answer_token_ids(FakeTok())
        self.assertEqual(ys, [1, 2, 3])
        self.assertEqual(ns, [4, 5, 6])

    def test_messages_contain_pair(self):
        for p in J.PROMPTS:
            m = J.build_messages(p, "PREMISE_X", "CLAIM_Y")
            self.assertEqual(m[0]["role"], "system")
            self.assertIn("PREMISE_X", m[1]["content"])
            self.assertIn("CLAIM_Y", m[1]["content"])
        self.assertIn("more strongly", J.PROMPTS["strength"])
        self.assertNotIn("certainty", J.PROMPTS["generic"])


if __name__ == "__main__":
    unittest.main()
