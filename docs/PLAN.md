# Plan

## Problem
MAGIS (NeurIPS 2024) resolves GitHub issues with four agents: Manager → Custodian (file retrieval) →
Developer (edits) → QA. For small open models it has two weaknesses:
1. **No execution-grounded feedback.** QA only has an LLM review the diff (Developer ↔ QA, ≤2 rounds; off
   by default in the released code). Nothing runs tests, and failures never reach the Manager (re-plan) or
   Custodian (re-localize). Note: MAGIS *does* have a review loop, so never claim "no feedback loop".
2. **Whole, unpruned files as context.** Expensive, and a 32k-context 7B model overflows.

## Research question (Path B)
For a small open model with a fixed token budget per issue, where should the budget go: **richer context**,
**more feedback rounds**, or **more samples**? Does running tests help small models (it barely helps strong
ones, see "To Run or Not to Run", ISSTA 2026)? Novelty assessment: `LITERATURE.md`.

The system is the mid-review one; the budget question is how it is evaluated. Path A (minimal change) is the
same build without the budget-matched experiments, so the build can start before choosing.

## System (built in LangGraph, original MAGIS kept untouched as baseline A)
1. **Context:** skeleton view (signatures + docstrings, bodies folded with line markers) + top blocks in full
   under budget B; block scores = SWE-Pruner line scores aggregated per Tree-sitter block (training-free).
2. **Edits:** search/replace instead of MAGIS's line ranges (robust to pruning, fewer small-model errors).
3. **QA:** writes a reproduction test before patching; runs it + the repo's existing tests in the SWE-bench
   Docker image. Never uses the hidden evaluation tests.
4. **Feedback routing (≤3 rounds):** traceback frames in folded blocks → expand them, back to Developer;
   frames in files never retrieved → Custodian; same block fails twice → Manager re-plans.

## Configurations
| Config | Description |
|---|---|
| A | Original MAGIS: no oracle, no hints, QA review on |
| A′ | mini-SWE-agent, same model (single-agent reference) |
| B | + test-based routed feedback, full context |
| C1 | B + SWE-Pruner (line-level) |
| C2 | B + block skeleton pruning |
| D | C2 + expand-on-failure (full method) |
| Path B extras | budget-matched sweeps over context budget, rounds, samples; observation-masking baseline |

Metrics: resolved %, tokens/instance, patch-apply rate, syntax validity, localization recall, rounds.
Statistics: McNemar, bootstrap CIs. Benchmarks: SWE-bench Lite (main), Verified (secondary), a recent
SWE-rebench slice (contamination check). Models: Qwen2.5-7B-Instruct + a stronger small model (e.g.
Qwen3-8B / Qwen3-Coder-30B-A3B), depending on the GPU.

## Timeline (~14 weeks, adjust to deadlines)
| Weeks | Work |
|---|---|
| 1–2 | Harness check, no-LLM analyses, baselines A and A′ on Lite |
| 3–6 | B: reproduction tests, Docker runner, routing (LangGraph) |
| 7–9 | C1, C2: pruning + search/replace edits |
| 10–11 | D: expand-on-failure; budget sweeps |
| 12–14 | Second model, SWE-rebench slice, writing |

## Main risk
Qwen2.5-7B inside MAGIS without oracle files may resolve very few Lite issues (one generic agent setup got
2.67%), making differences between configs insignificant. Mitigation: add a stronger small model.
