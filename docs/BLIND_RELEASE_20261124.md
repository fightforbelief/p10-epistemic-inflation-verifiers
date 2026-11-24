# Formal annotation packet

The Windows project verified all files in the sampling manifest, then generated a frozen roster with 910 distinct focal documents and 120 matched control edits. No formal score was computed. The Excel workbook has a Chinese instruction page followed by seven worksheets. Its question text, order, blank input cells, drop-down validation ranges, header freeze panes and stopping formulas were checked after export against all 1,030 roster records.

| Sheet | Available | Complete |
|---|---:|---|
| Modal | 330 | Through 200 valid edits, or the last row |
| Hedge | 220 | Through 150 valid edits, or the last row |
| Scope | 150 | All |
| Causal | 150 | All |
| Quantifier | 60 | All |
| Weaken | 60 | All |
| Negate | 60 | All |

The 1,030 is the maximum number of questions on reserve. The two stopping rules set the actual workload. Each of the seven sheets starts at its first data row. Send the annotator the workbook in audit/confirmatory. For reading long abstracts, the optional P10_evidence_reader.html in the same directory expands the full text by question ID. It works offline and collects no labels. The unfilled workbook has SHA-256 7e69d45ff002daecd0abdfd2fc854676f4fb872730da18c38c972b74c689f611. The local roster has SHA-256 a1cc701bbe406099ae464a2a8de8d0e5acb586e5283f15183b9180452977343d. The file hashes refer to the originally issued bytes.

## Return

The annotator returns a separately saved workbook and states whether they knew the hypotheses. At the Windows project root, validate the workbook against the issued roster and record both printed digests. This command only checks and exports human labels.

```powershell
$py = '.\.venv\Scripts\python.exe'
& $py scripts/read_confirmation_labels.py audit/confirmatory/roster.jsonl audit/confirmatory/returned.xlsx audit/confirmatory/labels.jsonl --roster-sha256 a1cc701bbe406099ae464a2a8de8d0e5acb586e5283f15183b9180452977343d
```

The validator checks the source and edited text, abstract, row order, required fields and stopping prefixes. Resolve incomplete returns with the annotator before freezing the labels. Obtain the researcher's separate approval for formal scoring after the return is validated. Use the immutable labels with scripts/primary_ledger.py and scripts/primary_analysis.py. Six real-library workflows across five packages remain secondary and require their own fidelity reports.
