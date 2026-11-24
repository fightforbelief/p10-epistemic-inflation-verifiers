# Pilot software check

The public MiniCheck.score method was run in the Windows project environment on a fixed hash-ordered selection from the 300 v1 pilot documents. Fifty sentence pairs and fifty abstract pairs were selected before comparing scores. Both encoder checkpoints were verified against their pinned cached revisions. Comparison used the previously recorded SciFact-segmented replay. Upstream code is at commit b58b9fa69acbd1015ec970fa65dd752413a053d2. The English punkt_tab data came from the official nltk_data archive (SHA-256 e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106). The project used nltk 3.10.4 and accelerate 1.16.0.

| Model | Matching binary verdicts | Largest absolute probability difference |
|---|---:|---:|
| MiniCheck RoBERTa | 100/100 | 0.00114 |
| MiniCheck DeBERTa | 100/100 | 0.00180 |

Both checks share the same 100 inputs. Agreement is a spot check. Use the upstream method for confirmatory scores. The official source archive was installed with pip --no-deps for the encoder-only path after the environment installed nltk and accelerate. Run scripts/check_minicheck_package.py with the two checkpoints available offline and NLTK_DATA pointing to the unpacked language tables. Row-level results are in runs/package_parity_v1/comparison.json. The base requirements-lock.txt records the earlier pilot environment.

[Official repository at the tested revision](https://github.com/Liyan06/MiniCheck/tree/b58b9fa69acbd1015ec970fa65dd752413a053d2)
