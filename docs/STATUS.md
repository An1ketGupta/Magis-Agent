# Status

_Last updated: 2026-11-19_

## Where we are
- **Step 0 done** (branch `step0-local-llm-setup`, commit `80e9b82`, pushed): MAGIS runs against any
  OpenAI-compatible LLM server (vLLM/Qwen), with token logging, fixed `--oracle`/QA flags, recreated data
  files and harness-format predictions. Tested end to end in WSL with a mock LLM only (see
  `EXPERIMENTS.md`, run `E0`). No real model has been run yet.
- **Direction chosen provisionally** (see `DECISIONS.md` D3–D5): build the mid-review system (LangGraph MAGIS
  + test-based feedback loop + SWE-Pruner), evaluate it with budget-matched comparisons (Path B in `PLAN.md`).
  Waiting for supervisors' agreement.
- **No real results exist yet.** The mid-sem 13.82% was never run.

## Next steps
1. Get GPU access; check GPU/VRAM, disk (SWE-bench images need ~150–250 GB), Docker without sudo, vLLM.
2. Validate the SWE-bench harness with gold patches on 5–10 Lite instances.
3. Analyses that need no LLM: BM25 file recall on Lite; context-size distribution (how often 32k overflows).
4. Smoke test: Config A on 10–20 Lite instances with Qwen; check the "Nothing changed." parse-failure rate.
5. Full Config A baseline on Lite (+ mini-SWE-agent reference A′).

## Waiting on the user
- Tailscale hostname/IP and username of the GPU machine; SSH key login (no passwords in chat).
- Final-review and paper deadlines.
- Supervisors' OK on Path B; the college's and target venue's rules on AI assistance.
- Optional: API key for hosted Qwen (smoke test without the college GPU).

## Loose ends
- A clone of the SWE-bench repos into WSL `~/SWE-bench-repo` was stopped part-way (2026-11-19). Delete
  `~/SWE-bench-repo` before re-running `setup_repos.sh` (it skips folders that exist), and check no
  `git clone` is still running (`wsl -d Ubuntu -- pkill -f "git clone"`).
