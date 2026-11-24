# 常用 RAG 评测库的默认 faithfulness 提示里有没有"强度规则"（2026-11-19）

**结论：5 个库的默认提示都没有要求检查确定性、因果或范围。其中 4 个还写了会让膨胀*更容易*通过的宽松规则。** 所以 LLM 评审对照里 `generic` 提示的结果（前沿模型在摘要前提下多数看不见）才是实际部署中的情形，`strength` 提示不是。这回应了"写好提示就解决了"的质疑：在默认配置下，没有人写这个提示。

## 方法

从 PyPI 下载每个库 2026-11-19 时的最新 wheel，只读源码文本，不安装也不运行。文件放在 scratchpad 的 `evalpkgs/`，没有进项目目录。检查的是各库在默认参数下实际使用的 faithfulness、groundedness 或 hallucination 提示，并在所有源码里检索 hedg、certainty、overstat、speculat、qualif 等词。

| 库 | 版本（上传日期） | 文件 |
|---|---|---|
| ragas | 0.4.4（2026-11-14） | `ragas/metrics/collections/faithfulness/util.py` |
| trulens-feedback | 2.16.0（2026-10-19） | `trulens/feedback/templates/rag.py`（`Groundedness`） |
| deepeval | 4.3.4（2026-11-11） | `metrics/faithfulness/templates/generate_verdicts.txt`、`templates/metrics/templates.json` 里的 fragments、`faithfulness.py` |
| llama-index-core | 0.14.26（2026-11-13） | `core/evaluation/faithfulness.py`（`DEFAULT_EVAL_TEMPLATE`） |
| arize-phoenix-evals | 3.10.0（2026-11-10） | `__generated__/classification_evaluator_configs/` 里的 faithfulness 和 hallucination |

## 逐库结果

| 库 | 判定规则（概括） | 强度规则 | 对膨胀不利还是有利 |
|---|---|---|---|
| **RAGAS** | 先把回答拆成原子陈述，再逐条判断能否 "directly inferred" from context | 无 | 中性。但拆句这一步本身可能丢掉 hedge 和范围，需要实测 |
| **TruLens** | 自称 "INFORMATION OVERLAP classifier"，0–3 分。规则包括：表示怀疑或不确定的陈述给满分；要考虑间接证据，"avoid penalizing potentially factual claims" | 无 | **有利于膨胀**：按信息重叠打分，强度不同、内容相同的句子重叠度很高。要求考虑间接证据，也是在放宽 |
| **DeepEval** | 判断每个陈述是否 "contradicts" 检索内容。只有 "DIRECTLY CONTRADICTS" 才判 no；证据不支持但也不矛盾的判 borderline；推测性措辞不算矛盾。**默认 `penalize_ambiguous_claims=False`，borderline 算通过** | 无 | **在默认设置下，膨胀按设计就会通过**：may→will、association→causation、删 "in mice" 都不和原文矛盾，最多是 borderline，而 borderline 默认算通过 |
| **LlamaIndex** | YES/NO："Answer YES if any of the context supports the information, even if most of the context is unrelated" | 无 | **有利于膨胀**："只要有任何部分支持就算 YES"，正好让同一主题、强度更低的原句"支持"更强的说法 |
| **Phoenix** faithfulness | 判断回答是否 "assumes information that is not available in the context" | 无 | 中性，近似我们的 generic 提示 |
| **Phoenix** hallucination（新版默认） | 详细列了矛盾、编造具体信息、编造工具结果等类别。表示不确定的回答算 GROUNDED。"When you are genuinely unsure whether a claim is supported, label the response grounded" | 无 | **有利于膨胀**：列出的错误类别都是实体、数值、事件，没有强度。不确定时默认判 grounded |

在 5 个库的全部源码里检索 hedge、certainty、overstat、speculat、qualif。其他命中都在无关的文件里（如数据合成、简洁度、拒答模板）。和 faithfulness 相关的命中，只有 TruLens 和 Phoenix 里的**放宽**规则（"不确定的表述算 grounded 或满分"）；DeepEval 的"推测性措辞不算矛盾"也是放宽。**没有一处要求"比证据更确定，就算不支持"。**

## 对 P10 的意义

1. **"默认就是盲的"有了制度上的依据。** 主流评测库的默认提示要么不提强度，要么明确放宽。前沿模型在 strength 提示下能看见一部分，这只说明能力存在，而部署配置并没有调用这种能力。
2. **DeepEval 是最强的单个例子。** 它在默认设置下是"矛盾检测器"。膨胀不和原文矛盾，所以按设计就会通过。这一点*仅凭读提示*就能确定，但论文里仍然应该实测。
3. **正式协议应加"部署配置"一臂**：把这 5 个库的默认提示（RAGAS 用两步流程；DeepEval 计 borderline 为通过）原样套到同一批对上，用同一个前沿评审打分。这样能直接报告"用 X 库默认设置评测 RAG，有多少膨胀会被计为 faithful"。这比我们自己写的 generic 提示更有说服力，因为它不可能被说成稻草人。
4. **TruLens 和 Phoenix 有一个反向的风险。** 它们对*削弱*给满分。如果 RAG 系统输出更弱的说法，这些库不会惩罚，这对用户来说是安全的。但这也意味着，强度这一维在评测里完全没有被约束。

## 局限

- 只读了提示，**没有实测**。RAGAS 的拆句步骤会不会丢失 hedge 和范围，需要跑一遍才知道。
- 只看了每个库的主要 faithfulness 或 groundedness 指标，没有看所有变体（例如 RAGAS 的 `FaithfulnesswithHHEM`，TruLens 用 NLI 模型的 groundedness 实现）。
- 库的默认值会变，所以引用时必须写明版本号。
