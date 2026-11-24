# P10 LLM 评审对照（Gate 0 条件 3，开源一半）（2026-11-19）

> **更正（2026-11-24）：** 人工审计后本文有多处结论被修正或撤回，见 `runs/AUDIT_RESCORE_20261124.md` 第 2 节。其中 report 类的结果和用它说明的“上下文更宽容”撤回。以下原文保留作记录。

标签：`PILOT_ONLY_NOT_CONFIRMATORY`。和 `runs/pilot_v1` 用**同一批 2,336 对**（同一 SciFact 包、种子、选择规则、v1 编辑规则）。

## 运行记录

| 项 | 值 |
|---|---|
| 机器 / 环境 | hanqing-win，RTX 5070 Ti；项目根 `.venv`，没有新增依赖（transformers 5.23.0，torch 2.15.0+cu132） |
| 评审模型 | `Qwen/Qwen3-4B-Instruct-2507`，bf16，非 gated，Apache-2.0。revision 字段为 `None`，正式协议要固定 commit |
| 打分方式 | 套 chat template 后取下一个 token，P(supported) = softmax(logsumexp(Yes 类 token), logsumexp(No 类 token))。4,672 次中最高概率 token 全部是 Yes/No（`n_argmax_not_yes_no = 0`） |
| 两个提示 | `generic`：只问 "Is the claim supported by the evidence?"（RAG 评测里 LLM 评审的默认用法）。`strength`：明确写出"确定性、因果与关联、范围或量词超出证据的，算 **不** 支持；更谨慎的说法仍算支持" |
| 测试 | 20 项通过（新增 3 项 `tests/test_llm_judge.py`） |
| 耗时 | generic 117 s，strength 129 s |
| 脚本 | `scripts/llm_judge.py`；对比表 `scripts/compare_table.py` |

## 结果（supported 率降幅 vs identity，阈值 0.5；粗体 ≤ 0.3）

**只给原句作前提：**

| 编辑 | n | MiniCheck-R | MiniCheck-D | DeBERTa-L NLI | Qwen-4B generic | Qwen-4B strength |
|---|---:|---:|---:|---:|---:|---:|
| identity（supported 率） | 300 | 1.00 | 0.98 | 1.00 | 1.00 | 1.00 |
| weaken（应支持） | 300 | 0.60 | 0.00 | 0.19 | 0.00 | 0.00 |
| negate | 239 | 0.98 | 0.97 | 0.99 | 1.00 | 1.00 |
| modal may→will | 103 | 0.69 | 0.66 | 0.92 | **0.09** | **0.12** |
| suggest→demonstrate | 81 | **0.06** | **0.19** | 0.96 | 0.42 | 0.52 |
| 删 hedge 副词 | 32 | 0.38 | **0.22** | 0.72 | **0.00** | **0.03** |
| associated→causes | 42 | **0.17** | **0.02** | 0.76 | 0.60 | 0.74 |
| 删范围 | 44 | **0.23** | **0.11** | **0.05** | **0.00** | **0.00** |
| some→all | 27 | 0.96 | 0.89 | 1.00 | 1.00 | 1.00 |

**整段摘要作前提：**

| 编辑 | n | MiniCheck-R | MiniCheck-D | DeBERTa-L NLI | Qwen-4B generic | Qwen-4B strength |
|---|---:|---:|---:|---:|---:|---:|
| identity（supported 率） | 300 | 0.97 | 0.96 | 0.94 | 0.99 | 0.99 |
| weaken | 300 | 0.03 | 0.00 | -0.03 | 0.00 | -0.00 |
| negate | 239 | 0.95 | 0.88 | 0.89 | 0.96 | 0.97 |
| modal | 103 | **0.06** | **0.13** | 0.68 | **0.03** | **0.04** |
| report | 81 | **0.01** | **0.00** | 0.52 | **0.05** | **0.07** |
| hedge | 32 | **0.03** | **0.00** | **0.22** | **0.00** | **0.03** |
| causal | 42 | **0.02** | **0.02** | **0.29** | 0.43 | 0.43 |
| scope | 44 | **0.00** | **0.00** | **0.02** | **0.00** | **0.00** |
| some→all | 27 | 0.96 | 0.81 | 0.93 | 0.85 | 0.85 |

AUROC 见 `python scripts/compare_table.py runs/pilot_v1/summary.json runs/judge_v1/summary.json`。

## 读法

1. **4B LLM 评审没有推翻主发现，反而更盲。** 摘要前提下，Qwen-4B 对 modal、report、hedge、scope 的降幅都 ≤ 0.07，和 MiniCheck 一个水平。就连只给原句时，它也把 91% 的 may→will 判成 supported（MiniCheck 只有 31%）。它唯一比 MiniCheck 明显更敏感的是 **associated→causes**（摘要前提 0.43 vs 0.02）。
2. **把规则写进提示几乎没用。** strength 提示明确说"说过头就不算支持"，降幅只多 0.00–0.14。在 report 编辑上，P(Yes) 的中位数从 0.95 降到 0.15（原句前提），也就是说分数动了，但大多没跨过阈值。所以"告诉评审要看强度"不能修好这个问题，至少对 4B 模型不能。
3. **LLM 评审没有"方向反了"的问题。** weaken 在两种前提下降幅都是 0.00；而 MiniCheck-R 和 NLI-base 在原句前提下会惩罚削弱（0.60 / 0.64）。所以发现 3 是**专用核查器**的性质，不能推广到 LLM 评审，论文要这样写。
4. **阳性对照正常**：negate 降幅 0.96–1.00，some→all 0.85–1.00，identity 0.99–1.00。不是评审整体失灵。

## 对 Gate 0 条件 3 的影响

- 开源一半：**完成**。结论没有被收窄，反而得到了一个更强的版本："在引文作前提的设定下，专用核查器*和*小型 LLM 评审都看不见认识强度膨胀，即使明确要求它看"。
- **API 一半：未做。** hanqing-win 上没有 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`。4B 是小模型，强前沿模型完全可能看得见，所以这仍然是最大的未决风险。如果前沿模型看得见，论文的范围就是"部署在 RAG 评测里的小型和专用评审"。
- 还应补一个 7–8B 的开源评审（例如 Bespoke-MiniCheck-7B），看模型规模的趋势。16 GB 显存放不下 bf16 的 8B，需要 8-bit 量化，即要新增 `bitsandbytes` 依赖。

## 局限

- 只有一个开源评审、一种答案读取方式（下一 token 的 Yes/No 概率），没有让模型先推理再回答。
- 和 pilot_v1 一样：编辑没有经过人工全量审计，scope_drop 的标签有争议，只有生物医学一个领域。

---

# API 一半：前沿模型评审（2026-11-19）

## 运行记录

| 项 | 值 |
|---|---|
| 评审 | `deepseek-v4-pro`（DeepSeek 官方 API，`thinking: disabled`）；`qwen3.7-max-2026-06-08`（阿里百炼 OpenAI 兼容接口，`enable_thinking: false`，固定日期快照）。`served_models` 已核对，与请求一致 |
| 设置 | 同一批 2,336 对，同一 system 和两个提示，`temperature 0`，`max_tokens 1`，`top_logprobs 5`。P(supported) 由首个 token 的 Yes/No logprob 计算。9,344 次调用全部用 logprob 读出，没有一次靠解析文本 |
| 用量 | 输入约 2.86M token（DeepSeek 1.35M，百炼 1.51M），每次输出 1 token |
| 密钥 | 从组合根目录的 `.apikey` 读取，没有写入任何输出。Mac 上已加入 `.gitignore`，并复制到 hanqing-win 的同一位置 |
| 脚本 | `scripts/api_judge.py`（只用标准库，没有新依赖）；测试 23 项通过 |
| 原始输出 | Windows `runs/judge_api_v1/raw_*.jsonl`（可续跑缓存）、`scores.jsonl`。Mac 只拉回了 summary、manifest 和 launch |

## 摘要作前提（主设定），降幅 vs identity；括号为文档 bootstrap 95% CI

| 编辑 | n | MiniCheck-R | Qwen-4B gen | DeepSeek-V4-Pro gen | DeepSeek-V4-Pro str | Qwen3.7-Max gen | Qwen3.7-Max str |
|---|---:|---:|---:|---:|---:|---:|---:|
| identity（supported 率） | 300 | 0.97 | 0.99 | 1.00 | 1.00 | 1.00 | 1.00 |
| weaken | 300 | 0.03 | 0.00 | 0.01 | 0.02 | 0.00 | 0.00 |
| negate | 239 | 0.95 | 0.96 | 1.00 | 1.00 | 1.00 | 1.00 |
| modal | 103 | **0.06** | **0.03** | **0.27** [.18,.35] | 0.55 [.46,.64] | 0.35 [.25,.44] | 0.89 [.83,.94] |
| report | 81 | **0.01** | **0.05** | **0.14** | **0.28** | **0.07** | 0.49 |
| hedge | 32 | **0.03** | **0.00** | **0.09** | **0.12** | **0.12** | 0.53 |
| causal | 42 | **0.02** | 0.43 | 0.57 [.43,.71] | 0.71 | 0.64 [.50,.79] | 0.90 [.81,.98] |
| scope | 44 | **0.00** | **0.00** | **0.00** | **0.00** | **0.00** | **0.00** |
| some→all | 27 | 0.96 | 0.85 | 0.93 | 0.96 | 1.00 | 1.00 |

只给原句作前提时，前沿评审更敏感：Qwen3.7-Max strength 对 modal、report、hedge、causal 的降幅是 1.00/0.89/0.72/0.98，但 scope 仍只有 0.25。完整表见 `python scripts/compare_table.py runs/pilot_v1/summary.json runs/judge_v1/summary.json runs/judge_api_v1/summary.json`。

## 读法（这会改变论文的主张）

1. **默认提示下，前沿评审也大多看不见。** 用通用的 "is the claim supported?" 提示、整段摘要作证据，DeepSeek-V4-Pro 和 Qwen3.7-Max 对 may→will 只拒绝 27–35%，对 suggest→demonstrate 只拒绝 7–14%，对删 hedge 副词只拒绝 9–12%。只有 associated→causes 被抓住一半以上（57–64%）。
2. **但这对前沿模型是"没被要求"，不是"做不到"。** 换成写明强度规则的提示后，Qwen3.7-Max 在摘要前提下的 modal 降幅从 0.35 升到 0.89，report 从 0.07 升到 0.49，hedge 从 0.12 升到 0.53。DeepSeek 升得少一些（modal 0.27→0.55）。同样的提示对 Qwen-4B 几乎没用（≤0.04）。所以**是否看得见强度，取决于规模和提示的交互**：小模型和专用核查器给了提示也看不见，前沿模型只要被要求就能看见一大部分。
3. **删范围对所有评审都是不可见的。** 摘要前提下，10 个核查器和评审配置的降幅全部是 0.00–0.02，包括写明"范围超出证据不算支持"的前沿配置。只给原句时，最高也只有 0.25。这是最稳定的发现。但它的标签本来就有争议（存在性读法下是蕴含），所以它最可能变成论文的核心问题："评审把'在小鼠中成立'当成'成立'"，需要人工标注来证明这是真错误，而不只是单调性。
4. **"上下文越长越宽容"在前沿模型上同样存在**：Qwen3.7-Max strength 的 modal 降幅从原句前提的 1.00 降到摘要前提的 0.89，report 从 0.89 降到 0.49，hedge 从 0.72 降到 0.53。不是专用核查器特有的。
5. **"惩罚削弱"确实只属于专用核查器**：所有 LLM 评审的 weaken 降幅都 ≤ 0.05。
6. **AUROC 不能当"能力"的证据。** Qwen3.7-Max generic 对 modal 的 AUROC 是 0.99，看起来像是分数排序正确，只是阈值偏松。但它对 weaken（应支持）的 AUROC 也有 0.94，说明它对*任何*改动都会略微降低分数，并不是专门对强度上升敏感。阈值上的降幅才是干净的信号。

## 对论文定位的影响

原先的主张"核查器对认识强度膨胀是盲的"需要改成更精确的版本：

> 在部署时的默认设置下（专用核查器，或用通用"是否支持"提示的 LLM 评审，以整段文献作证据），大多数认识强度膨胀会被判为 supported。前沿 LLM 评审只要明确被要求，就能抓到大部分膨胀，但小模型和专用核查器不能；而删掉范围限定对所有配置都不可见。

这其实更有用：它给出了一个**可操作的结论**（RAG 评测里的 faithfulness 提示应当写明强度规则，并且不要依赖 MiniCheck 一类模型来检查过度声称），也有一个**未解决的难点**（范围）。风险是审稿人会说"写好提示就解决了"。回应是：这只对前沿模型成立，而常用评测框架（RAGAS 等）的默认提示不包含强度规则。这一点要在正式协议里**实际检查** RAGAS 和 TruLens 的默认 faithfulness 提示，作为第三类"真实部署配置"。

## 局限

- 两个前沿模型都是非推理模式、单 token 回答。推理模式（先想后答）可能更敏感，正式协议应加一个推理配置。
- DeepSeek-V4-Pro 没有日期快照，结果可能随服务端更新漂移。
- 其余局限同上：编辑未经人工全量审计，只有生物医学一个领域。
