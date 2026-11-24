"""Rule set v2 for the formal protocol (docs/PROTOCOL_DRAFT_v0.2).

v1 (perturb.py) stays untouched so the pilot remains reproducible.  v2 only *skips* more
sentences or matches longer phrases; every edit it emits is produced by the same substitution
as v1, except scope_drop, which removes the whole phrase ('in a rat model', not 'in a rat').
report_verb_upgrade is dropped (70/81 pilot edits were warranted by the abstract).
Tuned only on the 300 pilot documents; no model score was consulted.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

import perturb as V1

_F = re.IGNORECASE
_has = lambda pat, s: re.search(pat, s, _F) is not None

# PURPOSE/OBJECTIVE/AIM sentences and statements of what was studied are not claims
_NONCLAIM = (r"^\s*(?:purpose|objectives?|aims?|methods?|design|setting|rationale)\b|"
             r"\b(?:we|study|studies|authors)\s+(?:also\s+|then\s+|will\s+(?:also\s+)?)?"
             r"(?:assess|assessed|investigate|investigated|examine|examined|evaluate|evaluated|aim|aimed|sought|"
             r"designed|discuss|discussed|review|reviewed|studied|describe)\b|\bwere studied\b|\bare (?:discussed|described|reviewed)\b|\b(?:we|authors?)\s+(?:measured|screened|selected|searched)\b|\bscreened all\b|\?\s*$")
_UNSETTLED = (r"\b(?:unclear|unknown|unresolved|not (?:well|fully|completely|yet) understood|poorly understood|"
              r"not (?:yet )?(?:known|clear)|remains? to be|whether|hypothesi[sz]\w*|postulat\w*|speculat\w*|it is hoped)\b")


def modal_strengthen(s: str) -> Optional[str]:
    """may/might -> will, skipping contexts where 'will' is ungrammatical or self-contradictory."""
    if _has(_NONCLAIM, s) or _has(_UNSETTLED, s):
        return None
    if len(re.findall(r"\b(?:may|might)\b", s, _F)) != 1:            # a second modal leaves the claim hedged
        return None
    if _has(r"\b(?:which|that|what|who|how|why)\s+(?:may|might)\b", s):  # relative / embedded question
        return None
    if _has(r"\b(?:may|might)\s+(?:not\s+)?(?:\w+ly\s+|also\s+)?have\s+(?:also\s+|\w+ly\s+)?"
            r"(?:been|had|arisen|begun|grown|led|made|lost|found|shown|come|become|\w{3,}ed|\w{3,}en)\b", s):
        return None                                                   # perfect: 'may have originated'
    if _has(r"\bhow\b.{0,120}\b(?:may|might)\b|\bsuggestions? that\b", s):
        return None
    return V1.modal_strengthen(s)


def hedge_adverb_drop(s: str) -> Optional[str]:
    if _has(r"\b(?:likely|probable|possible) that\b|\bnot (?:likely|probably|necessarily)\b", s) or _has(_NONCLAIM, s):
        return None
    if _has(_UNSETTLED, s) or _has(r"\bpotentially (?:relevant|eligible)\b|\bpropose[sd]?\b", s):
        return None
    return V1.hedge_adverb_drop(s)


def causal_upgrade(s: str) -> Optional[str]:
    if _has(_NONCLAIM, s) or _has(_UNSETTLED, s):
        return None
    if _has(r"\bwhich (?:is|are|was|were) (?:\w+ly )?(?:associated|correlated|linked)\b", s):
        return None
    # 'a reduced risk was associated with X' would reverse cause and effect; 'with X or with Y' would break
    if _has(r"\b(?:risks?|odds|incidence|prevalence|mortality|survival)\b[^,;]{0,40}\b(?:is|are|was|were|has been|have been)\s+(?:\w+ly\s+)?"
            r"(?:associated|correlated|linked)\b|\bassociated with the (?:degree|extent|level)\b|\b(?:or|and) with\b", s):
        return None
    out = V1.causal_upgrade(s)
    if out is None or _has(r"\b(?:associate[sd]?|associations?|correlat\w+|linked)\b", out):
        return None                                                   # association wording remains elsewhere
    return out


_ADJ = r"(?:(?:male|female|adult|aged|young|old|transgenic|knockout|diabetic|obese|wild-type|neonatal)\s+)*"
_PLURAL = r"(?:mice|rats|rodents|zebrafish|primates|monkeys|pigs|dogs|rabbits|animals|cell lines|cultured cells)"
_SING = r"(?:mouse|rat|animal|murine|rodent|rabbit|pig|dog)"
_PHRASE = (r",?\s+in (?:" + _ADJ + _SING + r"\s+models?|(?:a |an |the )" + _ADJ + _SING + r"\s+models?|"
           + _ADJ + _PLURAL + r"|the " + _SING + r"|vitro|(?:this|our) (?:cohort|sample|population|study population))")
# only before punctuation / end / an adverbial: never before a noun ('in mouse femur') or a qualifier ('in mice with')
_SCOPE = re.compile(_PHRASE + r"(?=\s*[,.;:)]|\s*$|\s+(?:after|during|following|by|via|through|upon)\b)", _F)
_SCOPE_WORD = r"\b(?:mice|mouse|rats?|murine|rodents?|zebrafish|primates?|monkeys?|pigs?|dogs?|rabbits?|animals?|vitro|vivo|cell lines?|cultured)\b"


def scope_drop(s: str) -> Optional[str]:
    m = _SCOPE.search(s)
    if not m or _has(_NONCLAIM, s):
        return None
    before = s[:m.start()]
    if _has(r"\b(?:for|of|and|or)\s*$", before):
        return None
    if _has(r"\b(?:observed|seen|found|performed|conducted|tested|used|present|measured|expressed|shown|reported|"
            r"carried out|studied|done|occurs?|documented|described|identified|detected|demonstrated|achieved|obtained|examined|is|are|was|were)\s*$", before):
        return None                                                   # the phrase is the verb's complement
    out = V1._tidy(before + s[m.end():])
    if _has(_SCOPE_WORD, out):
        return None                                                   # scope still recoverable in the sentence
    return out


def quantifier_inflate(s: str) -> Optional[str]:
    if _has(_NONCLAIM, s) or _has(r"\ball\b", s):
        return None
    if _has(r"\bsome of (?:the most|which|whom)\b|\b(?:and|or) some other\b|\b(?:is|are|as) a (?:subset|proportion|fraction|minority) of\b|"
            r"\b(?:reasons?|recommendations?|questions?)\b|\binclud(?:e|es|ing)\b|"
            r"\bat least (?:some|a (?:subset|proportion|fraction|minority))\b|"
            r"\bsome (?:form|sort|kind|type|degree|extent|level|evidence|with|method|way|time)s?\b|"
            r"\bsome (?:of (?:the|these|those) )?\w+, (?:like|such as)\b", s):
        return None
    return V1.quantifier_inflate(s)


def weaken(s: str) -> Optional[str]:
    if _has(_NONCLAIM, s):
        return None
    if _has(r"^\s*(?:however|thus|therefore|hence|moreover|furthermore|finally|interestingly|importantly|notably|"
            r"consequently|additionally|in addition|taken together|collectively|together|here|overall|conversely|"
            r"nevertheless|although|while|whereas|but|and|it is)\b", s):
        return None
    if _has(r"^\s*(?:conclusions?|results?|findings?|background|significance|interpretation|in this (?:study|paper|report|review)|"
            r"we|our|these (?:data|results|findings)|this (?:study|analysis))\b", s):
        return None                                                   # section labels; 'It is possible that we show ...'
    if re.match(r"\s*(?:[A-Z]{5,}\b|[A-Z][A-Za-z]+s?\s*:)", s):      # BACKGROUND ..., Conclusion: ...
        return None
    if _has(r"\b(?:possible|possibly|possibility|hoped|postulat\w*|hypothesi[sz]\w*|speculat\w*|whether)\b", s):
        return None
    return V1.weaken(s)


def negate(s: str) -> Optional[str]:
    """Contradict the source.  'may' -> 'may not' is NOT a contradiction, so may/might -> 'will not', can -> 'cannot';
    have/has/had only as auxiliaries."""
    if _has(r"\b(?:not|no|never|neither|nor|without|cannot)\b", s) or _has(_NONCLAIM, s) or _has(_UNSETTLED, s):
        return None
    if _has(r"\b(?:it is|there (?:is|are|was|were)|given|whose|which|suggesting|indicating|thereby|"
            r"allowing|although|whereas|because|since)\b|\bCI\b|\bP\s*[<=>]", s):
        return None                                                   # rest of the sentence presupposes the positive claim
    if _has(r"\b(?:may|might)\b", s):
        if modal_strengthen(s) is None:
            return None
        return re.sub(r"\b(may|might)\b", lambda m: V1._keep_case(m.group(1), "will") + " not", s, count=1, flags=_F)
    if _has(r"\b(?:can|could|is|are|was|were|has|have)\b.*\band\b.*\b(?:is|are|was|were|has|have)\b", s):
        return None                                                   # only one of two coordinated clauses would flip
    m = re.search(r"\b(is|are|was|were|can|could|will|did|does|do|has|have|had)\b", s, _F)
    if not m:
        return None
    w = m.group(1).lower()
    if w in ("do", "does", "did"):
        return None
    if w in ("has", "have", "had") and not re.match(r"\s+(?:\w+ly\s+|also\s+)?(?:been|\w{3,}ed|shown|led|begun|become|found|made|known)\b", s[m.end():], _F):
        return None                                                   # main verb: 'have not T-cells'
    return s[:m.start()] + ("cannot" if w == "can" else m.group(1) + " not") + s[m.end():]


INFLATIONS = {"modal_strengthen": modal_strengthen, "hedge_adverb_drop": hedge_adverb_drop, "causal_upgrade": causal_upgrade,
              "scope_drop": scope_drop, "quantifier_inflate": quantifier_inflate}
CONTROLS = {"identity": V1.identity, "weaken": weaken, "negate": negate}
EXPECTED_SUPPORTED = {"identity": True, "weaken": True, "negate": False, **{k: False for k in INFLATIONS}}


def variants(sentence: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for name, fn in {**CONTROLS, **INFLATIONS}.items():
        v = fn(sentence)
        if v is not None and (name == "identity" or v != sentence):
            out[name] = v
    return out
