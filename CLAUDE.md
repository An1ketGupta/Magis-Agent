# Capstone: Multi-Agent Program Repair with Small Open Models

BTech final-year capstone (IIITDM Kurnool) by Aniket Gupta and Akshat Jaipuriar, supervised by
Dr. N. Srinivas Naik and Dr. K. Sathya Babu. Goal: a working system, a final report, and a paper submission.

This repo is a fork of the official MAGIS code (github.com/co-evolve-lab/magis), pushed to
github.com/An1ketGupta/Magis-Agent. `main` holds merged work (upstream MAGIS = commit `5ae2591`);
new work happens on branches and is merged into `main`.

## Start of every session
1. Read `docs/STATUS.md` (current state, next steps, blockers), then whatever doc the task needs:
   - `docs/PLAN.md`: research direction, phases, configurations
   - `docs/DECISIONS.md`: decisions and their reasons (append, never rewrite history)
   - `docs/EXPERIMENTS.md`: every run, its exact settings and results
   - `docs/LITERATURE.md`: related work and novelty assessment
   - `docs/CODEBASE_NOTES.md`: MAGIS code quirks and what has been changed
2. At the end of a work session, update `docs/STATUS.md`, and log any run in `docs/EXPERIMENTS.md`.

## Rules (research integrity)
- Never report a number that was not produced by a logged run. The mid-sem report's 13.82% "reproduction"
  was never run and must not be reused anywhere.
- The agents must never see SWE-bench's gold patch, `test_patch`, `FAIL_TO_PASS` or `PASS_TO_PASS`
  (`prepare_dataset.py` strips them). Test-based feedback uses agent-written reproduction tests and the
  repo's existing tests only.
- Main results use no oracle files (`--oracle` off) and no `--hints_text`. Oracle runs are only for
  comparison with the MAGIS paper and must be labelled as such.
- Resolution rate = resolved / all instances of the split, scored by the official SWE-bench harness.
- Every run gets its own `MAGIS_RUN_DIR`, and its git commit, model, dataset, flags and seed are logged.

## Working with the user
The user is learning as the project goes: explain what was built and why in plain terms, so they can
defend it at reviews. Ask before pushing to GitHub or running anything on the shared college GPU that is
long or heavy.

## Environment
- Laptop: Windows 11, WSL Ubuntu (Python 3.12, Docker Desktop), RTX 4060 8 GB, 24 GB RAM.
  Run Linux-only code in WSL; call it through PowerShell (`wsl -d Ubuntu -- bash <script>`), not Git Bash
  (it rewrites `/mnt/c/...` paths). A test venv is at `~/.magis-test-venv` in WSL.
- College GPU: reachable over Tailscale (details pending, see `docs/STATUS.md`).
- How to run MAGIS on SWE-bench: `exp/SWE-bench/README.md`.
