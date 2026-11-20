import os

home_path = os.path.expanduser("~")

# All paths and LLM settings can be overridden with environment variables, so that
# different runs (configs A/B/C, seeds) can be isolated without editing this file.
local_repo_path = os.environ.get("MAGIS_REPO_PATH", os.path.join(home_path, "SWE-bench-repo"))
if not os.path.exists(local_repo_path):
    print(f"Warning: SWE-bench repos not found at {local_repo_path} (see exp/SWE-bench/README.md)")
# MAGIS_RUN_DIR keeps everything a run writes in one folder. Use a new one per run: the Custodian
# reuses the file notes it finds in the working directory from earlier issues.
run_dir = os.environ.get("MAGIS_RUN_DIR")
# Working directory for agents' repo copies and the Custodian's file notes.
virtual_env_path = os.environ.get("MAGIS_WORK_DIR", os.path.join(run_dir, "work") if run_dir else os.path.join(home_path, "virtual_env"))
if not os.path.exists(virtual_env_path):
    print(f"Creating the folder for Agents: {virtual_env_path}...")
    os.makedirs(virtual_env_path)
exp_json_result_path = os.environ.get("MAGIS_RESULT_DIR", os.path.join(run_dir, "result") if run_dir else os.path.join(home_path, "exp/SWE-bench/assets/our_result"))
if not os.path.exists(exp_json_result_path):
    print(f"Creating the folder for Agents: {exp_json_result_path}...")
    os.makedirs(exp_json_result_path)
# per-member patches (merged into the final patch of each instance)
exp_result_save_path = os.path.join(run_dir, "patches") if run_dir else os.path.join(os.path.dirname(os.path.abspath(__file__)), "exp/SWE-bench")
db_path = os.environ.get("MAGIS_DB_PATH", os.path.join(run_dir, "magis.db") if run_dir else os.path.join(os.path.dirname(os.path.abspath(__file__)), "sqlite_db/magis.db"))
print(f"Database path: {db_path}")

# LLM endpoint
# - "openai_compatible": any OpenAI-style /chat/completions server (vLLM, SGLang, OpenAI itself, ...)
# - "cloudflare": the original MAGIS setup (GPT models through a Cloudflare AI gateway)
llm_channel = os.environ.get("MAGIS_LLM_CHANNEL", "openai_compatible")
llm_base_url = os.environ.get("MAGIS_LLM_BASE_URL", "http://localhost:8000/v1")
API_TOKEN = os.environ.get("MAGIS_LLM_API_KEY", "EMPTY") # vLLM accepts any token unless started with --api-key
cloudflare_account_id = os.environ.get("MAGIS_CLOUDFLARE_ACCOUNT_ID", "")
cloudflare_gateway = os.environ.get("MAGIS_CLOUDFLARE_GATEWAY", "")

# Sampling. Default is greedy (0.0) for a reproducible baseline. Set MAGIS_LLM_TEMPERATURE=none to
# send no temperature and use the server's default, as the original MAGIS did with the OpenAI API.
_temperature = os.environ.get("MAGIS_LLM_TEMPERATURE", "0.0")
llm_temperature = None if _temperature.lower() == "none" else float(_temperature)
llm_seed = int(os.environ["MAGIS_LLM_SEED"]) if os.environ.get("MAGIS_LLM_SEED") else None
# Max completion tokens per call, and the model's total context window (prompt + completion).
# Prompts that do not fit are truncated (and the truncation is recorded in the token log).
llm_max_tokens = int(os.environ.get("MAGIS_LLM_MAX_TOKENS", "4096"))
llm_max_context = int(os.environ.get("MAGIS_LLM_MAX_CONTEXT", "32768"))
# How over-long prompts are cut: "middle" keeps the start and the end (where MAGIS puts the
# instructions), "head" keeps only the start (MAGIS's original strategy, which can lose the instructions).
llm_truncation = os.environ.get("MAGIS_TRUNCATION", "middle")
llm_truncation_tail_ratio = float(os.environ.get("MAGIS_TRUNCATION_TAIL_RATIO", "0.3"))

# Redis response cache (off by default; needs `redis-server` running).
# Keys include the namespace, so repeated runs (e.g. different seeds) do not share answers.
use_redis_cache = os.environ.get("MAGIS_REDIS_CACHE", "0") == "1"
cache_namespace = os.environ.get("MAGIS_CACHE_NAMESPACE", "")

bm25_result_file_path = os.environ.get("MAGIS_BM25_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "exp/SWE-bench/file_name_and_contents.retrieval_with_LLM.jsonl"))

# QA (code review) loop between Developer and QA Engineer. The released code had it off;
# the paper's full MAGIS has it on. exp.py sets these from --review / --max_review_rounds.
review = False
max_try_times = 2
