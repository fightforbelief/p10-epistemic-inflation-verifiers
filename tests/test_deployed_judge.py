import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import deployed_judge as D  # noqa: E402

SPEC = json.loads((ROOT / "specs" / "default_prompts_20261119.json").read_text(encoding="utf-8"))


class FakeClient:
    """Returns canned replies in order and records prompts."""

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def text(self, prompt, system=None, max_tokens=2048):
        self.prompts.append((system, prompt))
        return self.replies.pop(0)

    def chat(self, messages, max_tokens=2048, tools=None, tool_choice=None):
        self.prompts.append(messages)
        return self.replies.pop(0)


class TestHelpers(unittest.TestCase):
    def test_jinja_lite(self):
        t = "a {% if multimodal %}M{% else %}T{% endif %} b{% if not multimodal %} {{ _f.x }}{% endif %} {{ y }}"
        self.assertEqual(D.jinja_lite(t, multimodal=False, _f={"x": "FX"}, y="Y"), "a T b FX Y")

    def test_parse_json(self):
        self.assertEqual(D.parse_json('```json\n{"a": [1, "}"]}\n```'), {"a": [1, "}"]})
        self.assertEqual(D.parse_json('Sure: {"s": 2} trailing'), {"s": 2})
        self.assertIsNone(D.parse_json("no json"))
        # seen in deepseek-v4-pro deepeval verdicts: final brace missing
        self.assertEqual(D.parse_json('{\n"verdicts": [\n{"verdict": "yes"}\n]'), {"verdicts": [{"verdict": "yes"}]})


class TestPipelines(unittest.TestCase):
    def test_spec_has_all_libraries(self):
        for k in ("ragas", "trulens", "deepeval", "llamaindex", "phoenix"):
            self.assertIn(k, SPEC)
        self.assertIn("DIRECTLY CONTRADICTS", SPEC["deepeval"]["fragments"]["faithfulness_verdicts_guidelines_text_only"])

    def test_ragas_flow(self):
        c = FakeClient(['{"statements": ["S1", "S2"]}',
                        '{"statements": [{"statement": "S1", "reason": "r", "verdict": 1},'
                        ' {"statement": "S2", "reason": "r", "verdict": 0}]}'])
        r = D.Pipelines(SPEC, c).ragas("CTX", "ANS")
        self.assertEqual(r["p"], 0.5)
        self.assertIn('"answer": "ANS"', c.prompts[0][1])
        self.assertIn('"context": "CTX"', c.prompts[1][1])
        self.assertNotIn("@@INPUT@@", c.prompts[1][1])

    def test_deepeval_borderline_passes_by_default(self):
        c = FakeClient(['{"truths": ["T1"]}', '{"claims": ["C1", "C2"]}',
                        '{"verdicts": [{"verdict": "yes"}, {"verdict": "borderline", "reason": "x"}]}'])
        r = D.Pipelines(SPEC, c).deepeval("CTX", "ANS", "doc1")
        self.assertEqual((r["p"], r["p_strict"]), (1.0, 0.5))
        verdict_prompt = c.prompts[2][1]
        self.assertIn("T1", verdict_prompt)
        self.assertIn("['C1', 'C2']", verdict_prompt)
        self.assertNotIn("{%", verdict_prompt)
        self.assertNotIn("{{", verdict_prompt)

    def test_trulens_and_llamaindex(self):
        c = FakeClient(['{"criteria": "x", "supporting_evidence": "y", "score": 2}', "YES"])
        P = D.Pipelines(SPEC, c)
        self.assertAlmostEqual(P.trulens("CTX", "ANS")["p"], 2 / 3)
        self.assertEqual(P.llamaindex("CTX", "ANS")["p"], 1.0)
        self.assertIn("STATEMENT: ANS", c.prompts[0][1])

    def test_phoenix_labels(self):
        call = lambda lab: {"tool_calls": [{"function": {"arguments": json.dumps({"explanation": "e", "label": lab})}}]}
        c = FakeClient([call("unfaithful"), call("grounded")])
        P = D.Pipelines(SPEC, c)
        self.assertEqual(P.phoenix_faithfulness("CTX", "ANS")["p"], 0.0)
        self.assertEqual(P.phoenix_hallucination("CTX", "ANS")["p"], 1.0)
        self.assertNotIn("{{", c.prompts[1][0]["content"])


if __name__ == "__main__":
    unittest.main()
