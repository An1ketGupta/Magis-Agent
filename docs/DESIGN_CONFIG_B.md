# Design: Config B (LangGraph MAGIS + test-based, routed feedback)

Config B = Config A (original MAGIS) + one change: after the Developers produce a patch, QA **runs** a
reproduction test, and a failure is sent back to the agent responsible. Everything else (Custodian,
Manager, Developers, MAGIS's own LLM review) is the original MAGIS code, called through an adapter, so
that A vs. B measures the effect of execution-grounded feedback only. Context pruning (C1, C2, D) and
search/replace edits come later and plug into the same graph.

Code: `repair/` package, run with `run_repair.py`. The original MAGIS files stay usable as Config A.

## Graph
```
localize ─▶ reproduce ─▶ plan ─▶ develop ─▶ verify ─┬─▶ END (resolved / out of rounds / no reproduction)
              ▲                    ▲          ▲      ├─▶ develop     (bug in the edited code)
              │                    │          └──────┤
          relocalize ◀─────────────┼─────────────────┼─▶ relocalize  (failure in a file never retrieved)
                                   └─────────────────┴─▶ plan        (same failure twice: re-plan)
```
- **localize**: MAGIS Custodian (BM25 + LLM relevance), or the oracle files with `--oracle`.
- **reproduce** (QA agent): the LLM writes a standalone script that prints `Issue reproduced` /
  `Issue resolved` / `Other issues` (the Agentless format). It must print `Issue reproduced` on the
  unpatched code; otherwise the LLM gets the output and retries (≤2). If no script reproduces the issue,
  the instance continues without test feedback (= Config A behavior) and this is recorded.
- **plan**: MAGIS Manager: tasks per file, team, kick-off meeting, work order. On a re-plan, the failure
  report is appended to the issue text, and the team is rebuilt from clean repo copies.
- **develop**: first round: the Manager's work order (MAGIS `implement`). Later rounds: the Developers
  responsible for the files in the traceback (all of them if none match) work again, with the failure
  report in their prompt (`Member.work(feedback=...)`). MAGIS's LLM review stays on inside `work`, as in A.
- **verify**: apply the merged patch to a clean copy of the repo in the sandbox and run the reproduction
  script. Resolved = patch applies and the script prints `Issue resolved`.
- **route** (`repair/router.py`), deterministic, from the run result:
  1. resolved (patch applies, script prints `Issue resolved` and not `Issue reproduced`) → END
  2. the last traceback frame inside the repo is in a file not yet retrieved → relocalize (add that file)
     → plan. Checked first, whatever the patch looks like (an empty patch often means the wrong files).
  3. otherwise a failure signature is computed: empty patch, patch does not apply, syntax error,
     exception + location (Developers of that file), or the last output lines (no traceback)
  4. same signature as the previous round (the Developers' retry changed nothing) → plan; else → develop
  5. feedback rounds used up → END
  The reproduction prompt asks scripts that catch the issue's exception to call `traceback.print_exc()`,
  so the router still sees where it failed.
- Rounds: one initial attempt + up to `--max_feedback_rounds` (default 3) retries.

## Sandboxes (`repair/sandbox.py`)
- `DockerRunner`: the official SWE-bench instance image (`swebench/sweb.eval.x86_64.<id>`; repo at
  `/testbed`, conda env `testbed`), no network, timeout. Used for real runs.
- `LocalRunner`: a clean copy of the repo and a given Python interpreter. Only for tests and toy repos.

## Never used
The SWE-bench gold patch and hidden tests (`FAIL_TO_PASS`, `PASS_TO_PASS`, `test_patch`). The reproduction
test is written by the agent from the issue text alone.

## Not in v1 (planned)
- Regression tests (the repo's existing tests near the edited code) in `verify`.
- Patch selection across rounds (v1 returns the last patch that applies).

## Running
```bash
export MAGIS_RUN_DIR=~/runs/B_lite
python run_repair.py --swe_bench_tasks exp/SWE-bench/assets/lite.json --model_name Qwen2.5-7B-Instruct \
    --review --version 1 --end_idx 10              # --runner docker (default) needs the SWE-bench images
python -m pytest tests                              # unit tests (router, traceback parser, local sandbox)
```
`--max_feedback_rounds` (default 3), `--oracle`, `--instance_ids`, `--runner local --python <exe>` (toy repos).
A run resumes where it stopped (instances in `<version>_traces.jsonl` are skipped).

## Outputs per run (`$MAGIS_RUN_DIR/result`)
- `<version>_predictions.jsonl`: final patches (harness format)
- `<version>_token_usage.jsonl`: per-call tokens, agent = custodian/manager/developer/qa/meeting
- `<version>_traces.jsonl`: per instance: reproduction status, each round's route, failure signature, patch size
