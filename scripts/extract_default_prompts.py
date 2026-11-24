"""Extract the default faithfulness prompts of five RAG-eval libraries from their released
wheels.  Source files are only *parsed* (ast / json); no downloaded code is executed.
Runs on the Mac (spec preparation); output is a frozen spec the runner reads.

    python3 -I scripts/extract_default_prompts.py <wheels dir> specs/default_prompts_20261119.json

<wheels dir>/<pkg>/pkg.whl and <wheels dir>/<pkg>/src/ (unzipped wheel).
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from inspect import cleandoc
from pathlib import Path

VERS = {"ragas": "0.4.4", "trulens-feedback": "2.16.0", "deepeval": "4.3.4",
        "llama-index-core": "0.14.26", "arize-phoenix-evals": "3.10.0"}
MARK = "@@INPUT@@"


def _class(tree: ast.Module, name: str) -> ast.ClassDef:
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == name)


def _const(v):
    if isinstance(v, ast.Call) and getattr(v.func, "id", "") == "cleandoc":
        return cleandoc(ast.literal_eval(v.args[0]))
    return ast.literal_eval(v)


def _attrs(cls: ast.ClassDef) -> dict:
    out = {}
    for n in cls.body:
        tgt = n.target if isinstance(n, ast.AnnAssign) else (n.targets[0] if isinstance(n, ast.Assign) else None)
        if isinstance(tgt, ast.Name) and n.value is not None:
            try:
                out[tgt.id] = _const(n.value)
            except (ValueError, TypeError, SyntaxError):
                out[tgt.id] = n.value  # keep AST for non-literal values
    return out


def _fields(cls: ast.ClassDef) -> list[tuple[str, str, str]]:
    """(name, annotation source, Field description) for a pydantic model."""
    out = []
    for n in cls.body:
        if isinstance(n, ast.AnnAssign) and isinstance(n.value, ast.Call):
            desc = next(ast.literal_eval(k.value) for k in n.value.keywords if k.arg == "description")
            out.append((n.target.id, ast.unparse(n.annotation), desc))
    return out


def _call_to_obj(node):
    """Turn Model(field=..., ...) example constructors into plain dicts (recursively)."""
    if isinstance(node, ast.Call):
        return {k.arg: _call_to_obj(k.value) for k in node.keywords}
    if isinstance(node, ast.List):
        return [_call_to_obj(e) for e in node.elts]
    return ast.literal_eval(node)


def ragas(src: Path) -> dict:
    """Rebuild BasePrompt.to_string (ragas/prompt/metrics/base_prompt.py) with locally defined
    pydantic replicas of the models in collections/faithfulness/util.py."""
    import typing as t

    from pydantic import BaseModel, Field, create_model

    tree = ast.parse(src.read_text(encoding="utf-8"))
    models: dict[str, type[BaseModel]] = {}
    for name in ("StatementGeneratorInput", "StatementGeneratorOutput", "StatementFaithfulnessAnswer",
                 "NLIStatementInput", "NLIStatementOutput"):
        fields = {}
        for fname, ann, desc in _fields(_class(tree, name)):
            # whitelist of the annotations used in util.py (no eval of downloaded text)
            known = {"str": str, "int": int, "t.List[str]": t.List[str]}
            if "StatementFaithfulnessAnswer" in models:
                known["t.List[StatementFaithfulnessAnswer]"] = t.List[models["StatementFaithfulnessAnswer"]]
            typ = known[ann]
            fields[fname] = (typ, Field(..., description=desc))
        models[name] = create_model(name, __doc__=ast.get_docstring(_class(tree, name)), **fields)

    out = {}
    for key, pcls, inp, outp in (("statement_generator", "StatementGeneratorPrompt", "StatementGeneratorInput",
                                  "StatementGeneratorOutput"),
                                 ("nli_statement", "NLIStatementPrompt", "NLIStatementInput", "NLIStatementOutput")):
        a = _attrs(_class(tree, pcls))
        instruction = a["instruction"]
        ex_strs = []
        for idx, pair in enumerate(a["examples"].elts):
            i_obj = models[inp](**_call_to_obj(pair.elts[0]))
            o_raw = _call_to_obj(pair.elts[1])
            o_obj = models[outp].model_validate(o_raw)
            ex_strs.append(f"Example {idx + 1}\nInput: {i_obj.model_dump_json(indent=4)}\n"
                           f"Output: {o_obj.model_dump_json(indent=4)}")
        examples = "--------EXAMPLES-----------\n" + "\n\n".join(ex_strs)
        schema = json.dumps(models[outp].model_json_schema())
        out[key] = (f"{instruction}\nPlease return the output in a JSON format that complies with the following "
                    f"schema as specified in JSON Schema:\n{schema}Do not use single quotes in your response but "
                    f"double quotes,properly escaped with a backslash.\n\n{examples}\n-----------------------------"
                    f"\n\nNow perform the same with the following input\ninput: {MARK}\nOutput: ")
    out.update({"input_marker": MARK,
                "input_render": "model_dump_json(indent=4) of the input model == json.dumps(obj, indent=4, ensure_ascii=False)",
                "score": "mean(verdict) over generated statements"})
    return out


def trulens(src: Path) -> dict:
    a = _attrs(_class(ast.parse(src.read_text(encoding="utf-8")), "Groundedness"))
    likert = "0 to 3, where 0 is the lowest score according to the criteria and 3 is the highest possible score"
    criteria = a["criteria_template"].format(min_score=0, max_score=3)
    system = cleandoc(a["system_prompt_template"].format(output_space_prompt=likert, criteria=criteria,
                                                         additional_instructions=""))
    return {"system": system, "user": a["user_prompt"], "score": "score/3 (Likert 0-3)"}


def deepeval(root: Path) -> dict:
    T = json.loads((root / "deepeval/templates/metrics/templates.json").read_text(encoding="utf-8"))
    faith = {k: v for k, v in T.items() if "aithful" in k}
    return {"templates": faith, "fragments": {k: v for k, v in T["_fragments"].items() if "aithful" in k},
            "score": "fraction of verdicts in {yes, borderline} (penalize_ambiguous_claims=False default); "
                     "strict variant: fraction yes"}


def llamaindex(src: Path) -> dict:
    tree = ast.parse(src.read_text(encoding="utf-8"))
    tmpl = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "DEFAULT_EVAL_TEMPLATE")
    return {"template": ast.literal_eval(tmpl.value.args[0]), "score": "1 if 'yes' in response.lower() else 0"}


def phoenix(cfg_dir: Path) -> dict:
    out = {}
    for key, fn in (("faithfulness", "_faithfulness_classification_evaluator_config.py"),
                    ("hallucination", "_hallucination_classification_evaluator_config.py")):
        tree = ast.parse((cfg_dir / fn).read_text(encoding="utf-8"))
        content = next(ast.literal_eval(k.value) for n in ast.walk(tree) if isinstance(n, ast.Call)
                       for k in n.keywords if k.arg == "content")
        choices = next(ast.literal_eval(k.value) for n in ast.walk(tree) if isinstance(n, ast.Call)
                       for k in n.keywords if k.arg == "choices")
        out[key] = {"template": content, "choices": choices}
    out["call"] = "structured output {explanation, label} (include_explanation=True default), emulated via tool call"
    return out


def main() -> None:
    W, OUT = Path(sys.argv[1]), Path(sys.argv[2])
    spec = {"extracted": "2026-11-19", "note": "parsed from wheels, no package code executed",
            "provenance": {p: {"version": v, "wheel_sha256": hashlib.sha256((W / p / "pkg.whl").read_bytes()).hexdigest()}
                           for p, v in VERS.items()}}
    spec["ragas"] = ragas(W / "ragas/src/ragas/metrics/collections/faithfulness/util.py")
    spec["trulens"] = trulens(W / "trulens-feedback/src/trulens/feedback/templates/rag.py")
    spec["deepeval"] = deepeval(W / "deepeval/src")
    spec["llamaindex"] = llamaindex(W / "llama-index-core/src/llama_index/core/evaluation/faithfulness.py")
    spec["phoenix"] = phoenix(W / "arize-phoenix-evals/src/phoenix/evals/__generated__/classification_evaluator_configs")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
    print("ok", list(spec))


if __name__ == "__main__":
    main()
