# P10 部署配置一臂：5 个评测库的默认 faithfulness 流程（2026-11-19）

> **更正（2026-11-24）：** 人工审计后本文有多处结论被修正或撤回，见 `runs/AUDIT_RESCORE_20261124.md` 第 2 节。其中 TruLens/RAGAS/DeepEval 的结论依赖我加的 0.5 阈值，report 类撤回，按核查器排除 RAGAS/DeepEval 也不是 README 的规则。以下原文保留作记录。

标签：`PILOT_ONLY_NOT_CONFIRMATORY`。和 `runs/pilot_v1` 是同一批对，只用**摘要作前提**（贴近 RAG 的设定），共 1,168 对。

## 做法

- 提示原文冻结在 `specs/default_prompts_20261119.json`，来源是 5 个库在 2026-11-19 的最新 wheel：ragas 0.4.4、trulens-feedback 2.16.0、deepeval 4.3.4、llama-index-core 0.14.26、arize-phoenix-evals 3.10.0。每个 wheel 的 sha256 都记在文件里。提取脚本 `scripts/extract_default_prompts.py` 只用 ast 和 json 解析源码，**没有执行下载的代码**。RAGAS 的 `to_string` 渲染，用本地照搬字段定义的 pydantic 模型复现。
- 库本身没有安装。`scripts/deployed_judge.py` 按源码逐步复现每个库的默认流程：
  - **RAGAS**：先把回答拆成陈述，再逐条做 NLI 判断，分数是支持比例。
  - **DeepEval**：从上下文抽取 truths（每篇摘要一次），从回答抽取 claims，再判 verdicts。默认 `borderline` 算通过；另报 strict 变体，只有 yes 算通过。
  - **TruLens**：Groundedness 打 0–3 分，除以 3。
  - **LlamaIndex**：回答里出现 "yes" 就算通过。
  - **Phoenix**：faithfulness 和 hallucination 两个模板，按库的做法强制调用 `extract_structured_data` 工具，返回 `{explanation, label}`。
- 需要用户问题的流程（RAGAS、Phoenix）统一用 "What does this study find?"。
- 评审：`deepseek-v4-pro`（关闭 thinking）和 `qwen3.7-max-2026-06-08`（`enable_thinking=false`），`temperature 0`。supported 阈值仍是 0.5。
- 测试 30 项通过。DeepSeek 的 DeepEval 有 7 条 verdict 的 JSON 缺最后一个 `}`。解析器已加容错（有回归测试），这 7 条重新解析后通过，**没有改变任何判定规则**。

## 完整性

| 评审 | RAGAS | DeepEval | TruLens | LlamaIndex | Phoenix faithfulness | Phoenix hallucination |
|---|---|---|---|---|---|---|
| DeepSeek-V4-Pro | 1168/1168 | 1168/1168 | 1168/1168 | 1168/1168 | 1168/1168 | 1168/1168 |
| Qwen3.7-Max | 1168/1168 | 1168/1168 | 1168/1168 | 1168/1168 | 1168/1168 | 1168/1168 |

Qwen 的 Phoenix 两项第一次没跑完：运行中途百炼开始返回 `HTTP 400: Access denied, please make sure your account is in good standing`。用户处理账户后，续跑只重发了失败的调用（faithfulness 480 条，hallucination 1,133 条），现在全部完成，失败 0。续跑的 token 用量：输入 2.47M，输出 0.19M。

## 结果（降幅 = identity 的 supported 率减去该编辑的 supported 率；identity 行是 supported 率）

| 编辑 | n | RAGAS DS | RAGAS QM | DeepEval DS | DeepEval QM | DeepEval-strict DS | DeepEval-strict QM | TruLens DS | TruLens QM | LlamaIndex DS | LlamaIndex QM | Phoenix-faith DS | Phoenix-halluc DS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| identity | 300 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 0.96 | 1.00 | 1.00 | 1.00 | 1.00 | 0.88 | 1.00 |
| weaken | 300 | 0.05 | 0.01 | 0.00 | 0.00 | 0.00 | -0.01 | 0.00 | 0.00 | 0.00 | 0.00 | **0.35** | 0.00 |
| **negate（阳性对照）** | 239 | **0.35** | **0.36** | **0.48** | **0.43** | 0.51 | **0.49** | 0.96 | 0.98 | 0.67 | 0.98 | 0.85 | 1.00 |
| modal | 103 | 0.27 | 0.17 | -0.01 | 0.06 | 0.18 | 0.35 | **0.00** | **0.03** | **0.03** | **0.07** | 0.69 | 0.50 |
| report | 81 | 0.20 | 0.02 | 0.00 | 0.05 | 0.02 | 0.07 | **0.01** | **0.01** | **0.02** | **0.00** | 0.19 | **0.11** |
| hedge | 32 | 0.09 | 0.03 | 0.03 | 0.00 | 0.06 | 0.06 | **0.00** | **0.00** | **0.03** | **0.00** | 0.22 | **0.06** |
| causal | 42 | 0.43 | 0.40 | 0.14 | 0.26 | 0.33 | 0.40 | **0.10** | **0.17** | **0.02** | **0.19** | 0.69 | 0.88 |
| scope | 44 | 0.00 | 0.00 | 0.00 | 0.02 | -0.02 | 0.02 | **0.00** | **0.00** | **0.00** | **0.02** | 0.07 | **0.00** |
| some→all | 27 | 0.26 | 0.19 | 0.22 | 0.19 | 0.33 | 0.22 | 0.41 | 0.93 | 0.33 | 0.74 | 0.81 | 0.93 |

DS = DeepSeek-V4-Pro，QM = Qwen3.7-Max。粗体降幅出现在**通过了阳性对照**（negate 降幅 ≥ 0.5）的配置里。

## 读法

1. **先看哪些配置可以解读。** 按 README 事先写好的规则，negate 降幅 < 0.5 的配置没有通过敏感度对照，不解读。所以 **RAGAS（0.35/0.36）和 DeepEval 默认设置（0.48/0.43）不能作为"看不见膨胀"的证据**，因为在这个设定下它们连否定都只抓住不到一半。原因在流程本身：
   - RAGAS 把一句话拆成多条陈述，只要一条被否定，比例分数仍然 ≥ 0.5。
   - DeepEval 先把摘要改写成 truths 再比对，又把"没有直接矛盾"判成 borderline，而 borderline 算通过。

   这本身是值得报告的发现（这两个库在单句层面对否定都不敏感），但它不属于"认识强度"的论点。
2. **通过阳性对照的配置里，膨胀几乎完全看不见。** TruLens（negate 0.96–0.98）、LlamaIndex（0.67–0.98）、Phoenix hallucination（1.00）对 modal、report、hedge、scope 的降幅大多在 0.00–0.07（Phoenix 对 report 是 0.11）。换成"被判 faithful 的比例"：
   - TruLens：may→will 97–100%，suggest→demonstrate 99%，删 hedge 100%，删范围 100%。
   - LlamaIndex：may→will 93–97%，suggest→demonstrate 98–100%，删范围 98–100%。

   **这就是用这些库默认设置评测 RAG 时，膨胀会被记为 faithful 的比例。**
3. **causal 是唯一部分被看见的类型。** Phoenix hallucination 0.88，Phoenix faithfulness 0.69；TruLens 和 LlamaIndex 只有 0.02–0.19。和前面的结论一致：associated→causes 最"像"事实错误。
4. **Phoenix faithfulness 是个例外，但它的对照不干净。** 它对 modal 降幅 0.69，但对安全的削弱也降 0.35，identity 也只有 88%。我只看过一条解释：它把原句判为 unfaithful，理由是这句话"是背景，不是研究发现"。这说明判定可能受问题 "What does this study find?" 影响，而不是对强度敏感。要读完解释文本、换一个问题再测，才能解读这一列。
5. **删范围对所有部署配置仍然完全不可见**（0.00–0.07）。

## 对论文的影响

- 主张可以写得具体而有力：*"在 TruLens 和 LlamaIndex 的默认设置下，用前沿 LLM 作评审，93–100% 的 may→will、suggest→demonstrate、删 hedge 和删范围的句子被判为 faithful；而同样的配置能抓住 96–98% 的否定（LlamaIndex 用 DeepSeek 时只有 67%）。"* Phoenix hallucination 介于两者之间：may→will 只有 50% 被判 faithful，suggest→demonstrate 89%，删范围 100%。
- RAGAS 和 DeepEval 应单独作为"流程设计导致对单句错误不敏感"的例子，不放进强度论点。RAGAS 的拆句步骤会改写强度（冒烟测试里 "will have promise" 被拆成 "shows promise"），这个机制值得在论文里用几个例子说明。
- 这一臂回应了"写好提示就能解决"的质疑：真实部署时用的提示就是这些。

## 局限

- 库是按源码复现的，没有安装后直接调用。提示文本是逐字提取的，调用方式（JSON 解析、工具调用的参数）是近似。正式协议最好在项目 `.venv` 里装上这几个库，至少抽查一部分对是否和复现一致（需要更新依赖清单）。
- 两个评审都关闭了推理。Qwen 的 Phoenix 两项缺失。
- **第一次运行的 token 用量没有保存**：manifest 在补跑时被覆盖了。按冒烟测试估算，每个评审约 8–9M 输入 token。这是记录上的缺陷，之后的运行要把用量写进 raw 文件。
- 编辑没有经过人工全量审计；只有一个领域。

---

## 补充：Qwen 的 Phoenix 结果，以及换问题后的 Phoenix faithfulness（2026-11-19 晚）

为了检验 Phoenix faithfulness 的异常（identity 只有 88% 被判 supported，weaken 降幅 0.35）是不是问题措辞造成的，把问题从 "What does this study find?"（Q1）换成更中性的 "What does this abstract say?"（Q2），两个评审各重跑一次。输出在 `runs/deployed_q2_ds` 和 `runs/deployed_q2_qm`。每对的 token 用量都已写进 raw 文件：Q2 每个评审约 1.1M 输入、0.11–0.14M 输出。

**降幅 vs identity（identity 行是 supported 率）：**

| 编辑 | Phoenix-faith DS Q1 | Phoenix-faith QM Q1 | Phoenix-faith DS Q2 | Phoenix-faith QM Q2 | Phoenix-halluc DS | Phoenix-halluc QM |
|---|---:|---:|---:|---:|---:|---:|
| identity | 0.88 | 0.82 | **1.00** | **1.00** | 1.00 | 1.00 |
| weaken（应支持） | 0.35 | 0.19 | **0.33** | **0.36** | 0.00 | 0.24 |
| negate | 0.85 | 0.81 | 1.00 | 1.00 | 1.00 | 1.00 |
| modal | 0.69 | 0.60 | 0.81 | 0.82 | 0.50 | 0.65 |
| report | 0.19 | 0.09 | 0.35 | 0.16 | 0.11 | 0.22 |
| hedge | 0.22 | 0.25 | 0.28 | 0.44 | 0.06 | 0.31 |
| causal | 0.69 | 0.52 | 0.95 | 0.79 | 0.88 | 0.86 |
| scope | 0.07 | -0.07 | 0.00 | 0.11 | 0.00 | 0.00 |
| some→all | 0.81 | 0.81 | 0.96 | 0.96 | 0.93 | 0.96 |

**读法：**

1. **问题措辞确实是 identity 被拒的原因。** 换成 Q2 后，identity 回到 100%，negate 也到 1.00。Q1 下的 Phoenix faithfulness 结果不应采用，以 Q2 为准。
2. **但 Phoenix faithfulness 惩罚削弱，不是措辞造成的。** 在 Q2 下，"It is possible that X" 仍有 33–36% 被判 unfaithful。所以它对 may→will 的 0.81–0.82 降幅，有一部分是"对任何改写都更严格"，而不是专门对强度上升敏感。论文里要把它和 weaken 的降幅并列报告，或者报告两者的差（modal 约 0.46–0.48）。
3. **Phoenix 的两个模板是 5 个库里对强度最敏感的**：modal 0.50–0.82，causal 0.79–0.95。但即使是它们，suggest→demonstrate 也有 65–89% 被判 faithful，删 hedge 有 56–94%，**删范围有 86–100%**。
4. **综合 5 个库、两个评审，在所有通过否定对照的配置里**（TruLens、LlamaIndex、Phoenix faithfulness Q2、Phoenix hallucination）：
   - 删范围：判 faithful 的比例是 **89–100%**，所有配置都看不见。
   - suggest→demonstrate：**65–100%**；删 hedge：**56–100%**。
   - may→will 分成两类：TruLens 和 LlamaIndex 判 faithful 93–100%，Phoenix 是 18–50%。

   所以论文的部署配置结论应该是：*"认识强度膨胀在常用评测库的默认设置下普遍被判为 faithful；被看见的程度取决于库，最高的是 Phoenix 对 modal 的约 80%，而删范围在所有库里都看不见。"*

**Token 用量（有记录的部分）：** 续跑和 Q2 共约 4.7M 输入、0.44M 输出 token。第一次主运行的用量没有保存（见上）。
