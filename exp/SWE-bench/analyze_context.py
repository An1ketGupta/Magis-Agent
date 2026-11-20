"""
Analyses that need no LLM, on the files MAGIS's agents would see:
1. BM25 file recall: how often the files changed by the gold patch are among BM25's top-k files.
2. Context size: tokens of the prompts that carry a whole file (the Developer gets one whole, line-numbered
   file; the Custodian summarizes each of the top-k BM25 files), with the model's real tokenizer, and how
   often they exceed the context window (= truncation in a run).

The gold files are used only to measure (the oracle file written by prepare_dataset.py); nothing here is
given to an agent.

Usage:
    python exp/SWE-bench/analyze_context.py --swe_bench_tasks exp/SWE-bench/assets/lite.json \
        --oracle_file exp/SWE-bench/assets/lite_oracle_file_dict.json --output_dir ~/analyses/lite
"""
import argparse
import json
import os
import statistics
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config

RECALL_K_LIST = [1, 5, 10, 20, 50]
# Developer prompt around the numbered file (member.py): fixed text + the Manager's task and plan. An
# estimate, so the Developer numbers are a lower bound (review rounds add the diff and the review too).
DEVELOPER_PROMPT_OVERHEAD = 600
# Custodian summary prompt (custodian.py): system prompt + "Can you explain what this code file does? ..."
CUSTODIAN_PROMPT_OVERHEAD = 150


def read_file(repo_path, commit, file_path):
    result = subprocess.run(["git", "show", f"{commit}:{file_path}"], cwd=repo_path, capture_output=True)
    if result.returncode != 0:
        return None # file created by the gold patch
    return result.stdout.decode("utf-8", errors="ignore")


def numbered(content):
    # same format as operate.get_file_content(add_number=True)
    return "\n".join(f"{i+1} | {line}" for i, line in enumerate(content.splitlines()))


def percentile(values, q):
    values = sorted(values)
    return values[min(len(values)-1, int(round(q * (len(values)-1))))]


def describe(values):
    return {"n": len(values), "median": statistics.median(values), "p90": percentile(values, 0.9),
            "max": max(values), "mean": round(statistics.mean(values), 1)}


def main(args):
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_pretrained(args.tokenizer)
    count = lambda text: len(tokenizer.encode(text, add_special_tokens=False).ids)
    budget = args.max_context - args.max_tokens

    with open(args.swe_bench_tasks) as f:
        task_list = json.load(f)
    with open(args.oracle_file) as f:
        gold_files = json.load(f)
    bm25 = dict()
    with open(args.bm25_file) as f:
        for line in f:
            each = json.loads(line)
            bm25[each["instance_id"]] = [hit["docid"] for hit in each["hits"]]

    os.makedirs(args.output_dir, exist_ok=True)
    rows = []
    for idx, task in enumerate(task_list):
        instance_id = task["instance_id"]
        repo_path = os.path.join(config.local_repo_path, task["repo"].replace("/", "__"))
        commit = task["base_commit"]
        gold = gold_files[instance_id]
        ranked = bm25.get(instance_id, [])
        issue_tokens = count(task["problem_statement"])

        recall = dict()
        for k in RECALL_K_LIST:
            found = [file_path for file_path in gold if file_path in ranked[:k]]
            recall[k] = {"any": len(found) > 0, "all": len(found) == len(gold), "fraction": len(found) / len(gold)}

        # Developer: one whole numbered file + task text; the instance overflows if any gold file does
        developer_tokens = []
        for file_path in gold:
            content = read_file(repo_path, commit, file_path)
            if content is not None:
                developer_tokens.append(count(numbered(content)) + DEVELOPER_PROMPT_OVERHEAD)
        # Custodian: one summary call per top-k file, with the whole file (no issue text) in the prompt
        custodian_tokens = []
        for file_path in ranked[:args.custodian_top_k]:
            content = read_file(repo_path, commit, file_path)
            if content is not None:
                custodian_tokens.append(count(content) + CUSTODIAN_PROMPT_OVERHEAD)

        rows.append({"instance_id": instance_id, "repo": task["repo"], "gold_files": gold,
                     "recall": recall, "issue_tokens": issue_tokens,
                     "developer_tokens": developer_tokens, "custodian_tokens": custodian_tokens})
        print(f"[{idx+1}/{len(task_list)}] {instance_id}: gold in top-20={recall[20]['all']}, "
              f"largest gold file prompt={max(developer_tokens, default=0)} tokens")

    with open(os.path.join(args.output_dir, "per_instance.jsonl"), "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    n = len(rows)
    summary = {"instances": n, "tokenizer": args.tokenizer, "context_window": args.max_context,
               "completion_reserve": args.max_tokens, "prompt_budget": budget,
               "custodian_top_k": args.custodian_top_k, "recall": dict(), "context": dict()}
    for k in RECALL_K_LIST:
        summary["recall"][f"top{k}"] = {
            "all_gold_files_found_%": round(100 * sum(r["recall"][k]["all"] for r in rows) / n, 1),
            "any_gold_file_found_%": round(100 * sum(r["recall"][k]["any"] for r in rows) / n, 1),
            "mean_file_recall_%": round(100 * statistics.mean(r["recall"][k]["fraction"] for r in rows), 1)}

    developer_max = [max(r["developer_tokens"]) for r in rows if r["developer_tokens"]]
    custodian_all = [t for r in rows for t in r["custodian_tokens"]]
    custodian_total = [sum(r["custodian_tokens"]) for r in rows]
    summary["context"] = {
        "developer_prompt_largest_gold_file": describe(developer_max),
        "instances_where_a_gold_file_overflows_%": round(100 * sum(t > budget for t in developer_max) / n, 1),
        "instances_where_a_gold_file_overflows_16k_%": round(100 * sum(t > 16384 - args.max_tokens for t in developer_max) / n, 1),
        "custodian_prompt_per_file": describe(custodian_all),
        "custodian_files_overflowing_%": round(100 * sum(t > budget for t in custodian_all) / len(custodian_all), 1),
        "custodian_input_tokens_per_instance": describe(custodian_total),
        "issue_tokens": describe([r["issue_tokens"] for r in rows]),
    }
    by_repo = dict()
    for r in rows:
        by_repo.setdefault(r["repo"], []).append(r)
    summary["by_repo"] = {repo: {"instances": len(rs),
                                 "all_gold_in_top20_%": round(100 * sum(r["recall"][20]["all"] for r in rs) / len(rs), 1),
                                 "median_largest_gold_prompt": statistics.median([max(r["developer_tokens"]) for r in rs if r["developer_tokens"]] or [0])}
                          for repo, rs in sorted(by_repo.items())}
    with open(os.path.join(args.output_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--swe_bench_tasks", default="exp/SWE-bench/assets/lite.json")
    parser.add_argument("--oracle_file", default="exp/SWE-bench/assets/lite_oracle_file_dict.json")
    parser.add_argument("--bm25_file", default=config.bm25_result_file_path)
    parser.add_argument("--tokenizer", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max_context", type=int, default=32768)
    parser.add_argument("--max_tokens", type=int, default=4096)
    parser.add_argument("--custodian_top_k", type=int, default=20)
    parser.add_argument("--output_dir", required=True)
    main(parser.parse_args())
