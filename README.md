# P10：引用核查器会不会把"说过头"的结论判成"有依据"？

**2026-11-24 · 正式盲标已发放，等待人工回填。** 样本排除了两轮试点的全部 339 篇论文。先阅读 [盲标交付记录](docs/BLIND_RELEASE_20261124.md) 和 [抽样冻结补充](docs/SAMPLING_FREEZE_20261124.md)。历史试点只用于定设计。[结果论文工作稿](paper/manuscript.md) 已有引言、方法和解释范围，正式结果待盲标、标签冻结及另行批准打分后补入。

[真实库抽查](reports/NATIVE_LIBRARY_CHECK_20261124.md) 已完成六个流程各 50 对；Phoenix hallucination 复现低于门槛，正式比较排除。推理模式已完成两种评审、两种提示的[成本预试](reports/REASONING_BUDGET_20261124.md)。

原始试点材料和盲标工作簿保存在项目本地。复现者可用官方 SciFact 归档和公开句子索引，通过 Windows 项目环境运行 `scripts/restore_pilot_items.py`，恢复抽样程序所需的两份试点索引原件，再按冻结清单复查。以下为项目沿革。

---

## 1. 原 P10 的评估

原题（`archived/goals_archived.pdf`）：*RAG for Scientific QA with Provenance and Hallucination Calibration*。内容是建论文语料库、做 RAG 系统，然后测 citation correctness、retrieval sufficiency、faithfulness 和 abstention。文档自己给的评级是 Medium–High。

**结论：照原样不值得做，也写不成有意义的论文。** 理由如下：

1. **没有可证伪的研究问题。** 交付物是"语料库 + RAG 系统 + 评测包 + 报告"，按本组合的阶梯属于 L0 工程。它不回答任何未知问题。
2. **领域已经很挤。** 2024–2026 年已有 REASONS（科学引用的弃答与幻觉）、ResearchQA（有依据的拒答）、CiteEval/CiteBench、ScholarQABench、OpenScholar/PaperQA2 一类系统，以及 CLEF 2026 LongEval-RAG 的 citation faithfulness 赛道。再做一个"科学 RAG + 引用评测"，最好的结果也只是又多一个基准。
3. **和以往的失败模式一样。** `PORTFOLIO_LINE_HISTORY.md` 里 P1、P3、旧 P12 和 P19 的理论收窄都是在文献门或新颖性门停下的。原 P10 进门之前就是这个形态。
4. **不符合"要洞见、不要流水线论文"的要求。**

## 2. 新方向：认识强度膨胀与核查器的盲区

**一句话问题：** RAG 评测普遍用 NLI 或 MiniCheck 一类核查器判断"这句话有没有被引文支持"。来源只说"可能"、"在小鼠中"、"与……相关"，生成的句子却说"会"、"普遍如此"、"导致"。这时核查器还会判"supported"吗？

这是一个可证伪的测量问题。按逻辑蕴含，"X may reduce Y" **不**蕴含 "X reduces Y"。严格的 NLI 应当拒绝膨胀后的句子，同时接受被削弱的句子（"It is possible that …"）。核查器如果对加强和削弱一视同仁，就是**方向盲**。

**为什么现在有空档（检索截至 2026-11-19，标准检索，未用付费库）：**
- *Epistemic Erosion*（Nnamdi et al., AACL 2026）用规则匹配的 EFS 测量**生成端**确定性的流失，并指出 NLI/QA 类 faithfulness 方法只查"是否支持"，不查确定性是否保留。从摘要看，它没有直接压力测试**核查器本身**。
- Peters & Chin-Yee（R. Soc. Open Sci. 2025）发现 LLM 科学摘要的过度概括是专家的约 5 倍，但测的是生成，不是评测器。
- Ramprasad & Wallace 对事实性指标做了压力测试（对良性编辑过敏、可被灌水），MontageLie 测的是因果顺序。两者都不是认识强度。
- **还没有核实**：上面两篇的全文，以及 2026 年是否有直接撞题的工作。这是 Gate 0 的第一件事。

**可能的贡献（按强弱排列）：**
1. 一个受控的最小对基准：6 类膨胀，配 3 个对照（原句、削弱、否定）。
2. 对主流核查器的盲区测量：哪些类型被看见，哪些看不见；整段摘要作前提时盲区是否变大。
3. （生态部分）真实 RAG 输出里，"被判为 supported 却膨胀了"的句子占多少。这一条决定结论是否有实际意义。
4. （若前三条成立）一个便宜的修补：双向或强度感知的检验，例如同时要求 claim ⊨ source 的弱化方向。

**跨 CV 的用途：** NLP/MIIS（RAG 评测）、Stats（检验的方向性与校准）、Applied DS（评测可靠性）。它也和 P12 的主线一致：评测流程默默决定了结论。

## 3. 试点设计（这次准备运行的部分）

- **数据：** SciFact corpus（5,183 篇生物医学摘要），用官方 release tarball，记录 SHA-256。每篇摘要最多抽 1 句，按 `SHA-256(seed:doc_id:idx)` 排序选 N=300 句，选择与任何分数无关。
- **编辑**（`src/perturb.py`，纯规则，可单测）：
  - 膨胀：`modal_strengthen`（may→will）、`report_verb_upgrade`（suggest→demonstrate）、`hedge_adverb_drop`、`causal_upgrade`（associated with→causes）、`scope_drop`（in mice / in vitro / in this cohort）、`quantifier_inflate`（some→all）
  - 对照：`identity`（应支持）、`weaken`（应支持）、`negate`（应不支持，作敏感度阳性对照）
- **前提条件：** 只给原句；给整段摘要（更接近 RAG）。整段摘要里如果别处有不带 hedge 的结果句，膨胀句可能*确实*有依据。所以两种条件要分开报告，并人工复核。
- **核查器：** DeBERTa-v3-large NLI（MoritzLaurer）、nli-deberta-v3-base、MiniCheck-RoBERTa-L、MiniCheck-DeBERTa-v3-L。LLM 评审和 Bespoke-MiniCheck-7B 不在本次试点内。
- **指标：** 每个核查器 × 前提 × 编辑类型分别给出 supported 率（阈值 0.5）、相对 identity 的 supported 率下降（按文档 bootstrap 1,000 次，95% 区间），以及 AUROC(identity vs edit)。
- **人工复核：** `edit_audit_sheet.jsonl` 收录前 40 句的全部编辑。规则编辑可能不合语法或改变语义，必须由学生本人判断后才能解读数字。

**预先写下的去/留规则：**
- **NO-GO：** `negate` 的下降小于 0.5（核查器根本不敏感，测不出东西）；或者所有膨胀类型在 sentence 前提下的 AUROC 都 ≥ 0.90（盲区不存在）。
- **GO 到 Gate 0 文献深查：** 至少 2 类膨胀在 ≥2 个核查器上 supported 率下降 ≤ 0.3，且 `negate` 下降 ≥ 0.5。
- 无论结果如何，试点数字都不进论文，只用于决定是否冻结正式协议。

## 4. 运行（按 RULES.md，在 hanqing-win 上）

本项目在 Windows 项目根目录维护自己的 `.venv`，所有阶段共用。依赖清单是 `requirements.txt`（torch 固定为 2.15.0+cu132；不固定时 PyPI 会装上 CPU 版），安装后的实际版本冻结在 `requirements-lock.txt`。下载：SciFact（约 3 MB）和 4 个 HF checkpoint（合计约 3 GB）。

```powershell
Set-Location 'C:\Users\hanqi\Desktop\projects\Research_Portfolio_2026\p10-epistemic-inflation-verifiers'
# 仅首次：py -3.12 -m venv .venv; & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
$py = '.\.venv\Scripts\python.exe'
& $py -B -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw "P10 tests failed ($LASTEXITCODE)" }
& $py scripts/pilot_score.py --n 300 --out runs/pilot_v0
```

产物：`runs/pilot_v0/{manifest,summary}.json`、`scores.jsonl`、`items.jsonl`、`edit_audit_sheet.jsonl`、`run_complete.json`。

## 5. 本地测试

`tests/` 共 13 项。Mac 上 9 项纯标准库测试和 2 项选择/配对测试通过。另外 2 项需要 numpy，本机 miniconda 的 numpy 是空壳（未修复，不属于本项目），留到 Windows 上跑。

## 6. 人工编辑审计（Gate 0 条件 6）

- 工作簿：`audit/P10_edit_audit_v1.xlsx`，由 `scripts/build_audit_sheet.py` 在 hanqing-win 的项目 `.venv` 中生成（为此在 `requirements.txt` 加了 `openpyxl`，锁定为 3.1.5）。同样的行另存为 `audit/edit_audit_v1.jsonl`，用于把标注接回分数。
- `Inflations` 表：pilot_v1 打过分的全部 329 条加强编辑。每条回答四个问题：Q1 编辑是否完好；Q2 只看两句，是否比原句更强；Q3 整段摘要能否支持编辑后的说法（用来检验"上下文越长越宽容"是不是因为摘要别处本来就有更强的说法）；Q4 只针对删范围的行，读者会按泛指还是存在性理解（用来解决 scope 的标签争议）。
- `Controls` 表：随机抽取削弱、否定各 40 条，检查对照编辑是否符合预期。
- 盲法：工作簿里没有任何核查器或评审的输出。行序用种子 20261119 打乱。20% 的行（82 条）标为 `double_code`，供第二人独立标注，用来算一致性。
- 预计约 4 小时。标完后用脚本把 Q1=broken 的行排除，并按 Q2/Q3/Q4 重算各项降幅。重算脚本在拿到标注后再写。
- **2026-11-24：** 第一份标注已回收并重算，见 `runs/AUDIT_RESCORE_20261124.md`。研究者决定不做第二人标注，按单人标注结项（`double_code` 作废，不报一致性）；AUROC 条款有歧义，研究者裁定按全体读、维持 GO（事后解释，见该报告第 6 节）。
- **正式协议草案：** `docs/PROTOCOL_DRAFT_v0.3_20261124.md`（未冻结；五个待定项已定，规则 v2 已写，旧版留作记录）。
