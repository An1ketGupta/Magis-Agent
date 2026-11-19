import json
import re
import time
import hashlib
import requests

import config
import token_usage
from log import log
logger = log(__name__).get_log_obj()

API_TOKEN = config.API_TOKEN

class ResponseException(Exception):
    def __init__(self, info_dict):
        super().__init__(str(info_dict))
        self._info_dict = info_dict
        if 'message' in info_dict.keys():
            self._info_dict['_message'] = info_dict['message']

    def __getattr__(self, item):
        try:
            return self._info_dict[item]
        except KeyError:
            raise AttributeError(f"'ResponseException' object has no attribute '{item}'")


def is_context_length_error(message):
    return "maximum context length" in str(message)


def request_api(model_name, user_prompt, system_prompt, channel = config.llm_channel,
                account_id = config.cloudflare_account_id, gateway=config.cloudflare_gateway):
    if channel == "openai_compatible":
        API_BASE_URL = f"{config.llm_base_url.rstrip('/')}/chat/completions"
    elif channel  == "cloudflare":
        if "gpt" not in model_name:
            raise ValueError(f"The cloudflare channel only supports GPT models: {model_name}")
        API_BASE_URL = f"https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway}/openai/chat/completions"
    else:
        raise ValueError(f"Invalid channel: {channel}")
    headers = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}
    data = {"model": model_name,
            "messages": [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": user_prompt}]}
    if config.llm_temperature is not None:
        data["temperature"] = config.llm_temperature
    if config.llm_seed is not None:
        data["seed"] = config.llm_seed
    if config.llm_max_tokens is not None:
        data["max_tokens"] = config.llm_max_tokens
    response = requests.post(API_BASE_URL, headers=headers, json=data, timeout=60*10)
    logger.info(response.text)
    response = json.loads(response.text)
    # vLLM / OpenAI-compatible servers report errors as {"object": "error", "message": ..., "code": 400}
    if response.get("object") == "error":
        response = {"error": {"message": response.get("message", ""), "code": response.get("code")}}
    if "error" in response.keys() and is_context_length_error(response["error"].get("message")):
        response["error"]["code"] = "context_length_exceeded"
    return response


def count_prompt_tokens(model_name, system_prompt, user_prompt):
    # number of prompt tokens as counted by the serving model (vLLM's /tokenize endpoint)
    if config.llm_channel != "openai_compatible":
        return None
    base_url = config.llm_base_url.rstrip('/')
    if base_url.endswith("/v1"):
        base_url = base_url[:-len("/v1")]
    try:
        response = requests.post(f"{base_url}/tokenize", timeout=60,
                                 json={"model": model_name,
                                       "messages": [{"role": "system", "content": system_prompt},
                                                    {"role": "user", "content": user_prompt}]})
        return response.json()["count"]
    except Exception as e:
        logger.error(f"Failed to count tokens: {e}")
        return None


def truncate_to_context(model_name, system_prompt, user_prompt, error_message):
    # Keep the head of the user prompt so that prompt + completion fits in the context window
    # (the same strategy MAGIS used for gpt-4-1106-preview).
    max_prompt_tokens = config.llm_max_context - (config.llm_max_tokens or 0)
    token_num = count_prompt_tokens(model_name, system_prompt, user_prompt)
    if token_num is None:
        match = re.search(r"(\d+) (?:input )?tokens", str(error_message).split("However", 1)[-1])
        token_num = int(match.group(1)) if match else 2 * max_prompt_tokens
    for _ in range(5):
        if token_num is None or token_num <= max_prompt_tokens:
            break
        keep_ratio = max_prompt_tokens / token_num * 0.95
        user_prompt = user_prompt[:int(len(user_prompt) * keep_ratio)]
        token_num = count_prompt_tokens(model_name, system_prompt, user_prompt)
    logger.error(f"Truncated the user prompt to {len(user_prompt)} characters ({token_num} tokens)")
    return user_prompt


def atomic_chat(system_prompt, user_prompt, max_times=5, model_name=None, use_cache=False):
    use_cache = use_cache and config.use_redis_cache
    if use_cache:
        import redis
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        all_prompt = config.cache_namespace+model_name+system_prompt+user_prompt
        cache_key = hashlib.sha256(all_prompt.encode()).hexdigest()
        cached_response = r.get(cache_key)#.decode("utf-8")
        if cached_response:
            logger.debug(json.loads(cached_response))
            cached_response = json.loads(cached_response)
            token_usage.record(model_name, cached_response.get("usage"), cached=True)
            return cached_response
    try_times = 0
    truncated = False
    response = None
    while try_times < max_times:
        if try_times > 0:
            logger.debug(f"Try again... ({try_times+1}-th time)")
        try:
            start_time = time.time()
            response = request_api(model_name, user_prompt, system_prompt)
            if "error" in response.keys():
                # throw exception
                raise ResponseException(response["error"])
            if "detail" in response.keys() and "This model's maximum context length is 32768 tokens. However, you requested " in response["detail"]:
                raise ResponseException({"code": "context_length_exceeded", "_message": response["detail"]})
            token_usage.record(model_name, response.get("usage"), truncated=truncated, latency=time.time()-start_time)
            if use_cache:
                r.setex(cache_key, 60*60*24*365, json.dumps(response))
            break
        except Exception as e:
            logger.error(f"{try_times+1}-th time Error:{e}, Type(e):{type(e)}")
            if isinstance(e, ResponseException) and e.code == "context_length_exceeded":
                logger.error(e.code)
                logger.error(e._message)
                user_prompt = truncate_to_context(model_name, system_prompt, user_prompt, e._message)
                truncated = True
            elif isinstance(e, ResponseException) and e.code == "rate_limit_exceeded":
                time_to_wait = e.message.split("Please try again in ")[1].split("s.")[0]
                if 'm' in time_to_wait:
                    time_to_wait = float(time_to_wait.split("m")[0])*60 + float(time_to_wait.split("m")[1].split("s")[0])
                else:
                    time_to_wait = float(time_to_wait.split("s")[0])
                time.sleep(time_to_wait)
            else:
                time.sleep(30)
            try_times += 1
    if response is None or "error" in response.keys():
        raise ResponseException({"code": "request_failed", "message": f"No valid response after {max_times} tries: {response}"})
    return response


def chat(system_prompt, user_prompt, model_name, output_format = None, use_cache=False, remove_quote=False,
         db_manager=None, request_index=None):
    response = atomic_chat(system_prompt, user_prompt, model_name=model_name, use_cache=use_cache)

    if db_manager is not None and request_index is not None:
        db_manager.add_response(request_index, response)
    else:
        logger.debug(response)
    try:
        print(response)
        if "choices" not in response.keys() and "messages" in response.keys():
            response_txt = response['messages'][-1]['content']
        elif "choices" in response.keys() and len(response['choices']) > 0:
            response_txt = response['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Error: {e}\nresponse:{response}")
        # raise instead of exit(1), so that one bad response fails only the current task, not the whole run
        raise
    if output_format is not None:
        check_system_prompt = "You are an Information Extraction Expert. You check if the output strictly follows the format."
        check_user_prompt = f"Please determine whether the following Content (between '```' and '```') meets the Format. If so, output just 'True'. Otherwise, extract the content part that strictly follows the Format from the Content as output.\nContent:```{response_txt}```\nFormat:{output_format}"
        check_response = atomic_chat(check_system_prompt, check_user_prompt, model_name=model_name, use_cache=use_cache)
        if not check_response['choices'][0]['message']['content'] == "True":
            response_txt = check_response['choices'][0]['message']['content']

    if remove_quote:
        if len(response_txt) >= 2 and ((response_txt[0] == "\'" and response_txt[-1] == "\'") or \
            (response_txt[0] == "\"" and response_txt[-1] == "\"")):
            response_txt = response_txt[1:-1]
        if response_txt == "":
            response_txt = "<NONE>"
    return response_txt
