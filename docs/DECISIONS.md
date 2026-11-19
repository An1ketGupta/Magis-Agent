# Decisions

Append new entries at the end. Do not rewrite old ones; if a decision changes, add a new entry that
supersedes it.

### D1 (2026-11-19): Run a fair baseline before changing MAGIS
Every claim is relative to Config A, so A is measured first, with only the changes needed to run it
(Step 0). Behavior-changing fixes are deferred until the smoke test shows they matter.

### D2 (2026-11-19): Step 0 defaults
- Temperature 0 (reproducible baseline). Original MAGIS used the API default; `MAGIS_LLM_TEMPERATURE=none` restores it.
- Over-long prompts are truncated (head kept) and logged, as MAGIS did for gpt-4-1106-preview.
- `--oracle` off by default (upstream default made it impossible to turn off); `--end_idx` defaults to all.
- Agents' task file has the gold patch and tests removed.

### D3 (2026-11-19): The mid-sem 13.82% result is void
It was never run. It must not appear in the final report or any paper; real baseline numbers replace it.

### D4 (2026-11-19): Reframe the contribution
"MAGIS has no feedback loop" is wrong (it has an LLM-review loop). The contribution is execution-grounded
feedback routed to the responsible agent, combined with pruning. Reason: reviewers who know MAGIS would
reject the original claim.

### D5 (2026-11-19, provisional): Keep the mid-review system, evaluate it with budget-matched comparisons
Literature survey (`LITERATURE.md`): "loop + pruning" alone reads as a combination; budget allocation
(context vs rounds vs samples) for small models is the clearest gap. Build is identical either way, so
building starts now and the evaluation choice is confirmed later. Needs supervisors' agreement.
Phase 3 QLoRA pruner becomes optional; a training-free block pruner comes first (LaMR and SWE-Pruner Pro
already cover trained pruners).

### D6 (2026-11-19): Project documentation in the repo
Docs live in `docs/` (versioned, visible to the teammate on GitHub); `CLAUDE.md` gives each new session the
essentials.

### D7 (2026-11-19): Fix MAGIS's shared Developer folders (affects A and B)
Developers are named by an LLM call and the name is their folder. Upstream only made names unique with
`prepare_member_folder=True`, which MAGIS's pipeline never sets, so two Developers with the same name shared
a folder and patch file; the merged patch then held the same diff twice, which `patch --batch` (used by the
SWE-bench harness) treats as reversed and silently undoes. Found in the Config B mock test. Fixed in
`member.py`: names are always made unique within a team. This is a correctness fix, so A uses it too.

### D8 (2026-11-19): Config B design
LangGraph graph around the unchanged MAGIS agents (`docs/DESIGN_CONFIG_B.md`), so A vs. B isolates the
effect of test feedback. Reproduction scripts in the Agentless format, written from the issue only; a
deterministic router (traceback location → Developer / Custodian / Manager). Regression tests deferred to v2.
