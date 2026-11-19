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
