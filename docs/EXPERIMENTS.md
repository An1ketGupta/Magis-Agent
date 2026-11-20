# Experiments

One entry per run. Only numbers from runs logged here may be reported. Keep failed and aborted runs too.

Template:

```
### <ID> (<date>): <short name>
- Purpose:
- Commit / branch:
- Machine:
- Model + server settings:
- Dataset / instances:
- Flags + env (oracle, hints, review, rounds, temperature, seed, budget):
- MAGIS_RUN_DIR:
- Harness run_id:
- Results: resolved x/N (y%), applied %, mean tokens/instance, truncations, failures
- Notes:
```

### E0 (2026-11-19): Step 0 plumbing test with a mock LLM
- Purpose: check that Step 0 runs end to end. **Not a performance result.**
- Commit / branch: `80e9b82`, `step0-local-llm-setup`
- Machine: laptop, WSL Ubuntu, `~/.magis-test-venv`
- Model + server: mock OpenAI-compatible server (6000-token context, canned answers), scratch script, not in repo
- Dataset: one fake repo `demo__demo-1` (planted bug in `calc.py` plus a large `big.py`)
- Runs: A = retrieval + `--review` (2 rounds); B = `--oracle`, no review
- Results: both runs produced patches that apply with `git apply`; 1 prompt truncated in A; 0 tracebacks;
  token log by agent works (A 8,548 vs B 2,114 tokens/instance); all 7 DB tables written.
  `prepare_dataset.py` on real SWE-bench Lite: 300 instances, no hidden fields.

### E1 (2026-11-19): Config B plumbing tests with a mock LLM
- Purpose: check the Config B graph end to end. **Not a performance result.**
- Branch: `config-b-langgraph`; laptop WSL, `~/.magis-test-venv` (langgraph 1.2.23); `--runner local`
- Unit tests: 16 passed (`tests/test_repair.py`: traceback parser, router, local sandbox).
- Scenario 1 (bug in a retrieved file, retrieval + `--review`): reproduction script needed 2 attempts;
  round 0 wrong fix → develop with feedback; round 1 resolved. Final patch fixes the bug on a clean checkout.
- Scenario 2 (crash in a file not given to the agents, `--oracle` with the wrong file): round 0 → relocalize
  (adds `calc.py`) → re-plan; round 2 resolved; final patch clean.
- Found and fixed: router never escalated on repeated empty patches; shared Developer folders (D7);
  open: truncation cutting instructions (`CODEBASE_NOTES.md`).
- Config A mock test (E0 script) re-run after the `member.py` change: still passes.

### E2 (2026-11-20): BM25 file recall and prompt sizes on Lite (no LLM)
- Purpose: how often MAGIS's retrieval finds the file to fix, and how often whole-file prompts overflow.
- Commit / branch: scripts as committed in `1a76a19` (`truncation-and-analyses`; run from the working tree just before)
- Machine: laptop, WSL Ubuntu, `~/.magis-test-venv`; repos cloned with `setup_repos.sh` (3.6 min)
- Dataset: SWE-bench Lite test, 300 instances (`prepare_dataset.py --dataset lite`)
- Settings: our BM25 recreation (`bm25_retrieval.py`, top 50, path + content of `.py` files); Qwen2.5-7B-Instruct
  tokenizer; context 32,768, completion reserve 4,096 → prompt budget 28,672. Developer prompt = numbered gold
  file + 600-token estimate for the task text (a lower bound); Custodian = whole file + 150. Gold files used
  only to measure.
- Outputs: `~/analyses/lite/{bm25_lite_top50.jsonl, per_instance.jsonl, summary.json}` (WSL)
- Results:
  - BM25 recall (all gold files in top k): top-1 38.0%, top-5 64.0%, top-10 70.3%, **top-20 77.7%** (MAGIS's
    Custodian default), top-50 89.0%. Lowest top-20 by repo: pytest 58.8%, pylint 66.7%, matplotlib 69.6%.
  - Developer prompt for the largest gold file: median 10,239 tokens, p90 35,852, max 116,626.
    **21.7% of instances overflow 32k** (46.3% would overflow a 16k context).
  - Custodian: 6.5% of the 6,000 top-20 files overflow alone; it reads a median of **190,520 tokens per
    instance** (p90 389,682) to summarize its 20 files.
- Notes: with the Custodian's top 20, 22.3% of instances can only be solved if something re-localizes (Config B's
  relocalize route). Overflow is why the truncation strategy matters (D9).

### E3 (2026-11-20): Skeleton pruning, edit visibility vs. tokens (no LLM)
- Purpose: does block skeleton pruning (`repair/pruning.py`, C2) keep the lines the fix needs visible?
- Commit / branch: `1a76a19` (v2); v1 = the first version that day (no docstring folding, BM25 scorer)
- Machine: laptop WSL. Tokenizer: Qwen2.5-7B-Instruct.
- Metric: per gold file, the view at budget B (files that fit are shown whole) and whether every line the gold
  patch removes/changes (insertions: the line before) is unfolded. Gold patch used only to measure.
- Tuning set (D10): 100 instances of SWE-bench (full) test not in Lite, single-file patches, seed 0
  (`--exclude_lite`). Docstring folding: skeleton 25.3% of the full tokens. Scorer at 8k: BM25 68.0% vs.
  named-first 70.0% of instances with all edits visible (16k: 87.0% both) → named-first chosen.
- Lite (300 instances, 300 gold files; full file median 9,639 tokens), % of instances with all edits visible /
  total tokens vs. whole files:

  | Budget | v1 | v2 |
  |---|---|---|
  | skeleton only | 12.0% / 50.6% | 11.0% / 29.3% |
  | 4k | 44.0% / 53.7% | 52.7% / 35.4% |
  | 8k | 65.7% / 59.7% | **71.7% / 45.0%** |
  | 16k | 83.3% / 71.5% | **90.3% / 63.6%** |

- Notes: of the files that actually get pruned at 8k, only 47.2% keep the edit visible: the lexical scorer is
  the weak part (the motivation for a learned scorer such as SWE-Pruner, and for expand-on-failure in D).
  Visibility is necessary, not sufficient, for a fix; resolution needs LLM runs.
