import argparse
import json
import os
import shutil

import config
import token_usage
from log import log
from process import main as process_main
logger = log(__name__).get_log_obj()


def save_predictions(gen_result_list, save_path):
    # SWE-bench harness format (one JSON object per line); an empty patch counts as "no prediction"
    with open(save_path, "w") as f:
        for each_result in gen_result_list:
            patch = each_result["model_patch"]
            f.write(json.dumps({"instance_id": each_result["instance_id"],
                                "model_name_or_path": str(each_result["model_name_or_path"]),
                                "model_patch": patch if patch and patch.strip() else None}) + "\n")


def main(args):
    config.review = args.review
    config.max_try_times = args.max_review_rounds
    token_usage.set_context(log_path=os.path.join(config.exp_json_result_path, f"{args.version}_token_usage.jsonl"))
    logger.info(f"Setting: oracle={args.oracle}, hints_text={args.hints_text}, review={config.review}, "
                f"max_review_rounds={config.max_try_times}, model={args.model_name}, temperature={config.llm_temperature}")

    with open(args.swe_bench_tasks) as f:
        swe_bench_tasks = json.load(f)

    if args.idx_list_file_path is not None:
        with open(args.idx_list_file_path) as f:
            idx_list = json.load(f)
        swe_bench_tasks = [swe_bench_tasks[idx] for idx in idx_list]
        logger.info(f"Selected {len(idx_list)} tasks from SWE-bench")

    if args.filter_repofullname is not None:
        swe_bench_tasks = [task for task in swe_bench_tasks if task['repo'] == args.filter_repofullname]
        logger.info(f"Selected {len(swe_bench_tasks)} tasks from SWE-bench after filtering by repo {args.filter_repofullname}")

    if args.sort_by_issue:
        swe_bench_tasks = sorted(swe_bench_tasks, key=lambda x: x['created_at'])
        logger.info(f"Sorted by issue number")

    if args.start_idx is not None or args.end_idx is not None:
        swe_bench_tasks = swe_bench_tasks[args.start_idx:args.end_idx]
        logger.info(f"Selected {len(swe_bench_tasks)} tasks from SWE-bench")
    
    if args.max_num_for_test is not None:
        if args.max_num_for_test == -3:
            selected_instance_id_list = ['django__django-14373', 'sympy__sympy-21806', 'sympy__sympy-13372']
            swe_bench_tasks = [task for task in swe_bench_tasks if task['instance_id'] in selected_instance_id_list]
        else:
            swe_bench_tasks = swe_bench_tasks[:args.max_num_for_test]
        logger.info(f"Further selected {len(swe_bench_tasks)} tasks from SWE-bench")
    
    result_save_path = os.path.join(config.exp_json_result_path, f"{args.version}.json")
    before_review_result_save_path = os.path.join(config.exp_json_result_path, f"{args.version}_before_review.json")
    if args.skip_existing and os.path.exists(result_save_path) and os.path.exists(before_review_result_save_path):
        with open(result_save_path) as f:
            gen_result_list = json.load(f)
        with open(before_review_result_save_path) as f:
            before_review_gen_result_list = json.load(f)
        exist_instance_id_list = [each_result['instance_id'] for each_result in gen_result_list \
                                  if each_result['model_name_or_path'] == args.version and each_result['model_patch'] is not None]
        gen_result_list = [each_result for each_result in gen_result_list if each_result['instance_id'] in exist_instance_id_list]
        before_review_gen_result_list = [each_result for each_result in before_review_gen_result_list if each_result['instance_id'] in exist_instance_id_list]
        swe_bench_tasks = [task for task in swe_bench_tasks if task['instance_id'] not in exist_instance_id_list]
    else:
        gen_result_list = []
        before_review_gen_result_list = []

    candidate_file_dict = None
    if args.oracle:
        with open(args.oracle_file_path) as f:
            candidate_file_dict = json.load(f)

    if os.path.exists(config.local_repo_path):
        for task in swe_bench_tasks:
            repo_full_name_str = task["repo"].replace("/", "__")
            source_repo_path = os.path.join(config.local_repo_path, repo_full_name_str)
            target_repo_path = os.path.join(config.virtual_env_path, "manager", repo_full_name_str)
            if os.path.exists(target_repo_path):
                logger.info(f"Repo {repo_full_name_str} exists")
                continue
            # copy repo folder from config.local_repo_path to config.virtual_env_path/manager
            if os.path.exists(target_repo_path):
                os.makedirs(target_repo_path, exist_ok=True)
            shutil.copytree(source_repo_path, target_repo_path, dirs_exist_ok=True)
            logger.info(f"Repo {task['repo']} copied to {target_repo_path}")
    else:
        logger.error(f"Local repo path not exists: {config.local_repo_path}")
        exit(1)

    for idx, each_task in enumerate(swe_bench_tasks):
        # preprocess for the task
        repo_full_name_str = each_task["repo"].replace("/", "__")
        source_repo_path = os.path.join(config.virtual_env_path, "manager", repo_full_name_str)
        instance_id = each_task['instance_id']
        target_repo_path = os.path.join(config.virtual_env_path, "manager", instance_id)
        if os.path.exists(target_repo_path):
            logger.info(f"Task {instance_id} exists")
            continue
        shutil.copytree(source_repo_path, target_repo_path, dirs_exist_ok=True)
        logger.info(f"Task {instance_id} copied to {target_repo_path}")

        # checkout to the base_commit
        base_commit = each_task['base_commit']
        os.chdir(target_repo_path)
        os.system(f"git checkout {base_commit}")
        logger.info(f"Task {instance_id} checked out to {base_commit}")

    logger.info("All tasks checked out to base commit. Now you can see more details at https://loacalhost:8888")

    
    os.makedirs(config.exp_json_result_path, exist_ok=True)
    if candidate_file_dict is None:
        instance_candidate_file_dict = dict()
    for idx, each_task in enumerate(swe_bench_tasks):
        instance_id = each_task['instance_id']
        target_repo_path = os.path.join(config.virtual_env_path, "manager", instance_id)
        logger.info(f"Processing Task {idx+1}/{len(swe_bench_tasks)}: {each_task['instance_id']}")
        token_usage.set_context(instance_id=instance_id)

        # run the task
        process_args = argparse.Namespace()
        process_args.repo_local_path = target_repo_path
        with open(os.path.join(target_repo_path, "issue_description.md"), "w") as f:
            f.write(each_task['problem_statement'])
        if args.hints_text:
            with open(os.path.join(target_repo_path, "hints_text.md"), "w") as f:
                f.write(each_task['hints_text'])
        # previous_comment
        # with open(os.path.join(target_repo_path, "previous_comment.md"), "w") as f:
        #     f.write(each_task['hints_text'])
        process_args.requirement_file_path = os.path.join(target_repo_path, "issue_description.md")
        if candidate_file_dict is not None:
            process_args.candidate_file_path_list = candidate_file_dict[instance_id]
        else:
            process_args.candidate_file_path_list = None
        process_args.version = args.version
        process_args.granularity = "file"
        process_args.only_find_file_list = args.only_find_file_list
        process_args.bm_top_k = args.bm_top_k
        process_args.model_name = args.model_name #"gpt-4-0613" #"gpt-3.5-turbo-0125" #"gpt-4-0613"
        process_args.cache = True
        process_args.hints_text = args.hints_text
        logger.info(process_args)
        if not args.only_find_file_list:
            # process_main returns None when the task fails; record an empty patch and continue
            patch, before_review_patch = process_main(process_args) or (None, None)

            gen_result = {"instance_id": instance_id, "model_name_or_path": process_args.version,
                        "model_patch": patch}
            gen_result_list.append(gen_result)

            before_review_gen_result = {"instance_id": instance_id, "model_name_or_path": f"{process_args.version}_before_review",
                                        "model_patch": before_review_patch}
            before_review_gen_result_list.append(before_review_gen_result)

            with open(os.path.join(config.exp_json_result_path, f"{process_args.version}.json"), "w") as f:
                json.dump(gen_result_list, f)

            with open(os.path.join(config.exp_json_result_path, f"{process_args.version}_before_review.json"), "w") as f:
                json.dump(before_review_gen_result_list, f)
        else:
            candidate_file_list = process_main(process_args)
            instance_candidate_file_dict[instance_id] = candidate_file_list
            with open(os.path.join(config.exp_json_result_path, f"{process_args.version}_candidate_file_list.json"), "w") as f:
                json.dump(instance_candidate_file_dict, f)

        logger.info("-"*50)
        logger.info(f"========= Task {instance_id} ({idx+1}/{len(swe_bench_tasks)}) finished =========")
        logger.info("-"*50)
    
    if not args.only_find_file_list:
        with open(os.path.join(config.exp_json_result_path, f"{args.version}.json"), "w") as f:
            json.dump(gen_result_list, f)

        with open(os.path.join(config.exp_json_result_path, f"{args.version}_before_review.json"), "w") as f:
            json.dump(before_review_gen_result_list, f)

        save_predictions(gen_result_list, os.path.join(config.exp_json_result_path, f"{args.version}_predictions.jsonl"))
        save_predictions(before_review_gen_result_list,
                         os.path.join(config.exp_json_result_path, f"{args.version}_before_review_predictions.jsonl"))
        logger.info(f"Predictions for the SWE-bench harness saved in {config.exp_json_result_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--swe_bench_tasks", type=str, help="Path to SWE-bench task instances file", 
                        default="exp/SWE-bench/assets/lite.json")
    # the paper's subset list (gpt_4_selected_idx_short_patch.json) is not in the released repo
    parser.add_argument("--idx_list_file_path", type=str, default=None)
    parser.add_argument("--model_name", default="gpt-4-0613", help="Default model name")
    parser.add_argument("--max_num_for_test", type=int, default=None)
    parser.add_argument("--start_idx", type=int, default=None)
    parser.add_argument("--end_idx", type=int, default=None)
    parser.add_argument("--skip_existing", action="store_true", help="(Optional) Skip existing logs", default=True)
    # was `default=True, action="store_true"`, which made the oracle (gold files) setting impossible to turn off
    parser.add_argument("--oracle", default=False, action="store_true", help="(Optional) Evaluate on oracle setting (gold files given)")
    parser.add_argument("--oracle_file_path", type=str, default=None,
                        help="(Optional) instance_id -> files changed by the gold patch "
                             "(default: <swe_bench_tasks>_oracle_file_dict.json, see exp/SWE-bench/prepare_dataset.py)")
    parser.add_argument("--review", action="store_true", help="(Optional) Enable the QA Engineer's review loop (full MAGIS)", default=False)
    parser.add_argument("--max_review_rounds", type=int, default=2, help="(Optional) Max Developer attempts with QA review")
    parser.add_argument("--version", type=int, default=240201) # add hints after the issue description
    parser.add_argument("--filter_repofullname", help="(Optional) keeps the repo only", default=None) # 'scikit-learn/scikit-learn')
    parser.add_argument("--sort_by_issue", action="store_true", help="(Optional) Sort by Issue Number for Each Repo", default=False)
    parser.add_argument("--hints_text", action="store_true", help="(Optional) Use hints_text with issue description", default=False)
    parser.add_argument("--only_find_file_list", action="store_true", help="(Optional) finish the process when it generates the candidate_file_list ", default=False)
    parser.add_argument("--bm_top_k", type=int, help="(Optional) Top k for BM25", default=20)
    args = parser.parse_args()
    if args.oracle_file_path is None:
        args.oracle_file_path = f"{args.swe_bench_tasks.rsplit('.json', 1)[0]}_oracle_file_dict.json"
    logger = log(__name__).get_log_obj()
    main(args)
