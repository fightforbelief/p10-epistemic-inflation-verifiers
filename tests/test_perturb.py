import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import perturb as P  # noqa: E402


class TestInflations(unittest.TestCase):
    def test_modal(self):
        self.assertEqual(P.modal_strengthen("Metformin may reduce tumour growth."),
                         "Metformin will reduce tumour growth.")
        self.assertIsNone(P.modal_strengthen("Metformin reduced tumour growth."))

    def test_report_verb(self):
        self.assertEqual(P.report_verb_upgrade("These data suggest that IL-6 drives fibrosis."),
                         "These data demonstrate that IL-6 drives fibrosis.")
        self.assertEqual(P.report_verb_upgrade("Results indicated that X binds Y."),
                         "Results proved that X binds Y.")

    def test_hedge_adverb(self):
        self.assertEqual(P.hedge_adverb_drop("This is potentially a novel target."),
                         "This is a novel target.")
        self.assertEqual(P.hedge_adverb_drop("The effect appears to be dose dependent."),
                         "The effect is dose dependent.")
        self.assertEqual(P.hedge_adverb_drop("Patients are likely to benefit."),
                         "Patients will benefit.")
        self.assertIsNone(P.hedge_adverb_drop("The drug lowered blood pressure."))

    def test_causal(self):
        self.assertEqual(P.causal_upgrade("Smoking was independently associated with higher mortality."),
                         "Smoking caused higher mortality.")
        self.assertEqual(P.causal_upgrade("Obesity is linked to insulin resistance."),
                         "Obesity causes insulin resistance.")

    def test_scope(self):
        self.assertEqual(P.scope_drop("Deletion of Foxp3 caused autoimmunity in mice."),
                         "Deletion of Foxp3 caused autoimmunity.")
        self.assertEqual(P.scope_drop("The compound inhibited growth in vitro, but not in vivo."),
                         "The compound inhibited growth, but not in vivo.")
        self.assertEqual(P.scope_drop("Exercise improved memory in aged rats."),
                         "Exercise improved memory.")
        self.assertIsNone(P.scope_drop("Exercise improved memory in humans."))

    def test_quantifier(self):
        self.assertEqual(P.quantifier_inflate("Some patients developed rash."),
                         "All patients developed rash.")


class TestV1AuditRegressions(unittest.TestCase):
    """Failures found in the pilot_v0 edit audit sheet (2026-11-19)."""

    def test_comparative_likely_untouched(self):
        self.assertIsNone(P.hedge_adverb_drop(
            "Persons with high distress were more likely to have emotional difficulties."))

    def test_scope_not_in_coordination(self):
        self.assertIsNone(P.scope_drop("CPI is a big challenge for in vitro or in vivo experiments."))

    def test_quantifier_skips_negation_and_methods(self):
        self.assertIsNone(P.quantifier_inflate("Expression was not satisfied in a subset of melanomas."))
        self.assertIsNone(P.quantifier_inflate("Samples were collected for some biochemical parameters."))

    def test_modal_skips_could_and_impersonal(self):
        self.assertIsNone(P.modal_strengthen("Sty3 could discriminate between conformations."))
        self.assertIsNone(P.modal_strengthen("It might be expected that defects arise in all tissues."))
        self.assertEqual(P.modal_strengthen("Nitric oxide may have promise as therapy."),
                         "Nitric oxide will have promise as therapy.")


class TestControls(unittest.TestCase):
    def test_weaken_keeps_acronym(self):
        self.assertEqual(P.weaken("BRCA1 loss drives tumours."),
                         "It is possible that BRCA1 loss drives tumours.")
        self.assertEqual(P.weaken("The drug works."), "It is possible that the drug works.")

    def test_negate(self):
        self.assertEqual(P.negate("The drug was effective."), "The drug was not effective.")
        self.assertIsNone(P.negate("The drug lowered pressure."))

    def test_variants_and_labels(self):
        v = P.variants("These results suggest that statins may reduce stroke risk in mice.")
        for k in ("identity", "weaken", "negate", "modal_strengthen", "report_verb_upgrade", "scope_drop"):
            self.assertIn(k, v)
        self.assertTrue(all(k in P.EXPECTED_SUPPORTED for k in v))
        self.assertEqual(P.n_inflations("The sky is blue."), 0)


if __name__ == "__main__":
    unittest.main()
