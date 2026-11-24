import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import api_judge as A  # noqa: E402


class TestApiJudge(unittest.TestCase):
    def test_load_keys(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".apikey"
            f.write_text("# LLM\nA_KEY = abc\nB_KEY='x=y'\n\n", encoding="utf-8")
            self.assertEqual(A.load_keys(f), {"A_KEY": "abc", "B_KEY": "x=y"})

    def test_prob_from_logprobs(self):
        top = [{"token": "Yes", "logprob": math.log(0.6)}, {"token": " yes", "logprob": math.log(0.1)},
               {"token": "No", "logprob": math.log(0.3)}]
        p, m = A.prob_from_top(top, "Yes")
        self.assertAlmostEqual(p, 0.7)
        self.assertEqual(m, "logprobs")

    def test_prob_fallback(self):
        self.assertEqual(A.prob_from_top([], "No"), (0.0, "parsed"))
        self.assertEqual(A.prob_from_top([{"token": "Maybe", "logprob": 0.0}], "Yes"), (1.0, "parsed"))
        self.assertEqual(A.prob_from_top([], "Hmm")[1], "unparseable")


if __name__ == "__main__":
    unittest.main()
