# Primary analysis after label return

The sampling and hypothesis rules are in the sampling freeze. Use the project-root Windows environment for every command. The original roster, returned workbook, label file, schedule, per-call scores and SQLite checkpoints stay in the local research project. The review packet contains the source abstracts and is distributed privately to the annotator.

1. Run the return command in BLIND_RELEASE_20261124.md. Record its digests, the annotator's familiarity with the hypotheses, and the UTC time before running models. Obtain the researcher's separate scoring authorization. Archive this record with the frozen labels.
2. Verify the installed encoder environment with pip check, the test suite, and the upstream pilot spot check. Set NLTK_DATA to the project's data/nltk_data directory. Both pinned encoder snapshots must be in the local Hugging Face cache. Provide the two authorized judge API credentials only to the scoring process.
3. At the project root run the template below, filling in the returned label digest. The schedule fingerprint is printed by the builder. Each configuration uses its own checkpoint. Failed calls remain explicit missing values. A repeat uses a fresh call within the same configuration.

```powershell
$py = '.\.venv\Scripts\python.exe'
$d = 'audit/confirmatory'
$rosterHash = 'a1cc701bbe406099ae464a2a8de8d0e5acb586e5283f15183b9180452977343d'
$labelHash = (Get-FileHash "$d/labels.jsonl" -Algorithm SHA256).Hash.ToLower()
& $py scripts/primary_ledger.py "$d/roster.jsonl" "$d/labels.jsonl" "$d/schedule.jsonl" --roster-sha256 $rosterHash --labels-sha256 $labelHash
if ($LASTEXITCODE -ne 0) { throw "Schedule failed" }
```

Compare the label digest to the frozen return log. After recording the printed schedule fingerprint as $scheduleHash, execute each required configuration. A local model exception interrupts the run for diagnosis. If a request terminates before checkpointing, resumption can repeat that last request.

```powershell
$env:NLTK_DATA = (Resolve-Path data/nltk_data).Path
$configs = @('minicheck_roberta_large/abstract','minicheck_roberta_large/sentence','minicheck_deberta_v3_large/abstract','minicheck_deberta_v3_large/sentence','deepseek/generic','deepseek/strength','qwen/generic','qwen/strength')
foreach ($cfg in $configs) {
  & $py scripts/score_primary.py "$d/schedule.jsonl" "$d/scored" --config $cfg --schedule-sha256 $scheduleHash
  if ($LASTEXITCODE -ne 0) { throw "Scoring interrupted on $cfg" }
}
& $py -c "from pathlib import Path; p=Path('audit/confirmatory'); fs=sorted((p/'scored').glob('*.jsonl')); assert len(fs)==8; (p/'scores.jsonl').write_bytes(b''.join(f.read_bytes() for f in fs))"
if ($LASTEXITCODE -ne 0) { throw "Incomplete score files" }
& $py scripts/primary_ledger.py "$d/roster.jsonl" "$d/labels.jsonl" "$d/decisions.json" --roster-sha256 $rosterHash --labels-sha256 $labelHash --scores "$d/scores.jsonl"
if ($LASTEXITCODE -ne 0) { throw "Analysis failed" }
```

Always show all six decisions and the control/missingness diagnostics, including absolute denominators. For each matched change show both directions of switching. The matched filler, sensitivity populations, local reference models, native-library checks, and reasoning-mode results are secondary. Report those runs separately from this primary schedule. The current packet release contains no confirmatory outcomes.

For the local descriptive filler contrast, reserve every document from either pilot and every document in the issued queues, including unused reserve rows. Rank the remaining donor documents by the source-specific hash in scripts/secondary_contrasts.py. Place the exact source sentence at the same word offset as in its own abstract, using donor words on both sides to match the word count. This procedure can cut a donor sentence at the boundary. Distinct document IDs do not guarantee unrelated subject matter. Record donor IDs, tokenizer lengths, scored chunks and any clipping. Comparing real and filler contexts identifies sensitivity to this particular replacement and leaves length, naturalness and chunking as distinct interpretive limitations.

The 24 November stage-specific environment inventories are in reports/native_environment_freeze.txt and reports/primary_environment_freeze.txt. Both use the public upstream commit in place of the local install-archive path for MiniCheck. After the native check the Windows project restored Transformers 5.23.0, retained the compatible Hub 1.33.0 and removed the temporary DeepEval installation. The dependency check passed. All 57 tests passed and the entire MiniCheck spot-check JSON matched the pre-switch run byte for byte. Pilot custody and the formal sample roster were unaffected by this environment change.
