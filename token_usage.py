"""
Per-call token accounting, used for the Token Reduction Rate metric.
Each LLM call is appended as one JSON line to the file set with `set_context`.
"""
import contextlib
import inspect
import json
import os
import time

# module file -> agent role (as named in the MAGIS paper)
AGENT_BY_MODULE = {
    "custodian.py": "custodian",
    "manager.py": "manager",
    "member.py": "developer",
    "quality_assurance.py": "qa",
    "process.py": "meeting",
}

_context = {"instance_id": None, "log_path": None, "agent": None}


def set_context(instance_id=None, log_path=None):
    if log_path is not None:
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        _context["log_path"] = log_path
    _context["instance_id"] = instance_id


@contextlib.contextmanager
def agent(name):
    # attribute the LLM calls made inside this block to `name` (for code outside the MAGIS agent modules)
    previous = _context["agent"]
    _context["agent"] = name
    try:
        yield
    finally:
        _context["agent"] = previous


def caller_agent():
    if _context["agent"] is not None:
        return _context["agent"]
    # the first frame (from the innermost) that belongs to one of the agents' modules
    for frame_info in inspect.stack()[2:]:
        agent = AGENT_BY_MODULE.get(os.path.basename(frame_info.filename))
        if agent is not None:
            return agent
    return "other"


def record(model_name, usage, cached=False, truncated=False, latency=None, agent=None):
    if _context["log_path"] is None:
        return
    usage = usage or {}
    entry = {
        "time": time.time(),
        "instance_id": _context["instance_id"],
        "agent": agent or caller_agent(),
        "model": model_name,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "cached": cached,
        "truncated": truncated,
        "latency": latency,
    }
    with open(_context["log_path"], "a") as f:
        f.write(json.dumps(entry) + "\n")
