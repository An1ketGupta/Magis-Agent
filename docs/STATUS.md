# Status

_Last updated: 2026-11-20_

## Where we are
- **Step 0, Config B v1 and the 2026-11-20 work are on `main`** (merged from `truncation-and-analyses`,
  pushed to GitHub): middle truncation (D9), DockerRunner fix, skeleton pruning module (C2, D10), no-LLM analyses,
  machine check script, review notes (`REVIEW_PREP.md`). 28 unit tests pass.
- **Infrastructure verified on the laptop (E4):** the official harness resolves 5/5 gold patches on offline
  repos (flask, pytest); Config B's DockerRunner + router behave as designed on a real SWE-bench image, after a
  fix (it was testing the unpatched installed copy). requests instances fail even with gold (live-network
  tests): expect some instances unresolvable in our environment.
- **First numbers (no LLM, E2/E3):** BM25 top-20 file recall 77.7% on Lite; the file to fix overflows 32k in
  21.7% of issues; the Custodian reads a median 190k tokens/issue; skeleton pruning v2 keeps all gold edits
  visible in 71.7% of issues at 8k tokens (45% of the tokens), 90.3% at 16k.
- **Still no resolution rate.** The mid-sem 13.82% was never run.
- Review in ~4 days (from 2026-11-20); paper in ~2–3 months.

## Next steps (GPU from 2026-11-21)
1. Connect over Tailscale/SSH; run `bash exp/SWE-bench/check_machine.sh` on the GPU machine.
2. vLLM + Qwen2.5-7B-Instruct; clone repos (`setup_repos.sh`), `prepare_dataset.py`, BM25 file
   (copy of `exp/SWE-bench/results/analyses_lite/bm25_lite_top50.jsonl` can be used as `MAGIS_BM25_FILE`).
3. Gold check of all 300 Lite instances with the harness (which are unresolvable even with gold).
4. Config A smoke test (10–20 instances): check truncation counts, "Nothing changed.", ```` ```python ```` parsing.
5. Config A and Config B on the same instances (as many as time allows before the review), scored with
   `--dataset_name SWE-bench/SWE-bench_Lite`.
6. Wire pruning into the Developer (C2), then D; Config B v2 (regression tests).

## GPU machine (from the lab's spec sheet, 2026-11-20; verify with `check_machine.sh`)
Tyrone Camarero TDI100C3R-212: 1× NVIDIA L4 24 GB, 2× Xeon Gold 6342 (48C/96T), 256 GB RAM,
2× 3.84 TB + 2× 960 GB SATA SSD, OS listed as CentOS (`SETUP_GPU_ACCESS.md` assumed Windows: check). Shared
with other students. Fits Qwen2.5-7B (bf16/FP8, 32k); a stronger second model only quantized (Coder-14B, or
Qwen3-Coder-30B-A3B in 4-bit). Old CentOS 7 (glibc 2.17) would need vLLM in Docker.

## Waiting on the user
- GPU access: Tailscale name/IP, username, and the OK to run long jobs on it.
- Review format (slides/report/demo); supervisors' OK on Path B; AI-assistance rules.

## Laptop state
- Cleaned 2026-11-20: SWE-bench images, repo clones and HF cache deleted; WSL and Docker disks compacted
  (C: free 103.5 GB). Kept: `~/.magis-test-venv` (swebench 5.0.2, tokenizers), small logs in `~/runs`, `~/analyses`.
- Docker Desktop's WSL integration for Ubuntu is now on.
