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
