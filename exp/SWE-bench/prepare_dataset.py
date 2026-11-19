"""
Download a SWE-bench split from Hugging Face and write the files exp.py needs
(the released MAGIS repo points to a Google Drive file and an oracle file that are not available).

Writes into exp/SWE-bench/assets/:
- <name>.json: the task instances given to the agents. The gold patch and the tests are removed,
  so they cannot leak into the agents' prompts.
- <name>_oracle_file_dict.json: instance_id -> files changed by the gold patch (for the --oracle setting only).

Usage:
    python exp/SWE-bench/prepare_dataset.py --dataset lite
    python exp/SWE-bench/prepare_dataset.py --dataset verified
"""
import argparse
import json
import os
import re

from datasets import load_dataset

DATASETS = {
    "lite": "princeton-nlp/SWE-bench_Lite",
    "verified": "princeton-nlp/SWE-bench_Verified",
    "full": "princeton-nlp/SWE-bench",
}
# fields that reveal the solution or the evaluation tests
HIDDEN_FIELDS = ["patch", "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS"]


def changed_files(patch):
    return sorted(set(re.findall(r"^diff --git a/(\S+) b/", patch, flags=re.MULTILINE)))


def main(args):
    dataset = load_dataset(DATASETS[args.dataset], split=args.split)
    os.makedirs(args.output_dir, exist_ok=True)

    task_list = []
    oracle_file_dict = dict()
    for instance in dataset:
        oracle_file_dict[instance["instance_id"]] = changed_files(instance["patch"])
        task_list.append({k: v for k, v in instance.items() if k not in HIDDEN_FIELDS})

    task_path = os.path.join(args.output_dir, f"{args.dataset}.json")
    with open(task_path, "w") as f:
        json.dump(task_list, f)
    oracle_path = os.path.join(args.output_dir, f"{args.dataset}_oracle_file_dict.json")
    with open(oracle_path, "w") as f:
        json.dump(oracle_file_dict, f)

    repo_list = sorted(set(each["repo"] for each in task_list))
    print(f"{len(task_list)} instances from {DATASETS[args.dataset]} ({args.split}) saved to {task_path}")
    print(f"Oracle files saved to {oracle_path}")
    print(f"Repositories needed ({len(repo_list)}): {', '.join(repo_list)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=DATASETS.keys(), default="lite")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output_dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))
    main(parser.parse_args())
