# P10 试点结果（2026-11-19）

> **更正（2026-11-24）：** 人工审计后本文有多处结论被修正或撤回，见 `runs/AUDIT_RESCORE_20261124.md` 第 2 节。其中 AUROC 的 NO-GO 依据是错的（MiniCheck-R 六类都 ≥ 0.90；研究者 2026-11-24 裁定按全体读、维持 GO），“71 个中的 71 个”应为“103 个中的 71 个”，report 类大多不是有效膨胀。以下原文保留作记录。

标签：`PILOT_ONLY_NOT_CONFIRMATORY`。这些数字只用于决定是否冻结正式协议，不进论文。

## 运行记录

| 项 | 值 |
|---|---|
| 机器 | hanqing-win，RTX 5070 Ti |
| 环境 | 项目根 `.venv`，Python 3.12.10，torch 2.15.0+cu132，transformers 5.23.0，numpy 2.5.5（`requirements-lock.txt`） |
| 测试 | v0 前 13 项通过；v1 前 17 项通过（新增 4 项审计回归） |
| 数据 | SciFact release tarball，SHA-256 `11c621288d41…`（全值见 `manifest.json`），5,183 篇摘要，选 300 句，每篇最多 1 句 |
| v0 | `runs/pilot_v0`，2,344 对 × 4 个核查器。规则有已知缺陷，保留作记录 |
| v1 | `runs/pilot_v1`，2,336 对 × 4 个核查器，修了审计发现的 4 类规则错误。种子和选择规则不变 |
| 启动 | 第一次用 `Start-Process` 启动（PID 3180），SSH 断开时进程被杀，没有产出。之后改用 `Win32_Process.Create`（见各 `launch.json`） |
| 核查器标签 | 两个 NLI 模型按 `id2label` 取 entailment。两个 MiniCheck 的标签是 `0/1`，取 index 1 |

## 主表（v1，supported 阈值 0.5；"降幅" = identity 的 supported 率减去该编辑的 supported 率）

**摘要作前提（接近 RAG 的设定）：**

| 编辑 | n | MiniCheck-RoBERTa-L | MiniCheck-DeBERTa-L | DeBERTa-v3-L NLI |
|---|---:|---:|---:|---:|
| identity（应支持） | 300 | 96.7% supported | 96.3% | 94.3% |
| negate（应拒绝，阳性对照） | 239 | 降幅 0.95 | 0.88 | 0.89 |
| modal may→will | 103 | **0.06** | **0.13** | 0.68 |
| suggest→demonstrate | 81 | **0.01** | **0.00** | 0.52 |
| 删 hedge 副词 | 32 | **0.03** | **0.00** | **0.22** |
| associated→causes | 42 | **0.02** | **0.02** | **0.29** |
| 删范围（in mice 等） | 44 | **0.00** | **0.00** | **0.02** |
| some→all | 27 | 0.96 | 0.81 | 0.93 |

粗体表示降幅 ≤ 0.3，也就是这类说过头的编辑基本被判成 supported。按文档 bootstrap 的 95% 区间见 `summary.json`，例如 MiniCheck-RoBERTa 上 causal 为 [0.00, 0.07]。

**只给原句作前提：** DeBERTa-v3-large NLI 能看见大部分膨胀（modal 0.92、report 0.96、hedge 0.72、causal 0.76），**唯独看不见删范围（0.05）**。MiniCheck-DeBERTa 对 causal（0.02）、scope（0.11）、hedge（0.22）、report（0.19）也基本看不见。

## 三个发现（待人工复核和正式协议确认）

1. **文档级核查在强度上几乎是盲的。** 用 MiniCheck 判断"引文是否支持这句话"，把 may 改成 will、suggest 改成 demonstrate、association 改成 causation、删掉 in mice，supported 率几乎不降（0.00–0.13）。同时否定被稳稳抓住（0.88–0.95），所以不是核查器整体失灵，而是专门对认识强度不敏感。
2. **上下文越长，越宽容。** 只给原句时，MiniCheck-RoBERTa 拒绝了 71 个 modal 膨胀中的 71 个；同样的句子换成整段摘要作前提后，其中 63 个被判 supported（hedge 10/12，scope 10/10，causal 6/7）。抽查的摘要里，被膨胀的那句通常就是全文唯一的相关表述，并没有更强的版本可以支持它。所以这不能用"摘要别处有更强证据"来解释。这需要人工全量核对。
3. **方向反了。** 只给原句时，MiniCheck-RoBERTa 和 nli-deberta-v3-base 拒绝"It is possible that X"（安全的削弱）的比例（0.60 / 0.64），高于拒绝 suggest→demonstrate（0.06）和 associated→causes（0.17 / 0.02）。它们惩罚的是字面改动，不是强度上升。

## 去/留判定（对照 README 里事先写下的规则）

- GO 条件（≥2 类膨胀在 ≥2 个核查器上降幅 ≤ 0.3，且 negate 降幅 ≥ 0.5）：**满足**。摘要前提下，两个 MiniCheck 各有 5 类，DeBERTa-large 有 3 类。
- NO-GO 条件：**都不成立**。没有哪个核查器在原句前提下对所有膨胀类型 AUROC ≥ 0.90，因为 scope 只有 0.51–0.80。
- 例外：nli-deberta-v3-base 在摘要前提下连 identity 都只判 6.0% supported，negate 降幅 0.05，没通过敏感度对照，所以**这个条件下排除该模型**，不解读它的数字。
- **结论：进入 Gate 0，也就是全文文献深查加人工编辑审计。暂不冻结正式协议。**

## 局限（必须在正式协议里处理）

- **scope_drop 的标签有争议。** 删掉限定介词短语，在存在性读法下是向上蕴含的："caused X in mice" 蕴含 "caused X"（某处）。它说过头的是*泛指*读法。正式协议要么用人工标注确定"应不支持"，要么把它单独报告，不和逻辑上明确不蕴含的类型（modal、causal、some→all）混在一起。
- 编辑由规则生成。v1 仍有已知错误：`in animal model studies` 被删成 `observations model studies`，因为匹配了 `animal` 而不是 `animal model`。另外，"seem to indicate→seem to prove" 仍带 hedge，some→all 会出现在推荐清单这类非结论句里。审计表只覆盖前 40 句。**数字在学生本人逐条核对编辑之前不能解读为效应大小。**
- 每类 n = 27–103，只有生物医学（SciFact）一个领域，阈值固定为 0.5，没有 LLM 评审，也没有 Bespoke-MiniCheck-7B。
- 模型 revision 字段是 `None`（transformers 没有暴露 commit hash）。正式协议要固定 HF 修订号。
- 这只是"受控扰动"层面。真实 RAG 输出中这类错误有多常见（README 第 2 节的贡献 3）还没有测。

## 下一步建议

1. Gate 0 文献深查：读 Epistemic Erosion（AACL 2026）和 Ramprasad & Wallace 的全文，检索 2026 年是否有"核查器 × 认识强度"的直接先例。
2. 人工审计：学生逐条标注 v1 的全部膨胀编辑（约 330 条），记录有效、无效或有争议。
3. 之后再决定正式协议：加入 LLM 评审和 7B MiniCheck，固定修订号，扩到第二个领域，并加上真实 RAG 输出的生态测量。
