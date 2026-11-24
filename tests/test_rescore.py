import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rescore_with_audit as R  # noqa: E402

L = lambda a, b, c: {"Q1": a, "Q2": b, "Q3": c, "Q4": "n/a"}


class TestRescore(unittest.TestCase):
    def test_sets(self):
        cases = {("ok", "yes", "no"): {"all", "nb", "valid", "valid_s", "lenient"},
                 ("broken", "yes", "no"): {"all"},
                 ("minor", "contested", "no"): {"all", "nb", "lenient"},
                 ("ok", "yes", "yes"): {"all", "nb", "valid_s", "warranted"}}
        for lab, want in cases.items():
            got = {s for s in ("all", "nb", "valid", "valid_s", "lenient", "warranted") if R.in_set(s, L(*lab))}
            self.assertEqual(got, want)

    def test_threshold_hides_partial_deduction(self):
        pairs = [(1.0, 2 / 3)] * 4  # TruLens 3 -> 2
        self.assertEqual(R.stats(pairs, 0.5)["drop"], 0.0)
        self.assertEqual(R.stats(pairs, 0.999)["drop"], 1.0)
        self.assertEqual(R.stats(pairs, 0.5)["score_lower_than_identity"], 1.0)


if __name__ == "__main__":
    unittest.main()
