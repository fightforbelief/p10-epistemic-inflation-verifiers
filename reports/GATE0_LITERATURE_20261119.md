# P10 Gate 0：文献深查（2026-11-19）

> **更正（2026-11-24）：** 人工审计后本文有多处结论被修正或撤回，见 `runs/AUDIT_RESCORE_20261124.md` 第 2 节。条件 3、6、7 以审计报告为准；条件 6 按单人标注结项（研究者 2026-11-24 决定不做第二人标注，列为局限）。研究者 2026-11-24 裁定维持 GO，Gate 0 仍是 `PASS_WITH_CONDITIONS`。以下原文保留作记录。

**判定：`PASS_WITH_CONDITIONS`。新颖性：`PROVISIONAL`。** 没有找到直接撞题的工作。三个试点发现各有不同程度的近邻，论文必须按下面的方式定位和引用。

## 检索范围与方法

- 网页检索 9 轮（标准 + 扩展），截至 2026-11-19。没有用付费数据库，**也没有检索 OpenReview 上在审的 ICLR 2027 投稿**（截稿 2026 年 10 月），这是剩余的主要撞题风险。
- 精读全文 7 篇：Wührl et al. 2024、Ramprasad & Wallace 2025（v4）、Mujahid et al. 2026（2511.07689v2）、Trustworthy RAG（2608.21095）、RIGOURATE（2601.04350）。另外 4 篇的 PDF 网页抓取读不出来，改用本机 PDFKit 抽取文本后做关键词定位，读了对应段落：Epistemic Erosion（AACL 2026）、Can We Trust the Judges?（2609.15561）、Saying More Than They Know（2604.19768）、Bouke 2026（2607.04223）。后三篇*没有逐页通读*。
- 只读摘要、没有读全文：Peters & Chin-Yee 2025、BUMP（Ma et al. 2023）、Teaching LMs to Faithfully Express Uncertainty（2510.12587）、AquiLLM（2609.16519）。

## 近邻与撞题判断

| 工作 | 做了什么 | 和 P10 的关系 |
|---|---|---|
| **Epistemic Erosion**（Nnamdi et al., AACL 2026） | 测 LLM 摘要和改写中确定性的流失。EFS 用规则做一对一对齐，分 6 类（escalation、attenuation、omission、fabrication、scope shift、severity warp）。领域是临床、法律、科学。只把 EFS 和 ROUGE-L、BERTScore 对比（\|r\|≈0.1） | **生成端**测量。NLI 只出现在相关工作里，原话是 NLI 类方法 "primarily assess whether generated claims are supported"，**没有测核查器**。和 P10 互补：它说生成会膨胀，P10 测评测器能不能发现。必须引用 |
| **Wührl et al.**（ACL Findings 2024） | 1,600 条论文结论与新闻、推文的配对，标注因果、确定性、概括度和夸张程度。用微调的 RoBERTa、SciBERT 和 few-shot LLM 检测失真，macro-F1 约 0.4–0.59 | 框架是科学传播。**没有测通用 NLI、MiniCheck、AlignScore**。它的数据可以当 P10 的**自然失真臂**（见条件 2） |
| **Ramprasad & Wallace**（2025） | 6 个指标（含 AlignScore、MiniCheck、SummaC、LLM 评审），8 种良性扰动，外加 GenAudit 人工纠正。指标对良性编辑过敏，追加无内容句子就能刷分 | 扰动里**没有确定性、因果、范围或量词**。它支持发现 3 的一半，即对无害改动过敏。必须引用 |
| **Mujahid et al.**（2026，长文档压力测试） | 6 个指标，7 种"保义"扰动，领域是法律、科幻、CS。检索窗口 w 变大时，AlignScore 和 MiniCheck 对原摘要的分数上升；插入无关原文句子也会让分数上升 | **发现 2 最近的近邻**：上下文越多分数越高。但它没有对错标签，不能说"误判支持"。P10 有确定不该支持的受控句子。必须引用，发现 2 要表述成"在有真值的受控对上量化这个效应" |
| **Can We Trust the Judges?**（2609.15561） | 对开放域 QA 的金标答案做分级**事实**替换，测 RAGAS、LLM 评审和 LLM+NLI 是否随降级单调下降 | 元评测方法相近，但扰动是事实替换，不是认识强度。引用即可 |
| **RIGOURATE**（2026） | 用 LLM 评审给 ML 论文作者自身的夸大打分（0–1），微调 VLM，只有一个定性的最小对案例 | 测的是 LLM 评审，不是 RAG 核查器。它提示 **LLM 评审可能看得见膨胀**，这是 P10 必须补测的对照（条件 3） |
| **Trustworthy RAG**（2608.21095） | 文档投毒检测，其中"subtle manipulation"（加假限定或 hedge）召回 20%。另外发现带 hedge 的前缀会压低 NLI 蕴含分 | 方向和发现 3 一致：hedge 会被惩罚。但它没有受控对照。引用 |
| **BUMP**（2023） | 889 条人工写的最小对，7 类错误（谓词、实体、情境、共指等），CNN/DM 新闻 | 最小对元评测的先例，**错误类型里没有认识强度**。引用 |
| NLI 单调性文献（如 MoNLI、HELP） | 已知 NLI 模型处理上行/下行单调推理很差 | 直接关系到 scope_drop：删限定语在上行语境下*是*蕴含。所以 scope 必须单列，或作为单调性问题讨论 |
| Saying More…、Bouke 2026、2510.12587 | 分别是生成文本修辞校准、训练无关的无依据检测，以及让模型 hedge 与置信一致 | 不撞题 |

## 三个发现的新颖性

1. **文档级核查器对认识强度膨胀是盲的**：**没有找到先例**，是 P10 的主贡献。新颖性是"窄但真实"的经验发现，前提是 LLM 评审对照的结果不推翻它。
2. **前提越长越宽容**：**部分先例**（Mujahid 2026 观察到分数随窗口上升）。P10 的增量是：在有真值的受控不支持句上，把它量化成误判支持率（例如 71→8 次拒绝）。
3. **惩罚削弱多于膨胀**：一半有先例（对良性编辑过敏，hedge 前缀被惩罚）。**用加强与削弱成对对照、测出方向反转**，这一点没有找到先例。

## 通过 Gate 0 的条件（冻结正式协议之前）

1. **重新定位**：论文是*元评测*，题目类似 "Supported but overstated: grounding verifiers are blind to epistemic inflation"。不要声称发现了"认识侵蚀"本身。要明确站在 Epistemic Erosion（生成端）和 Wührl（科学传播）之间。
2. **加自然失真臂**：用 Wührl et al. 的配对（论文结论 → 新闻或推文结论，带确定性、因果、概括度标签）。测核查器是否把*标注为更确定、更因果或更泛化*的报道句判成被论文句支持。这能回答"规则编辑不自然"的质疑。**先查清数据许可**：页面没写许可，论文只说接收后公开。
3. **加 LLM 评审对照**：至少一个 API 模型和一个开源模型。如果强 LLM 评审能看见膨胀，结论要收窄到"小型专用核查器（MiniCheck 一类，被广泛用于 RAG 评测）"，这仍然有意义，但范围变小。**开源一半已完成（2026-11-19，`runs/LLM_JUDGE_RESULTS_20261119.md`）**：Qwen3-4B-Instruct 在摘要前提下对 modal、report、hedge、scope 同样是盲的（降幅 ≤ 0.07），明确要求看强度的提示也没用；它只对 causal 更敏感（0.43）。它不惩罚削弱，所以发现 3 只适用于专用核查器。**API 一半已完成**：默认提示下 DeepSeek-V4-Pro 和 Qwen3.7-Max 在摘要前提下也大多看不见（modal 0.27–0.35，report 0.07–0.14，hedge 0.09–0.12），但写明强度规则后 Qwen3.7-Max 能抓到大部分（modal 0.89，causal 0.90）；scope 对所有配置都是 0.00。**结论要改写为'默认设置下盲，前沿模型被要求时部分可见，范围对所有配置不可见'**（见结果文件的'对论文定位的影响'）。正式协议需加入 RAGAS/TruLens 默认 faithfulness 提示和一个推理模式配置。**默认提示已检查（`reports/EVAL_DEFAULT_PROMPTS_20261119.md`）**：RAGAS、TruLens、DeepEval、LlamaIndex、Phoenix 都没有强度规则，其中 4 个带放宽规则。DeepEval 默认只在直接矛盾时判失败，所以膨胀按设计就会通过。
4. **scope_drop 单独处理**：放在单调性框架下讨论，不和逻辑上明确不蕴含的类型合并。
5. ~~补查 OpenReview 上 ICLR 2027 的在审稿~~ **已完成，未发现撞题（见下文附录）。** 冻结前仍需读完 Epistemic Erosion 附录全文。
6. 人工审计 v1 的全部膨胀编辑（约 330 条），这是 README 里已有的要求。

7. **部署配置一臂（2026-11-19，`runs/DEPLOYED_CONFIGS_RESULTS_20261119.md`）**：把 5 个库的默认流程按源码复现，用前沿评审打分。通过阳性对照的 TruLens 和 LlamaIndex，把 93–100% 的 may→will、suggest→demonstrate、删 hedge 和删范围的句子判为 faithful。RAGAS 和 DeepEval 默认设置连否定都只抓住 35–48%，没通过敏感度对照，不进强度论点。Qwen 的 Phoenix 两项已在账户恢复后补完。换成中性问题后，Phoenix faithfulness 的 identity 恢复到 100%，但它仍会惩罚 33–36% 的削弱。在所有通过否定对照的配置里，删范围有 89–100% 被判 faithful，suggest→demonstrate 有 65–100%。

## 来源

- Epistemic Erosion：https://aclanthology.org/2026.aacl-long.223/
- Wührl et al. 2024：https://arxiv.org/abs/2402.12431 ；数据：https://www.uni-bamberg.de/en/nlproc/resources/sciencecommdistortion/
- Ramprasad & Wallace：https://arxiv.org/abs/2411.16638
- Mujahid et al. 2026：https://arxiv.org/abs/2511.07689
- Can We Trust the Judges?：https://arxiv.org/abs/2609.15561
- RIGOURATE：https://arxiv.org/abs/2601.04350
- Trustworthy RAG：https://arxiv.org/abs/2608.21095
- BUMP：https://aclanthology.org/2023.acl-long.716/
- Peters & Chin-Yee 2025：https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12042776/
- Saying More Than They Know：https://arxiv.org/abs/2604.19768
- Bouke 2026：https://arxiv.org/abs/2607.04223

## 附录：ICLR 2027 OpenReview 在审稿检查（2026-11-19）

**结论：没有找到撞题的在审稿。** 条件 5 的这一半已完成。

**方法：**
- 用 OpenReview 公开 API `api2.openreview.net/notes/search`，限定 `group=ICLR.cc/2027/Conference`，按论坛去重，共检索 37 个关键词，得到 2,194 篇唯一投稿。原始结果在 `reports/iclr2027_openreview_hits_20261119.json`。
- 筛选：标题、摘要或关键词*同时*含"强度"类词（hedge、certainty、epistemic、overstat、exaggerat、overgenerali、qualifier……）和"核查器"类词（verifier、faithful、NLI、entailment、grounding、attribution、citation、judge……），得到 110 篇，逐条读标题。可疑的 12 篇读了摘要。又按"stronger than / unsupported certainty / partially supported"等措辞做了第二轮筛选。
- **对"强度"类词，检索在结果数上限之内，应当是完整的**：hedging 21 篇、hedge 46、certainty 58、overclaiming 2、overstatement 3、exaggeration 7、overgeneralization 5、qualifier 7、boosters 1、MiniCheck 0、AlignScore 0、epistemic 166（翻页取全）。核查器类的宽泛词碰到了每次 100 条的上限，所以那一侧召回不完整。不过要撞题，必须同时出现强度类词。
- 局限：只查了标题、摘要和关键词，没有读全文。撤稿和桌拒的投稿没有单独检索。

**最近的在审稿（都不撞题）：**

| 投稿 | 内容 | 与 P10 的距离 |
|---|---|---|
| Narrative Fidelity（oeedYIz6gO） | 临床对话摘要的"叙事保真"六维人工标注，其中包括不确定性和认识立场。只和 ROUGE、BERTScore 比较（r≈0.43） | 生成端的人工标注，没有测核查器。可作相关工作 |
| Evidence Over Memory / MainLogic（P5SFMmkU5Q） | 改变科学引文中的主张和证据基础，测长上下文 LLM 推理时是否跟着证据走 | 测的是生成或推理模型，不是对认识强度的核查。方法（受控的证据—主张族）接近，可引用 |
| WARNINGS ARE NOT VERDICTS（MioRSrhSId） | 引用核查器把部分支持的主张*过度降级*为证据不足 | 方向相反（过严，而不是过宽），没有涉及认识强度。可作对照引用 |
| PacketCert（Uf0lsyBTeO） | 压缩 RAG 选段时会丢掉"限定主张的 qualifier" | 检索端，不是核查端 |
| EGAA（FotNLO6fOF） | 多模态幻觉中的 "Unsupported Certainty" 错误类型，用于训练 | 多模态生成端训练，不测核查器 |
| Expression Gap、Jagged Judges、Sanity Checks for Reasoning-Based Hallucination Detection | 模型内部认识状态与 hedge 输出；LLM 评审在施压下的稳定性；推理轨迹上的幻觉检测 | 不相关 |

**Gate 0 状态更新：** 仍是 `PASS_WITH_CONDITIONS`。新颖性仍是 `PROVISIONAL`，原因是 Epistemic Erosion 附录没有通读、Wührl 数据许可未查，而且 arXiv 上 2026-11 之后的新稿需要在投稿前再查一次。
