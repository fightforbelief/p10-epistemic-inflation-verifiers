"""Rule-based minimal-pair edits for epistemic-strength stress tests.

Every edit takes one source sentence and returns an edited claim, or None when
the rule does not apply.  Inflation edits make the claim *stronger* than the
source (should NOT be judged supported by a strength-aware verifier).
Controls: IDENTITY and WEAKEN should be supported; NEGATE should not.

Stdlib only, so it can be tested on any interpreter.
"""
from __future__ import annotations

import re
from typing import Callable, Dict, Optional

Edit = Callable[[str], Optional[str]]

_FLAGS = re.IGNORECASE


def _sub_once(pattern: str, repl, s: str) -> Optional[str]:
    out, n = re.subn(pattern, repl, s, count=1, flags=_FLAGS)
    return out if n else None


def _keep_case(src: str, word: str) -> str:
    return word[:1].upper() + word[1:] if src[:1].isupper() else word


def _tidy(s: str) -> str:
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+([,.;:)])", r"\1", s)
    s = re.sub(r"\(\s*\)", "", s)
    return s.strip()


# ---------------------------------------------------------------- inflation

def modal_strengthen(s: str) -> Optional[str]:
    """Epistemic may / might + verb  ->  will + verb.

    v1: 'could' dropped (usually ability, not hedging); impersonal 'it may/might be'
    (e.g. 'it might be expected') skipped.
    """
    return _sub_once(r"(?<!\bit )\b(may|might)(\s+(?:not\s+)?[a-z])",
                     lambda m: _keep_case(m.group(1), "will") + m.group(2), s)


_REPORT = {
    "suggest": "demonstrate", "suggests": "demonstrates", "suggested": "demonstrated",
    "indicate": "prove", "indicates": "proves", "indicated": "proved",
    "imply": "establish", "implies": "establishes", "implied": "established",
}


def report_verb_upgrade(s: str) -> Optional[str]:
    """suggest/indicate/imply that  ->  demonstrate/prove/establish that."""
    pat = r"\b(" + "|".join(sorted(_REPORT, key=len, reverse=True)) + r")\s+that\b"
    return _sub_once(pat, lambda m: _keep_case(m.group(1), _REPORT[m.group(1).lower()]) + " that", s)


def hedge_adverb_drop(s: str) -> Optional[str]:
    """Delete hedging adverbs; 'appear(s) to be' -> 'is/are'; 'is likely to' -> 'will'."""
    out = s
    out = re.sub(r"\b(is|are) (?:likely|unlikely) to\b",
                 lambda m: "will" if "un" not in m.group(0) else "will not", out, flags=_FLAGS)
    out = re.sub(r"\bappears to be\b", "is", out, flags=_FLAGS)
    out = re.sub(r"\bappear to be\b", "are", out, flags=_FLAGS)
    # v1: never touch comparative 'more/most/less/as likely' ('were more likely to' is a result, not a hedge)
    out = re.sub(r"(?<!\bmore )(?<!\bmost )(?<!\bless )(?<!\bas )"
                 r"\b(possibly|potentially|probably|perhaps|presumably|putatively|likely)\s+(?!to\b)",
                 "", out, flags=_FLAGS)
    if out == s:
        return None
    out = _tidy(out)
    return out[:1].upper() + out[1:]


_CAUSAL = {"is": "causes", "are": "cause", "was": "caused", "were": "caused",
           "has been": "causes", "have been": "cause"}


def causal_upgrade(s: str) -> Optional[str]:
    """'<be> (adv)? associated/correlated with | linked to'  ->  causes/caused."""
    pat = (r"\b(has been|have been|is|are|was|were)\s+"
           r"(?:(?:significantly|positively|negatively|inversely|independently|strongly|closely)\s+)?"
           r"(?:associated with|correlated with|linked (?:to|with))\b")
    return _sub_once(pat, lambda m: _CAUSAL[m.group(1).lower()], s)


_SCOPE = (
    r",?\s+in (?:a |an |the )?(?:(?:male|female|adult|aged|young|old|transgenic|knockout|diabetic|obese)\s+)?"
    r"(?:mice|mouse|rats?|murine|rodents?|zebrafish|primates?|monkeys?|pigs?|dogs?|animals?|cell lines?|"
    r"cultured cells|vitro|this cohort|our cohort|this sample|our sample|this population|this study population|"
    r"(?:mouse|rat|animal|murine|rodent) models?(?: of [a-z\- ]+?)?)"
    # v1: not inside a coordination ('in vitro or in vivo'), and not after 'for'/'of' (argument, not scope)
    r"(?=[,.;:)]|\s(?!or\b|and\b)|$)"
)

_NEG = re.compile(r"\b(not|no|never|neither|nor|without|fail(?:ed|s)? to)\b", _FLAGS)


def scope_drop(s: str) -> Optional[str]:
    """Delete restricting scope phrases such as 'in mice', 'in vitro', 'in this cohort'."""
    m = re.search(_SCOPE, s, flags=_FLAGS)
    if not m or re.search(r"\b(?:for|of|and|or)\s*$", s[:m.start()], flags=_FLAGS):
        return None
    return _tidy(s[:m.start()] + s[m.end():])


def quantifier_inflate(s: str) -> Optional[str]:
    """'some / a subset of / a proportion of / a minority of X' -> 'all X'.

    v1: skipped in sentences with negation (inflation direction flips under 'not')
    and in methods sentences ('collected', 'measured', ...), which are not claims.
    """
    if _NEG.search(s) or re.search(r"\b(collected|measured|determined|recruited|enrolled|analy[sz]ed)\b", s, _FLAGS):
        return None
    return _sub_once(r"\b(some|a subset of|a proportion of|a minority of|a fraction of)\s+",
                     lambda m: _keep_case(m.group(1), "all") + " ", s)


INFLATIONS: Dict[str, Edit] = {
    "modal_strengthen": modal_strengthen,
    "report_verb_upgrade": report_verb_upgrade,
    "hedge_adverb_drop": hedge_adverb_drop,
    "causal_upgrade": causal_upgrade,
    "scope_drop": scope_drop,
    "quantifier_inflate": quantifier_inflate,
}

# ---------------------------------------------------------------- controls


def identity(s: str) -> Optional[str]:
    return s


def weaken(s: str) -> Optional[str]:
    """Logically weaker claim: 'It is possible that <s>'.  Entailed by s."""
    body = s.rstrip(".")
    first = body.split(" ", 1)[0]
    # keep capitalisation of acronyms / proper names (e.g. 'BRCA1', 'IL-6')
    if not (len(first) > 1 and (first[1:2].isupper() or any(c.isdigit() for c in first))):
        body = body[:1].lower() + body[1:]
    return f"It is possible that {body}."


def negate(s: str) -> Optional[str]:
    """Insert 'not' after the first auxiliary / copula; positive control."""
    return _sub_once(r"\b(is|are|was|were|may|might|can|could|will|did|does|do|has|have|had)\b(?!\s+not\b)",
                     lambda m: m.group(1) + " not", s)


CONTROLS: Dict[str, Edit] = {"identity": identity, "weaken": weaken, "negate": negate}

EXPECTED_SUPPORTED = {"identity": True, "weaken": True, "negate": False,
                      **{k: False for k in INFLATIONS}}


def variants(sentence: str) -> Dict[str, str]:
    """All applicable edits for one sentence (controls always present when they apply)."""
    out: Dict[str, str] = {}
    for name, fn in {**CONTROLS, **INFLATIONS}.items():
        v = fn(sentence)
        if v is not None and (name == "identity" or v != sentence):
            out[name] = v
    return out


def n_inflations(sentence: str) -> int:
    return sum(1 for fn in INFLATIONS.values() if fn(sentence) not in (None, sentence))
