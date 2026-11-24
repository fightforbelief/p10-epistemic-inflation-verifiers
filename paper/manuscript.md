# Does reading the full abstract change whether a verifier accepts an overstated claim?

Yunjie Guo and Hanqing Yang  
Independent Researcher, Suzhou, China  
Correspondence to Hanqing Yang, hanqing.yang189@gmail.com

*Working manuscript for a result paper. Confirmatory labels were frozen on 24 November 2026. Verifier outcomes are pending.*

## Introduction

A source that says an effect *may* occur gives a reader less reason for confidence than a claim that the effect *will* occur. The words identifying the effect can be identical. A citation checker therefore faces a decision about what the evidence licenses even when it has retrieved the right document and matched the right entities. The practical question is whether its binary verdict changes when the cited document contains the original qualification along with related findings.

Prior work provides three reasons to test this decision directly. Wührl and colleagues annotated changes in certainty, causality, generality and sensationalism between scientific findings and their coverage. Nnamdi and colleagues tested whether certainty survives rewriting. Their controlled removal of hedges and their certainty-specific directional judge establish a close precedent for both the manipulation and the use of a judge. Ramprasad and Wallace found that factuality metrics can react to benign edits. A change in a score after editing, by itself, therefore provides limited evidence about whether the checker recognizes unsupported strengthening. [Wührl et al.](https://aclanthology.org/2024.findings-acl.369/) · [Nnamdi et al., Appendix J](https://aclanthology.org/2026.aacl-long.223.pdf) · [Ramprasad and Wallace](https://arxiv.org/abs/2411.16638)

We study a paired decision. A human first determines whether a strengthened sentence exceeds what the full abstract supports. For those documents the edited claim is held fixed while a verifier receives either the original sentence or the full abstract. The primary contrast counts transitions in both directions. Related text can legitimately provide stronger evidence elsewhere in an abstract. Human review of the full premise before model scoring is therefore essential to the interpretation. Prior results on context sensitivity in long-document evaluation also motivate a length-matched unrelated-text control. [Mujahid et al.](https://arxiv.org/abs/2511.07689)

## Methods

SciFact provides the document pool. Two development pilots informed the sampling limits, acceptance thresholds and test design. The pilots cover 339 distinct papers. Every sentence from each of these papers is excluded from the confirmatory population. In the remaining documents, fixed rules identify eligible edits of sentences between 8 and 60 words. Documents enter mutually exclusive edit categories in a fixed order. A deterministic hash selects one sentence per document within its category. Sampling prioritizes rarer edits and the estimands apply to the resulting rule-eligible populations. [Wadden et al.](https://aclanthology.org/2020.emnlp-main.609/)

For the primary categories, the edits replace *may* or *might* with *will*, or remove a lexical hedge. An annotator reviews the source and edited versions for grammatical integrity and increased strength, then reads the full abstract to assess whether it warrants the edited claim. A claim qualifies if it is well formed or has a minor imperfection, is stronger than its source, and lacks support in the abstract. Greater confidence can alter temporal meaning as well as modality. The annotator can reject a change that fails to preserve the underlying claim. A fixed stopping rule targets 200 valid modal edits and 150 valid hedge edits. Each document contributes once per focal contrast. The issued workbook contained no verifier scores. The annotator reported using tool assistance followed by item-level human review for the initial 833 records. The annotation method for the final 66 records, familiarity with the hypotheses and exposure to formal model scores outside the workbook await confirmation.

We test two encoder variants of MiniCheck and two API judges. MiniCheck produces one support verdict for each combination of claim and premise. We compare its document-level decision with its own decision on the source sentence. Prompt comparisons use the same claim and abstract under both instructions within each judge. Each configuration faces a copied-sentence control and an unsupported-negative control. For the prompt comparison, the maximum tolerated loss of acceptance is five percentage points on both copied and weakened claims. Formatting, document segmentation, the probability comparison at the threshold, and the aggregation over chunks are part of the intervention. [Tang et al.](https://aclanthology.org/2024.emnlp-main.499/)

The six primary hypotheses and their decision rules are fixed in the archived protocol. For each encoder, the first hypothesis requires both class-specific lower confidence limits for document-level acceptance to exceed 0.70. The second requires the lower limit for the mean paired increase on modal edits to exceed 0.20. For each judge, the third requires the lower limit for the paired reduction under explicit strength instructions to exceed 0.10, together with the preservation criteria above. All tests use a one-sided level of 0.05/6. We will report successes, failures and configurations with insufficient controls, plus missingness and the two discordant counts for every paired comparison.

### Paired decisions and sensitivity analyses

Suppose that, among the eligible documents for one model, *g* claims change from rejected to accepted when the full abstract is supplied, and *l* change from accepted to rejected. With *n* complete pairs, the estimated net increase is (*g* − *l*) / *n*. All valid documents enter the denominator, including those whose verdict stays the same. Restricting analysis to initially rejected claims would remove the reverse transitions and estimate a different quantity. We resample whole documents jointly across conditions and retain the original pair in each draw.

Some edits may be disputed by the annotator or make the sentence less natural. We will report the impact of admitting contested strength judgments, excluding minor imperfections, and using the entire processed edit set. For scope removal, the reader's interpretation as a generic assertion is an additional eligibility criterion. Causal strengthening and universal quantification will be reported separately. For matched documents on which weakening is possible, subtracting the identity-to-weaken drop from the identity-to-strengthen drop measures how selectively the verifier reacts to the direction of change.

For a binary verifier decision, the score threshold and the quality of the underlying ranking can give different answers. A copied claim supplies an easy support case. A negative edit supplies a test of sensitivity to an unsupported claim. Among documents eligible for that negative control, a configuration must accept at least 90% of copies and show a paired drop of at least 70 percentage points on negative edits, with at least 150 complete pairs. A configuration with more than 2% missing planned scores is uninterpretable under the protocol. Missing responses are recorded explicitly. Repeated judge calls on a deterministic 10% document subsample quantify agreement under identical inputs.

## Confirmatory sample

The frozen return contains 899 annotations. Among 779 focal documents, 690 edits met the prespecified eligibility criteria. Modal strengthening first reached its target at document 216 (200 eligible), and hedge removal first reached its target at document 203 (150 eligible). The remaining categories yielded 137 eligible scope edits out of 150 reviewed, 145 causal edits out of 150 and 58 quantifier edits out of 60. In the separate control audit, 59 of 60 weakening edits and 58 of 60 negations were judged to perform the intended change. These counts describe human judgments of the edits. Verifier acceptance and paired changes await formal scoring.

## Interpretation

The study measures a verifier's operating decisions on controlled scientific edits. False acceptance can depend on its threshold even when the underlying score decreases after editing. The context comparison combines additional evidence with changes in token position and segmentation. A length-matched filler contrast can inform interpretation, while differences in wording, placement and the number of scored chunks still constrain a mechanistic claim. The two encoders are members of a larger verifier family, which also includes models of different architectures. The corpus, rule-defined population, and use of one annotator bound external validity. Occurrence rates in naturally generated answers require a different sampling frame.

## Declarations

The authors report no specific funding and no competing interests.
