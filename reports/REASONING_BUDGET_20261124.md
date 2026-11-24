# Pilot estimate for the optional reasoning arm

A hash-ordered sample of 50 abstract–claim pairs from the original v1 pilot was submitted under both prompts to each service. Each call allowed 2,048 completion tokens. All 200 calls stopped with a parseable binary answer. This pilot stored usage and completion status. It did not retain reasoning text or any confirmatory verdict.

| Model and prompt | Requests | Input tokens | Output tokens | Estimated cost for 1,000 similar requests (CNY) |
|---|---:|---:|---:|---:|
| deepseek_v4_pro_generic | 50 | 24,656 | 5,945 | 3.82–7.65 |
| deepseek_v4_pro_strength | 50 | 28,006 | 7,112 | 2.70–5.41 |
| qwen3_7_max_generic | 50 | 22,957 | 14,143 | 15.69–15.69 |
| qwen3_7_max_strength | 50 | 26,357 | 11,950 | 14.93–14.93 |

At the v0.3 planning volume of 2,200 calls per model–prompt combination (8,800 calls total), scaling the measured token and cache mix gives CNY 82–96. With a 10% allowance for repeated calls this becomes CNY 90–106. These are marginal estimates for the reasoning arm alone. The primary non-reasoning judges, software workflows, retries, and any changes in service rates require separate accounting. Recompute using the actual frozen-label schedule and current prices before requesting approval for the full run.

List prices checked on 24 November 2026. For the dated Qwen snapshot the mainland endpoint lists CNY 12 per million input tokens and 36 per million output tokens. For DeepSeek the estimate uses observed cache hits and misses at both off-peak and peak rates. The served DeepSeek alias has no immutable date. Actual account billing and discounts may differ. [Alibaba Cloud](https://help.aliyun.com/zh/model-studio/model-pricing) · [DeepSeek](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)
