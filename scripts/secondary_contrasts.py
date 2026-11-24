"""Document-level descriptive contrasts used alongside the six primary decisions."""
import hashlib
import numpy as np


def matched_filler(source, abstract_sentences, source_index, unused_docs, doc_id):
    """Choose an unrelated document by hash and match the original source position in words.

    Keep whole donor words from the beginning. When the hashed donor is too short,
    continue to the next unused donor. The matched length is in whitespace words.
    """
    if abstract_sentences[source_index].strip()!=source:
        raise ValueError("Source sentence differs from the abstract")
    n_before = sum(len(s.split()) for s in abstract_sentences[:source_index])
    n_after = sum(len(s.split()) for s in abstract_sentences[source_index+1:])
    needed = n_before + n_after
    ranking = sorted((d for d in unused_docs if d!=doc_id),key=lambda d:hashlib.sha256(f"P10-padding:{doc_id}:{d}".encode()).digest())
    words, donors = [], []
    for donor in ranking:
        if len(words)>=needed:break
        text=" ".join(unused_docs[donor])
        if source in text:continue
        donor_words=text.split()
        if donor_words:
            words.extend(donor_words[:needed-len(words)])
            donors.append(donor)
    if len(words)!=needed:raise ValueError("Insufficient donor text")
    return " ".join([*words[:n_before],source,*words[n_before:]]),donors


def specificity(rows):
    """Paired difference of drops: (identity - focal) - (identity - weaken).

    The two identity terms cancel on the same document. Inputs are thresholded
    binary decisions. None denotes missing or ineligible; retain complete triples.
    """
    vals=[r["weaken"]-r["focal"] for r in rows if all(r[k] is not None for k in ("identity","focal","weaken"))]
    n=len(vals)
    if not n:return {"n":0}
    counts=[vals.count(k) for k in (-1,0,1)]
    if max(counts)==n:
        from primary_analysis import cp_lower
        a=.05/4
        lo=cp_lower(counts[2],n,a)+cp_lower(n-counts[0],n,a)-1
        hi=1-cp_lower(n-counts[2],n,a)-cp_lower(counts[0],n,a)
    else:
        draws=np.random.default_rng(20261124).multinomial(n,np.array(counts)/n,10000)
        lo,hi=np.quantile((draws[:,2]-draws[:,0])/n,[.025,.975])
    return {"n":n,"mean":sum(vals)/n,"interval95":[float(lo),float(hi)],"counts_minus_zero_plus":counts}
