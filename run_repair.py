"""
Run Config B (MAGIS + test-based, routed feedback; docs/DESIGN_CONFIG_B.md) on SWE-bench instances.
Config A is exp.py. Same dataset files, environment variables and output formats.

Example:
    MAGIS_RUN_DIR=~/runs/B_lite python run_repair.py --swe_bench_tasks exp/SWE-bench/assets/lite.json \\
        --model_name Qwen2.5-7B-Instruct --review --version 1 --end_idx 10
"""
import argparse
import json
import os
import shutil
import subprocess
import traceback

import config
import token_usage
from log import log
from repair.graph import RepairSession
from repair.sandbox import DockerRunner, LocalRunner

logger = log(__name__).get_log_obj()


def prepare_repo(task):
    # a copy of the repo at the base commit, as exp.py does
    source_repo_path = os.path.join(config.local_repo_path, task["repo"].replace("/", "__"))
    target_repo_path = os.path.join(config.virtual_env_path, "manager", task["instance_id"])
    if not os.path.exists(target_repo_path):
        shutil.copytree(source_repo_path, target_repo_path, symlinks=True)
    subprocess.run(["git", "checkout", "-q", "-f", task["base_commit"]], cwd=target_repo_path, check=True)
    subprocess.run(["git", "clean", "-fdq"], cwd=target_repo_path, check=True)
    return target_repo_path


def main(args):
    config.review = args.review
    config.max_try_times = args.max_review_rounds
    result_dir = config.exp_json_result_path
    token_usage.set_context(log_path=os.path.join(result_dir, f"{args.version}_token_usage.jsonl"))
    logger.info(f"Setting: config B, oracle={args.oracle}, hints_text={args.hints_text}, review={config.review}, "
                f"max_review_rounds={config.max_try_times}, max_feedback_rounds={args.max_feedback_rounds}, "
                f"runner={args.runner}, model={args.model_name}, temperature={config.llm_temperature}")

    with open(args.swe_bench_tasks) as f:
        swe_bench_tasks = json.load(f)
    swe_bench_tasks = swe_bench_tasks[args.start_idx:args.end_idx]
    if args.instance_ids:
        swe_bench_tasks = [task for task in swe_bench_tasks if task["instance_id"] in args.instance_ids]
    oracle_file_dict = None
    if args.oracle:
        with open(args.oracle_file_path) as f:
            oracle_file_dict = json.load(f)

    trace_path = os.path.join(result_dir, f"{args.version}_traces.jsonl")
    done_instance_id_set = set()
    if os.path.exists(trace_path):
        with open(trace_path) as f:
            done_instance_id_set = {json.loads(line)["instance_id"] for line in f}

    for idx, task in enumerate(swe_bench_tasks):
        instance_id = task["instance_id"]
        if instance_id in done_instance_id_set:
            logger.info(f"Skip {instance_id} (done)")
            continue
        logger.info(f"Processing Task {idx+1}/{len(swe_bench_tasks)}: {instance_id}")
        token_usage.set_context(instance_id=instance_id)
        trace = {"instance_id": instance_id}
        patch = None
        try:
            repo_path = prepare_repo(task)
            issue = task["problem_statement"]
            if args.hints_text:
                with open(os.path.join(repo_path, "hints_text.md"), "w") as f:
                    f.write(task["hints_text"])
            if args.runner == "docker":
                runner = DockerRunner(instance_id, timeout=args.test_timeout)
            else:
                runner = LocalRunner(repo_path, python=args.python, timeout=args.test_timeout)
            session = RepairSession(issue, repo_path, runner, args.model_name, args.version,
                                    candidate_files=oracle_file_dict[instance_id] if oracle_file_dict else None,
                                    max_feedback_rounds=args.max_feedback_rounds, hints_text=args.hints_text,
                                    bm_top_k=args.bm_top_k)
            patch, final_state = session.run()
            trace.update({"reproduced": final_state.get("reproduced"),
                          "reproduction_attempts": len(session.reproduction_attempts),
                          "reproduction_script": session.script,
                          "resolved_by_reproduction_test": final_state.get("resolved"),
                          "candidate_files": final_state.get("candidate_files"),
                          "rounds": final_state.get("history", []),
                          "final_patch_lines": len((patch or "").splitlines())})
        except Exception:
            logger.error(f"Task {instance_id} failed:\n{traceback.format_exc()}")
            trace["error"] = traceback.format_exc()

        # SWE-bench harness format, written per instance so that an interrupted run can be resumed
        with open(os.path.join(result_dir, f"{args.version}_predictions.jsonl"), "a") as f:
            f.write(json.dumps({"instance_id": instance_id, "model_name_or_path": f"{args.version}_B",
                                "model_patch": patch if patch and patch.strip() else None}) + "\n")
        with open(trace_path, "a") as f:
            f.write(json.dumps(trace) + "\n")
        logger.info(f"========= Task {instance_id} ({idx+1}/{len(swe_bench_tasks)}) finished =========")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--swe_bench_tasks", type=str, default="exp/SWE-bench/assets/lite.json")
    parser.add_argument("--model_name", default="Qwen2.5-7B-Instruct")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--start_idx", type=int, default=None)
    parser.add_argument("--end_idx", type=int, default=None)
    parser.add_argument("--instance_ids", nargs="+", default=None)
    parser.add_argument("--oracle", action="store_true", default=False, help="(Optional) gold files instead of the Custodian")
    parser.add_argument("--oracle_file_path", type=str, default=None)
    parser.add_argument("--hints_text", action="store_true", default=False)
    parser.add_argument("--review", action="store_true", default=False, help="MAGIS's LLM review loop (on in A and B)")
    parser.add_argument("--max_review_rounds", type=int, default=2)
    parser.add_argument("--max_feedback_rounds", type=int, default=3, help="test-feedback rounds after the first attempt")
    parser.add_argument("--bm_top_k", type=int, default=20)
    parser.add_argument("--runner", choices=["docker", "local"], default="docker")
    parser.add_argument("--python", default="python3", help="interpreter for --runner local")
    parser.add_argument("--test_timeout", type=int, default=300)
    args = parser.parse_args()
    if args.oracle_file_path is None:
        args.oracle_file_path = f"{args.swe_bench_tasks.rsplit('.json', 1)[0]}_oracle_file_dict.json"
    main(args)
