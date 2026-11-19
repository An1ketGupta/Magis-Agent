Note that most experiments were conducted in February 2024, and the state of [SWE-bench at that time](https://github.com/SWE-bench/SWE-bench/tree/b93ac87) may differ from the current version.

> **Capstone changes.** The steps below replace the original ones, whose data files (`swe-bench.json` on Google Drive,
> `instance_oracle_file_dict.json`, `gpt_4_selected_idx_short_patch.json` and the BM25 retrieval file) are not in the
> released repo. Everything here runs on a Linux machine with a GPU and Docker.

## 1. Environment

```bash
conda create -n magis python=3.11 -y
conda activate magis
pip install -r requirements.txt
```

Serve the backbone LLM with an OpenAI-compatible server (separate environment recommended), e.g. vLLM:

```bash
vllm serve Qwen/Qwen2.5-7B-Instruct --served-model-name Qwen2.5-7B-Instruct --max-model-len 32768 --port 8000
```

All settings are environment variables (see [config.py](../../config.py)):

| Variable | Default | Meaning |
|---|---|---|
| `MAGIS_LLM_BASE_URL` | `http://localhost:8000/v1` | OpenAI-compatible endpoint |
| `MAGIS_LLM_API_KEY` | `EMPTY` | API key, if the server needs one |
| `MAGIS_LLM_TEMPERATURE` | `0.0` | `none` = server default |
| `MAGIS_LLM_SEED` | unset | sampling seed |
| `MAGIS_LLM_MAX_TOKENS` / `MAGIS_LLM_MAX_CONTEXT` | `4096` / `32768` | completion limit / context window; longer prompts are truncated and logged |
| `MAGIS_REPO_PATH` | `~/SWE-bench-repo` | the 12 SWE-bench repositories |
| `MAGIS_RUN_DIR` | unset | everything a run writes: `work/` (agents' copies, Custodian notes), `result/` (predictions, token log), `patches/`, `magis.db`. **Use a new one per run**: the Custodian reuses notes from earlier issues |
| `MAGIS_WORK_DIR` / `MAGIS_RESULT_DIR` / `MAGIS_DB_PATH` | under `MAGIS_RUN_DIR` | override single locations |
| `MAGIS_REDIS_CACHE` | `0` | `1` = cache LLM responses in Redis (`redis-server --daemonize yes`) |

## 2. Data

```bash
bash exp/SWE-bench/setup_repos.sh                                  # clone the 12 repositories
python exp/SWE-bench/prepare_dataset.py --dataset lite             # or: verified
python exp/SWE-bench/bm25_retrieval.py --swe_bench_tasks exp/SWE-bench/assets/lite.json
```

`prepare_dataset.py` removes the gold patch and the tests from the agents' task file, and writes the files changed
by the gold patch to a separate file that is only read with `--oracle`.

## 3. Run

```bash
export MAGIS_RUN_DIR=~/runs/A_lite
python exp.py --swe_bench_tasks exp/SWE-bench/assets/lite.json --model_name Qwen2.5-7B-Instruct \
              --review --version 1 --end_idx 10      # smoke test: first 10 instances
```

| Flag | Meaning |
|---|---|
| `--review` / `--max_review_rounds N` | QA review loop (full MAGIS) / max Developer attempts (default 2) |
| `--oracle` | give the agents the gold files instead of the Custodian's retrieval (paper-comparison setting only) |
| `--hints_text` | append the issue comments to the issue (not allowed on the SWE-bench leaderboard) |
| `--start_idx`, `--end_idx`, `--max_num_for_test` | run a slice |

Outputs in `$MAGIS_RUN_DIR/result`:
- `<version>_predictions.jsonl`: final patches, in SWE-bench harness format
- `<version>_before_review_predictions.jsonl`: the Developer's first attempt (= MAGIS without QA, for free)
- `<version>_token_usage.jsonl`: one line per LLM call (instance, agent, prompt/completion tokens, truncation)

Visualize the process of the agents:

```bash
cd visual_web_page/
MAGIS_RUN_DIR=~/runs/A_lite python process.py
```

![example](../../visual_web_page/example.png)

## 4. Evaluate

With the official harness (`pip install swebench`, needs Docker):

```bash
python -m swebench.harness.run_evaluation --dataset_name princeton-nlp/SWE-bench_Lite \
    --predictions_path ~/runs/A_lite/result/1_predictions.jsonl --max_workers 8 --run_id A_lite
```

Resolution rate = resolved / all instances of the split (300 for Lite, 500 for Verified), not / submitted.

Token usage per agent, and the token reduction of other runs against the first one:

```bash
python exp/SWE-bench/summarize_tokens.py ~/runs/A_lite/result/1_token_usage.jsonl ~/runs/C_lite/result/1_token_usage.jsonl
```
