"""
Measure block skeleton pruning (repair/pruning.py) on the files changed by the gold patches, without an LLM:
for each token budget, how much smaller the Developer's view of the file gets, and whether the lines the
gold patch edits are still visible (shown in full, not folded). A fix the Developer cannot see is hard to
make; expand-on-failure (Config D) can unfold such blocks later, which this does not measure.

The gold patches are read from Hugging Face only to measure; nothing here is given to an agent.

Usage:
    python exp/SWE-bench/analyze_pruning.py --output_dir ~/analyses/lite
"""
import argparse
import json
import os
import random
import re
import statistics
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config
from repair import pruning

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def edited_lines(patch):
    """file -> old-file line numbers the patch removes or changes (for pure insertions: the line before)."""
    result = dict()
    current_file = None
    old_line = None
    for line in patch.splitlines():
        if line.startswith("diff --git"):
            current_file = re.match(r"diff --git a/(\S+) b/", line).group(1)
            result.setdefault(current_file, set())
        elif line.startswith("@@"):
            old_line = int(HUNK_RE.match(line).group(1))
        elif old_line is None or line.startswith("---") or line.startswith("+++"):
            continue
        elif line.startswith("-"):
            result[current_file].add(old_line)
            old_line += 1
        elif line.startswith("+"):
            result[current_file].add(max(old_line - 1, 1))
        else:
            old_line += 1
    return result


def read_file(repo_path, commit, file_path):
    result = subprocess.run(["git", "show", f"{commit}:{file_path}"], cwd=repo_path, capture_output=True)
    return result.stdout.decode("utf-8", errors="ignore") if result.returncode == 0 else None


def main(args):
    from datasets import load_dataset
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_pretrained(args.tokenizer)
    count_tokens = lambda text: len(tokenizer.encode(text, add_special_tokens=False).ids)
    scorer = {"bm25": pruning.bm25_scores, "named_first": pruning.named_first_scores}[args.scorer]
    dataset = list(load_dataset(args.dataset, split="test"))
    if args.exclude_lite:
        # a tuning set from the same repos as Lite that does not overlap Lite
        lite_ids = {instance["instance_id"] for instance in load_dataset("princeton-nlp/SWE-bench_Lite", split="test")}
        dataset = [instance for instance in dataset if instance["instance_id"] not in lite_ids
                   and len(edited_lines(instance["patch"])) == 1]
        dataset = random.Random(args.seed).sample(dataset, args.sample)

    rows = []
    for idx, instance in enumerate(dataset):
        repo_path = os.path.join(config.local_repo_path, instance["repo"].replace("/", "__"))
        for file_path, lines in edited_lines(instance["patch"]).items():
            source = read_file(repo_path, instance["base_commit"], file_path)
            if source is None or not file_path.endswith(".py"):
                continue
            full = pruning.PrunedView(source.splitlines(), [], whole=True)
            row = {"instance_id": instance["instance_id"], "file": file_path,
                   "full_tokens": count_tokens(full.render()), "edited_lines": sorted(lines), "budgets": dict()}
            for budget in [0] + args.budgets: # 0 = skeleton only
                view = pruning.prune(source, instance["problem_statement"], budget, count_tokens, scorer=scorer)
                row["budgets"][budget] = {"tokens": count_tokens(view.render()), "whole": view.whole,
                                          "edits_visible": all(view.visible(n) for n in lines)}
            rows.append(row)
        print(f"[{idx+1}/{len(dataset)}] {instance['instance_id']}")

    os.makedirs(args.output_dir, exist_ok=True)
    with open(os.path.join(args.output_dir, f"pruning_{args.tag}_per_file.jsonl"), "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    summary = {"dataset": args.dataset, "exclude_lite": args.exclude_lite, "scorer": args.scorer,
               "files": len(rows), "instances": len({r["instance_id"] for r in rows}), "tokenizer": args.tokenizer,
               "full_tokens": {"median": statistics.median(r["full_tokens"] for r in rows),
                               "mean": round(statistics.mean(r["full_tokens"] for r in rows))},
               "budgets": dict()}
    for budget in [0] + args.budgets:
        stats = [r["budgets"][budget] for r in rows]
        pruned = [(r, s) for r, s in zip(rows, stats) if not s["whole"]]
        instances = dict()
        for r, s in zip(rows, stats):
            instances[r["instance_id"]] = instances.get(r["instance_id"], True) and s["edits_visible"]
        summary["budgets"][str(budget) if budget else "skeleton_only"] = {
            "files_pruned_%": round(100 * len(pruned) / len(rows), 1),
            "edits_visible_all_files_%": round(100 * sum(s["edits_visible"] for s in stats) / len(rows), 1),
            "edits_visible_pruned_files_%": round(100 * sum(s["edits_visible"] for _, s in pruned) / len(pruned), 1) if pruned else None,
            "instances_all_edits_visible_%": round(100 * sum(instances.values()) / len(instances), 1),
            "total_tokens_vs_full_%": round(100 * sum(s["tokens"] for s in stats) / sum(r["full_tokens"] for r in rows), 1),
            "median_tokens": statistics.median(s["tokens"] for s in stats),
        }
    with open(os.path.join(args.output_dir, f"pruning_{args.tag}_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="princeton-nlp/SWE-bench_Lite")
    parser.add_argument("--tokenizer", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--budgets", type=int, nargs="+", default=[2000, 4000, 8000, 16000])
    parser.add_argument("--scorer", choices=["bm25", "named_first"], default="named_first")
    parser.add_argument("--exclude_lite", action="store_true", help="sample a tuning set outside Lite")
    parser.add_argument("--sample", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--tag", default="lite", help="name of the output files")
    main(parser.parse_args())
