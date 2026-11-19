# Codebase notes

## How MAGIS runs (`exp.py` → `process.py`)
1. `exp.py` copies each repo to `$WORK/manager/<instance_id>`, checks out `base_commit`, writes `issue_description.md`.
2. **Custodian** (`custodian.py`, only without `--oracle`): top-k BM25 files from `config.bm25_result_file_path`,
   then an LLM summary of each file (reused from earlier issues' notes in `$WORK/<repo>/<issue_number>`) and a
   0/1 relevance judgment. If the BM25 file has no entry, it summarizes **every** `.py` file in the repo.
3. **Manager** (`manager.py`): one task per candidate file, "hires" a Developer per file, runs a kick-off
   meeting (`process.Meeting`, ≤10 rounds), then has the LLM write Python that calls `member.work()` in order
   and **`exec`s it** (fallback: all members in sequence).
4. **Developer** (`member.py: work`): LLM picks a line range in the numbered file, the range is replaced with
   `# [NEW CODE]`, the LLM writes the replacement; `git diff` gives the patch. With `--review`, QA
   (`quality_assurance.py`) reviews the diff and rates 1–3; below 3, the Developer retries (≤`max_try_times`,
   edits accumulate, no revert).
5. `merge_code_change` concatenates per-member patches → `<version>_predictions.jsonl`.

## Quirks to watch (not changed, behavior-relevant)
- **Truncation can cut the instructions (open decision).** MAGIS prompts put the code first and the `# TODO`
  instructions last; our truncation (like MAGIS's for gpt-4-1106) keeps the head, so on files larger than the
  context the instructions are lost, the answer cannot be parsed and the edit fails ("Nothing changed.").
  Seen in the Config B mock test with a large file. Options: truncate the code part instead of the end, or
  keep it and report it. Check how often it happens (`truncated` in the token log) in the smoke test.
- Code-block parsing splits on `` ```Python `` exactly (capital P, the Pygments lexer name). If the model writes
  `` ```python ``, the edit silently fails and the log says `Nothing changed.` Count these in the smoke test.
- Editing from line 1 inserts a blank first line (`before_modify_code` is empty). Patches still apply.
- Kick-off meeting and member order are LLM-generated; `exec` of model output is part of MAGIS's design.
- Loggers add handlers twice, so lines appear twice in logs.
- Relevance answers that are neither 0 nor 1 default to 1 (relevant).

## What Step 0 changed (commit `80e9b82`)
- `chat_with_LLM.py`: OpenAI-compatible HTTP client (no `openai` SDK); temperature/seed/max_tokens from config;
  context-length errors → truncate via vLLM `/tokenize` and retry; failures raise instead of `exit(1)`;
  Redis cache optional and namespaced.
- `config.py`: everything via env vars; `MAGIS_RUN_DIR` isolates a run (work/, result/, patches/, magis.db);
  no conda requirement; `review`/`max_try_times` settings.
- `exp.py`: `--oracle` fixed (was always on), `--oracle_file_path`, `--review`, `--max_review_rounds`,
  no default subset file, per-instance token-log context, harness-format predictions (final and
  before-review), a failed task no longer kills the run.
- `member.py`: QA settings read at call time. `common.py`: tiktoken fallback. `database_manager.py`: schema created.
- New: `token_usage.py`, `exp/SWE-bench/{prepare_dataset,bm25_retrieval,summarize_tokens}.py`, `setup_repos.sh`,
  `requirements.txt`, `.gitattributes` (LF for `.sh`).
- Later (branch `config-b-langgraph`): `member.py` folder names always unique (D7); `Member.work(feedback=...)`
  shows a test-failure report in every try (None = unchanged behavior); `token_usage.agent(name)` labels calls
  made outside the agent modules. Config B lives in `repair/` + `run_repair.py` (see `DESIGN_CONFIG_B.md`).
- BM25 is our recreation (`rank_bm25`, path + content of `.py` files at base commit, identifier-split tokens),
  not SWE-bench's Pyserini index; report it as such.
