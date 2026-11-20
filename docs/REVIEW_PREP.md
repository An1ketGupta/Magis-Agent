# Review preparation

Material for the progress review: what exists, why, the numbers we have (all from logged runs in
`EXPERIMENTS.md`), and questions to expect. Update it as results come in.

## One-line summary
We make MAGIS, a four-agent issue-fixing system built for GPT-4, work with small open models (Qwen ~7B) by
(1) running tests and sending failures back to the agent responsible and (2) showing agents pruned files
instead of whole ones, and we ask where a fixed token budget is best spent.

## What is built
| Part | Where | State |
|---|---|---|
| MAGIS on any OpenAI-compatible server (vLLM), token logging, fixed `--oracle`, harness-format output | `chat_with_LLM.py`, `exp.py`, `token_usage.py` | done, mock-tested (E0) |
| Data pipeline: Lite/Verified without gold patch and tests, BM25 recreation | `exp/SWE-bench/prepare_dataset.py`, `bm25_retrieval.py` | done |
| Config B: LangGraph graph, reproduction test, Docker sandbox, deterministic router | `repair/`, `run_repair.py` | done, mock-tested (E1); Docker test pending |
| Two MAGIS bugs fixed: shared Developer folders (D7), truncation losing instructions (D9) | `member.py`, `chat_with_LLM.py` | done, unit-tested |
| C2: skeleton pruning with expand-on-failure | `repair/pruning.py` | built, measured without LLM (E3); not wired into the agents yet |
| Analyses: retrieval recall, context overflow, pruning visibility | `exp/SWE-bench/analyze_*.py` | done (E2, E3) |
| Unit tests | `tests/` | 28 passing |

## Architecture (Config B → D)
```
Issue ─▶ Custodian ─▶ QA writes reproduction test ─▶ Manager ─▶ Developers ─▶ Verify (run test in the
          (BM25 +       (from the issue only, must      (plan)     (edit)         SWE-bench Docker image)
          LLM filter)    fail on the original code)                                 │ fails
              ▲                                            ▲          ▲              ▼
              └── crash in a file never retrieved ─────────┼──────────┼──────── Router (≤3 rounds)
                                                           └ same failure twice: re-plan
                                                                      └ bug in edited code: fix again
C2/D: Developers see a skeleton (signatures + docstring summaries, bodies folded, real line numbers);
D unfolds the block a traceback points into.
```

## Numbers we have (no LLM yet)
- **Retrieval is a ceiling** (E2): BM25 puts the file to fix in MAGIS's top 20 for 77.7% of Lite issues
  (top-1 38%). For 22% of issues the agents never see the right file unless something re-localizes; this is
  what Config B's relocalize route targets.
- **Whole files overflow small-model context** (E2): the file to fix does not fit a 32k context in 21.7% of
  Lite issues (46% at 16k). The Custodian reads a median 190k tokens per issue.
- **Skeleton pruning** (E3): at an 8k budget, the edited lines stay visible in 71.7% of issues with 45% of the
  tokens; at 16k, 90.3% with 64%. Folding docstrings mattered most (skeleton 51% → 29% of tokens).
- **Not yet:** any resolution rate. The first real runs (Config A and B with Qwen on the college GPU) are next.

## Plan
1. GPU: Config A smoke test → Config A and B on Lite, scored by the official harness.
2. Wire C2 into the Developer (with search/replace edits), then D (expand-on-failure).
3. Budget-matched comparison: the same token budget spent on context vs. feedback rounds vs. samples.
4. Second model; SWE-bench Verified and a recent SWE-rebench slice (contamination check); paper.

## Questions to expect
- **"MAGIS already has QA, isn't this a feedback loop it already has?"** MAGIS's QA only has an LLM read the
  diff; nothing is executed, and failures never reach the Manager or Custodian. We add execution-grounded
  feedback and route it. We never claim MAGIS has no loop.
- **"Do the agents see the answer?"** No. `prepare_dataset.py` strips the gold patch and the hidden tests; the
  reproduction test is written from the issue text only. The gold patch is used only to measure (E2, E3) and to
  score.
- **"Why not just use a bigger context?"** The analysis shows 22% of files overflow 32k, and cost grows with
  context; the research question is exactly where a fixed budget helps most.
- **"Why skeleton pruning instead of SWE-Pruner?"** SWE-Pruner is line-level and needs a 0.6B model per call;
  block folding keeps syntax intact and line numbers stable for MAGIS's edits, and SWE-Pruner can serve as the
  block scorer (C1 vs. C2 is one of our comparisons).
- **"Why only 47% visibility for pruned files?"** The lexical block scorer is weak on large files; this is why D
  unfolds blocks on test failure and why a learned scorer is planned. It is measured, not hidden.
- **"Is the 13.82% from mid-sem real?"** No, it was never run and is withdrawn (D3); every number now comes from a
  logged run.
