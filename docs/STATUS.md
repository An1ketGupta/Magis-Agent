# Status

_Last updated: 2026-11-19_

## Where we are
- **Step 0 done**, merged into `main`: MAGIS runs against any OpenAI-compatible LLM server (vLLM/Qwen), with
  token logging, fixed `--oracle`/QA flags, recreated data files and harness-format predictions.
- **Config B v1 built** (branch `config-b-langgraph`, not merged yet): LangGraph graph around the unchanged
  MAGIS agents + reproduction test + routed feedback (`DESIGN_CONFIG_B.md`). Tested only with a mock LLM and
  the local sandbox (`EXPERIMENTS.md` E1). The Docker sandbox has not run on a real SWE-bench image yet.
- Two MAGIS bugs found by the tests: shared Developer folders (fixed, D7, affects A too) and truncation that
  can cut the instructions (open decision, `CODEBASE_NOTES.md`).
- **Direction chosen provisionally** (`DECISIONS.md` D3–D5): build the mid-review system, evaluate it with
  budget-matched comparisons (Path B in `PLAN.md`). Waiting for supervisors' agreement.
- **No real results exist yet.** The mid-sem 13.82% was never run.

## Next steps
1. Get GPU access; check GPU/VRAM, disk (SWE-bench images need ~150–250 GB), Docker without sudo, vLLM.
2. Validate the SWE-bench harness with gold patches on 5–10 Lite instances; run `DockerRunner` on one real image.
3. Analyses that need no LLM: BM25 file recall on Lite; context-size distribution (how often 32k overflows).
4. Smoke test: Config A on 10–20 Lite instances with Qwen; check "Nothing changed." and truncation counts,
   then decide on the truncation question.
5. Full Config A baseline on Lite (+ mini-SWE-agent reference A′); then Config B smoke test.
6. Config B v2: regression tests in `verify`.

## Waiting on the user
- **Tailscale is not installed on the laptop**: install it (same account as the GPU) so Claude can reach the GPU.
- The GPU's Tailscale hostname/IP and username. A dedicated key is ready on the laptop:
  `~/.ssh/capstone_gpu` (no passphrase; public key `~/.ssh/capstone_gpu.pub` goes into the GPU account's
  `~/.ssh/authorized_keys`).
- Final-review and paper deadlines.
- Supervisors' OK on Path B; the college's and target venue's rules on AI assistance.
- Optional: API key for hosted Qwen (smoke test without the college GPU).

## Loose ends
- A clone of the SWE-bench repos into WSL `~/SWE-bench-repo` was stopped part-way (2026-11-19). Delete
  `~/SWE-bench-repo` before re-running `setup_repos.sh` (it skips folders that exist), and check no
  `git clone` is still running (`wsl -d Ubuntu -- pkill -f "git clone"`).
