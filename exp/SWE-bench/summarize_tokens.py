"""
Summarize the token log written by exp.py (<version>_token_usage.jsonl): tokens per instance and per agent.
Token Reduction Rate of a config B against a baseline A = 1 - mean_tokens(B) / mean_tokens(A),
computed over the instances both runs finished.

Usage:
    python exp/SWE-bench/summarize_tokens.py A_token_usage.jsonl [B_token_usage.jsonl ...]
"""
import json
import sys
from collections import defaultdict


def load(log_path):
    per_instance = defaultdict(int)
    per_agent = defaultdict(lambda: [0, 0])
    call_num, truncated_num = 0, 0
    with open(log_path) as f:
        for line in f:
            entry = json.loads(line)
            tokens = (entry["prompt_tokens"] or 0) + (entry["completion_tokens"] or 0)
            per_instance[entry["instance_id"]] += tokens
            per_agent[entry["agent"]][0] += entry["prompt_tokens"] or 0
            per_agent[entry["agent"]][1] += entry["completion_tokens"] or 0
            call_num += 1
            truncated_num += entry["truncated"]
    return per_instance, per_agent, call_num, truncated_num


def main(log_path_list):
    run_list = [(log_path, *load(log_path)) for log_path in log_path_list]
    common_instance_set = set.intersection(*[set(run[1].keys()) for run in run_list])
    baseline_mean = None
    for log_path, per_instance, per_agent, call_num, truncated_num in run_list:
        mean_tokens = sum(per_instance[i] for i in common_instance_set) / max(len(common_instance_set), 1)
        print(f"== {log_path}")
        print(f"   instances: {len(per_instance)} ({len(common_instance_set)} shared), LLM calls: {call_num}, truncated prompts: {truncated_num}")
        print(f"   mean tokens per instance (shared): {mean_tokens:,.0f}")
        if baseline_mean is None:
            baseline_mean = mean_tokens
        elif baseline_mean > 0:
            print(f"   token reduction vs. {log_path_list[0]}: {1 - mean_tokens / baseline_mean:.1%}")
        for agent, (prompt_tokens, completion_tokens) in sorted(per_agent.items()):
            print(f"   {agent:<10} prompt {prompt_tokens:>12,}  completion {completion_tokens:>10,}")


if __name__ == "__main__":
    main(sys.argv[1:])
