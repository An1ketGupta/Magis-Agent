"""
BM25 file retrieval for the Custodian (config.bm25_result_file_path).
The released MAGIS repo does not include its retrieval file, so this recreates it in the same format:
one JSON line per instance, {"instance_id": ..., "hits": [{"docid": <file path>, "score": ...}, ...]}.

Like SWE-bench's "file_name_and_contents" BM25 setting, each document is a .py file's path plus its
contents at the instance's base commit, and the query is the issue text. Files are read with git
(no checkout), so the repositories are left untouched.

Usage:
    python exp/SWE-bench/bm25_retrieval.py --swe_bench_tasks exp/SWE-bench/assets/lite.json
"""
import argparse
import json
import os
import re
import subprocess
import sys

from rank_bm25 import BM25Okapi

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import config


def tokenize(text):
    # split identifiers too, e.g. "get_file_content" -> get, file, content; "LinuxEnv" -> linux, env
    tokens = []
    for word in re.findall(r"[A-Za-z0-9_]+", text):
        tokens.append(word.lower())
        parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+", word)
        if len(parts) > 1:
            tokens.extend(part.lower() for part in parts)
    return tokens


def read_py_files(repo_path, commit):
    file_list = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit],
                                        cwd=repo_path, text=True).splitlines()
    file_list = [file_path for file_path in file_list if file_path.endswith(".py")]
    batch_input = "".join(f"{commit}:{file_path}\n" for file_path in file_list)
    output = subprocess.run(["git", "cat-file", "--batch"], cwd=repo_path, input=batch_input.encode(),
                            capture_output=True, check=True).stdout
    documents = dict()
    position = 0
    for file_path in file_list:
        header_end = output.index(b"\n", position)
        header = output[position:header_end].split()
        if header[-1] == b"missing": # e.g. a submodule entry
            position = header_end + 1
            continue
        size = int(header[2])
        content = output[header_end+1:header_end+1+size]
        position = header_end + 1 + size + 1
        documents[file_path] = content.decode("utf-8", errors="ignore")
    return documents


def main(args):
    with open(args.swe_bench_tasks) as f:
        swe_bench_tasks = json.load(f)
    done_instance_id_set = set()
    if os.path.exists(args.output):
        with open(args.output) as f:
            done_instance_id_set = {json.loads(line)["instance_id"] for line in f}

    with open(args.output, "a") as f:
        for idx, task in enumerate(swe_bench_tasks):
            if task["instance_id"] in done_instance_id_set:
                continue
            repo_path = os.path.join(config.local_repo_path, task["repo"].replace("/", "__"))
            documents = read_py_files(repo_path, task["base_commit"])
            file_path_list = list(documents.keys())
            bm25 = BM25Okapi([tokenize(f"{file_path}\n{documents[file_path]}") for file_path in file_path_list])
            score_list = bm25.get_scores(tokenize(task["problem_statement"]))
            ranked = sorted(zip(file_path_list, score_list), key=lambda x: -x[1])[:args.top_k]
            f.write(json.dumps({"instance_id": task["instance_id"],
                                "hits": [{"docid": file_path, "score": float(score)} for file_path, score in ranked]}) + "\n")
            f.flush()
            print(f"[{idx+1}/{len(swe_bench_tasks)}] {task['instance_id']}: {len(file_path_list)} files, top-1 {ranked[0][0] if ranked else None}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--swe_bench_tasks", type=str, default="exp/SWE-bench/assets/lite.json")
    parser.add_argument("--output", type=str, default=config.bm25_result_file_path)
    parser.add_argument("--top_k", type=int, default=50)
    main(parser.parse_args())
