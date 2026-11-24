import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import perturb as V1  # noqa: E402
import perturb_v2 as V2  # noqa: E402


class TestModal(unittest.TestCase):
    def test_plain_claims_kept(self):
        self.assertEqual(V2.modal_strengthen("Metformin may reduce tumour growth."), "Metformin will reduce tumour growth.")
        self.assertIsNotNone(V2.modal_strengthen("Nitric oxide may have promise as a therapy."))  # 'have' + noun is fine

    def test_skips(self):
        for s in ("The virus may have originated from a recombination event.",
                  "Several genes, which might participate in reprogramming, were found.",
                  "The mechanism is unclear but may be related to magnesium deficiency.",
                  "We hypothesized that Notch signaling might play roles in cancer.",
                  "PURPOSE Pleural effusion may represent an early phase of malignancy.",
                  "The allele may differ in patients, indicating that it may be protective.",
                  "We explain how what is learned in animals may provide insight."):
            self.assertIsNone(V2.modal_strengthen(s), s)


class TestScope(unittest.TestCase):
    def test_whole_phrase_removed(self):
        self.assertEqual(V2.scope_drop("The drug lowered blood pressure in a rat model."), "The drug lowered blood pressure.")
        self.assertEqual(V2.scope_drop("Loss of Foxp3 caused autoimmunity in mice."), "Loss of Foxp3 caused autoimmunity.")

    def test_skips(self):
        for s in ("Results are related to our observations in animal model studies.", "VEGF enhanced maturation in mouse femur fractures.",
                  "Cytokines in rodent brain are region-specific.", "Scavenging activities were observed in vitro.",
                  "Liraglutide elicits effects in mice with severe obesity.", "The drug slowed ageing in mice, and rats lived longer.",
                  "PURPOSE We assessed effects on renal damage in a rat model."):
            self.assertIsNone(V2.scope_drop(s), s)


class TestOthers(unittest.TestCase):
    def test_hedge(self):
        self.assertIsNone(V2.hedge_adverb_drop("It is likely that RNA never lost its other capacities."))
        self.assertEqual(V2.hedge_adverb_drop("This is possibly a novel target."), "This is a novel target.")

    def test_causal(self):
        self.assertIsNone(V2.causal_upgrade("TLR-2 is associated with larger plaques, while CD14 associate with smaller."))
        self.assertIsNone(V2.causal_upgrade("Cells pass through phases, each of which is associated with distinct factors."))
        self.assertEqual(V2.causal_upgrade("Smoking was associated with higher mortality."), "Smoking caused higher mortality.")

    def test_quantifier(self):
        self.assertIsNone(V2.quantifier_inflate("That period has seen some of the most dramatic changes."))
        self.assertIsNone(V2.quantifier_inflate("All animals have some method to compensate."))
        self.assertEqual(V2.quantifier_inflate("Some patients developed rash."), "All patients developed rash.")

    def test_controls(self):
        self.assertIsNone(V2.weaken("Thus, collagen regulates signaling."))
        self.assertIsNone(V2.weaken("OBJECTIVES To determine if vaccination prevents events."))
        self.assertIsNotNone(V2.weaken("BRCA1 loss drives tumours."))
        self.assertIsNone(V2.negate("It is hoped that research may improve outcome."))
        self.assertIsNone(V2.negate("The gene is a regulator whose loss lowers the threshold."))
        self.assertEqual(V2.negate("The drug was effective."), "The drug was not effective.")
        self.assertEqual(V2.negate("SIV may undergo adaptation."), "SIV will not undergo adaptation.")  # not 'may not'
        self.assertEqual(V2.negate("The assay can detect virus."), "The assay cannot detect virus.")
        self.assertIsNone(V2.negate("Some patients have avenin-reactive T-cells."))
        self.assertIsNone(V2.weaken("Conclusions  We conclude that X drives Y."))
        self.assertIsNone(V2.weaken("We demonstrate that X drives Y."))

    def test_dev_findings(self):
        self.assertIsNone(V2.hedge_adverb_drop("What is the efficacy of possibly low-dose aspirin?"))
        self.assertIsNone(V2.causal_upgrade("A reduced risk was associated with high SHBG levels."))
        self.assertIsNone(V2.causal_upgrade("Ciliopathies are associated with abnormal shedding or with abnormal interactions."))
        self.assertIsNone(V2.quantifier_inflate("At least some bind to several targets."))
        self.assertIsNone(V2.quantifier_inflate("The system shows some form of memory."))
        self.assertIsNone(V2.scope_drop("Imprinting has so far only been documented in mice."))


class TestAgainstPilot(unittest.TestCase):
    def test_v2_only_skips(self):
        """On every audited pilot row v2 either reproduces the v1 text or skips it."""
        fns = {**V2.CONTROLS, **V2.INFLATIONS}
        for d in map(json.loads, (ROOT / "audit/edit_audit_v1.jsonl").read_text(encoding="utf-8").splitlines()):
            if d["edit"] in fns and d["edit"] != "negate":  # v2 negate changes modals on purpose
                self.assertIn(fns[d["edit"]](d["source"]), (None, d["edited"]))
        self.assertNotIn("report_verb_upgrade", V2.variants("Data suggest that X binds Y."))
        self.assertIn("report_verb_upgrade", V1.variants("Data suggest that X binds Y."))


if __name__ == "__main__":
    unittest.main()
