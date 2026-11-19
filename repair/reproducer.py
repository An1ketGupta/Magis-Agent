"""
QA agent, step 1: write a reproduction script from the issue text alone (Agentless format) and check that
it reproduces the issue on the unpatched repository.
"""
import re

import token_usage
from chat_with_LLM import chat
from log import log
from repair.router import REPRODUCED, RESOLVED, truncate

logger = log(__name__).get_log_obj()

SYSTEM_PROMPT = "You are a senior Python developer who writes minimal scripts that reproduce reported bugs."

USER_PROMPT = """# Issue
{issue}

# Repository
The repository is installed and importable; the script runs from the repository root.
Files that may be related to the issue:
{files}

# TODO
Write a minimal, standalone Python script that reproduces the issue above:
- If the behavior described in the issue occurs, print exactly `{reproduced}`.
- If the behavior is the expected, fixed one, print exactly `{resolved}`.
- If something else goes wrong (e.g. an unrelated error), print `Other issues`.
If the issue is a crash, catch that exception, call `traceback.print_exc()` (so the error location stays
visible), then print `{reproduced}`. Do not modify any repository files.
Respond with only the script in one ```python block."""

RETRY_PROMPT = """

# Your previous script
```python
{script}
```
It was run on the current (unfixed) repository and did not print `{reproduced}`. Its output was:
```
{output}
```
Fix the script so that it reproduces the issue on the current repository."""


def extract_code(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if blocks:
        return max(blocks, key=len)
    return text.strip()


def write_reproduction(issue, candidate_files, runner, model_name, max_tries=3):
    """Return (script, reproduced, attempts): attempts = [(script, output), ...]."""
    attempts = []
    files = "\n".join(f"- {file_path}" for file_path in candidate_files) or "(unknown)"
    user_prompt = USER_PROMPT.format(issue=issue, files=files, reproduced=REPRODUCED, resolved=RESOLVED)
    for try_index in range(max_tries):
        prompt = user_prompt
        if attempts:
            script, output = attempts[-1]
            prompt += RETRY_PROMPT.format(script=script, output=truncate(output, 2000), reproduced=REPRODUCED)
        with token_usage.agent("qa"):
            response = chat(SYSTEM_PROMPT, prompt, model_name=model_name)
        script = extract_code(response)
        run = runner.run("", script)
        attempts.append((script, run.output))
        logger.info(f"Reproduction attempt {try_index+1}:\n{script}\nOutput:\n{run.output}")
        if REPRODUCED in run.output and RESOLVED not in run.output:
            return script, True, attempts
    return attempts[-1][0] if attempts else None, False, attempts
