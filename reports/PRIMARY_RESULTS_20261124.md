# P10 confirmatory run, 24 November 2026

The Windows project environment scored the eight authorized configurations from 13:54:24 to 14:03:17 UTC. Each configuration had 2,320 first calls and 234 scheduled repeats across 78 repeated documents. All 20,432 scheduled IDs were present exactly once, including explicit missing values. The eight checkpoint exports shared the expected schedule fingerprint. The pre-frozen analysis returned six positive decisions and all eight control gates passed.

| Contrast | Primary result | Multiplicity-adjusted one-sided lower bound |
|---|---|---|
| H1, RoBERTa abstract | Modal 183/200 and hedge 149/150 accepted | 85.6% and 95.5% |
| H1, DeBERTa abstract | Modal 175/200 and hedge 144/150 accepted | 80.9% and 90.4% |
| H2, RoBERTa abstract minus sentence | 112 gains, 2 losses, +55.0 pp across 200 | +46.0 pp |
| H2, DeBERTa abstract minus sentence | 117 gains, 0 losses, +58.5 pp across 200 | +50.0 pp |
| H3, DeepSeek generic minus strength | 48 gains, 0 losses, −24.0 pp in acceptance under the strength prompt | +17.0 pp reduction |
| H3, Qwen generic minus strength | 123 gains, 0 losses, −61.5 pp in acceptance under the strength prompt | +53.0 pp reduction |

DeepSeek's preservation costs were 2/690 on copied claims and 3/424 on weakened claims. Qwen showed zero net cost and no switches on either control. Eight configuration-specific checks covered 427 available negative edits each. Three first-call RoBERTa abstract scores were missing because of clipping. All primary modal and hedge endpoints were observed. Repeat agreement was 936/936 for the local encoders and 930/936 for the API judges.

## Usage

| Service | Requests | Input tokens | Output tokens | Estimated CNY at list price |
|---|---:|---:|---:|---:|
| DeepSeek-V4-Pro | 5,108 | 2,164,030 | 5,108 | 6.8366 |
| Qwen3.7-Max | 5,108 | 2,402,604 | 5,108 | 29.0151 |
| Total | 10,216 | 4,566,634 | 10,216 | 35.8517 |

The estimate uses supplier-reported usage. DeepSeek reported 682,880 cached input tokens and 1,481,150 uncached input tokens. The experiment ran during the evening off-peak period in China. Qwen uses the mainland snapshot list price. Account credits and invoice adjustments can change the amount paid. All API results used first-token log probabilities. The four MiniCheck configurations used the existing research GPU. [DeepSeek pricing](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/) · [Alibaba Cloud pricing](https://help.aliyun.com/zh/model-studio/model-pricing)

## Provenance and reproduction

| Frozen object | SHA-256 |
|---|---|
| Roster | a1cc701bbe406099ae464a2a8de8d0e5acb586e5283f15183b9180452977343d |
| Labels | d274c5c83f174a2269f9272d85ba14b50aebb282bbd5586ea8d9b3e096a1490c |
| Call schedule, canonical JSON fingerprint | 7b3def27c6bbec7a600371d42133d2ad7195214cfc0604fd526251f82e5c9c4e |

The [decision export](primary_decisions.json) contains the complete frozen primary analysis. The [aggregate export](primary_aggregate.json) records per-file score digests, served model IDs, API usage, class-conditional rates with exact two-sided descriptive intervals, the matched weakening contrasts, and the well-formed subset rates. The [strict modal export](primary_strict_modal.json) contains the remaining paired results for the 191 modal documents rated well formed. Document IDs, item-level confirmatory scores, labels and source texts are absent from all three exports.

See the [execution procedure](../docs/PRIMARY_EXECUTION.md), [analysis freeze](../docs/SAMPLING_FREEZE_20261124.md), and [execution notes](../docs/DEVIATIONS.md). The analyst verified the deployed scoring, analysis, prompt, sampling and edit code against the corresponding local file digests. The official package and its reference implementation agreed on 100/100 pilot decisions for each checkpoint immediately before formal scoring.
