# Native-library pilot concordance

Five pinned distributions were run through six public evaluation entry points in the same P10 Windows virtual environment. Each workflow received the same 50 hash-selected abstract–claim inputs from pilot v1 under the dated Qwen judge. Inputs were selected before comparing verdicts. The reference is the historical replay on the same document and edit. Phoenix faithfulness uses its neutral Q2 question. A failed native call counts against the 50-call denominator. All comparisons use independent API calls, so discrepancies can reflect both pipeline differences and judge variability.

| Native workflow | Matching decisions | Exactly matching scores | Native failures |
|---|---:|---:|---:|
| RAGAS Faithfulness | 48/50 | 42/50 | 0 |
| DeepEval FaithfulnessMetric | 49/50 | 48/50 | 0 |
| TruLens groundedness with reasons | 48/50 | 47/50 | 0 |
| LlamaIndex FaithfulnessEvaluator | 49/50 | 49/50 | 1 |
| Phoenix FaithfulnessEvaluator | 49/50 | 49/50 | 0 |
| Phoenix HallucinationEvaluator | 47/50 | 47/50 | 0 |

For RAGAS and TruLens the decision is full credit, an analyst-defined interpretation. DeepEval uses its 0.5 cutoff. The other workflows return binary verdicts. The negative direction of the Phoenix hallucination score was reversed to align higher scores with support. The LlamaIndex exception was a LookupError. Per-input scores and error types are in runs/native_library_check. The six checks reuse the same inputs. The agreement criterion of 95% requires at least 48 matches out of 50.

**Decision before formal labels.** Omit the Phoenix hallucination replay from the formal comparisons. Retain the five passing binary comparisons as secondary outcomes. For score changes and other graded analyses of RAGAS and TruLens use the native implementations, because passing the decision check does not establish numerical equivalence. A library's fidelity to a replay and its sensitivity to unsupported claims are separate questions. The configuration-level positive and negative controls still apply to the formal data.

The package and model-family constraints differ between native-evaluation and encoder scoring. The spot check used Transformers 5.17.0, huggingface-hub 1.16.1 and click 8.3.3. DeepEval 4.3.4 requires click below 8.4.0, whereas the Hub versions usable with Transformers 5.23.0 in this stack require a newer click. The Windows project retained a single virtual environment and recorded the versions before switching the packages back for the primary encoders. Recreate the native stage with requirements-library-pilot.txt and check dependencies with pip check.
