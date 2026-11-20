"""
Unit tests for prompt truncation (chat_with_LLM.truncate_to_context). Run from the repo root:
    python -m pytest tests
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MAGIS_RUN_DIR", tempfile.mkdtemp(prefix="magis-test-"))

import chat_with_LLM
import config

INSTRUCTIONS = "# TODO\nRewrite the code between line 10 and line 20. Answer in a ```Python block."
PROMPT = "File: big.py\n" + "".join(f"{i:5d} x = compute({i})\n" for i in range(5000)) + INSTRUCTIONS


def fake_token_count(model_name, system_prompt, user_prompt):
    return len(system_prompt + user_prompt) // 4  # roughly 4 characters per token


def truncate(monkeypatch, mode, max_context=4000, max_tokens=1000):
    monkeypatch.setattr(chat_with_LLM, "count_prompt_tokens", fake_token_count)
    monkeypatch.setattr(config, "llm_truncation", mode)
    monkeypatch.setattr(config, "llm_max_context", max_context)
    monkeypatch.setattr(config, "llm_max_tokens", max_tokens)
    return chat_with_LLM.truncate_to_context("model", "system", PROMPT, "")


def test_middle_truncation_keeps_start_and_instructions(monkeypatch):
    prompt = truncate(monkeypatch, "middle")
    assert prompt.startswith("File: big.py\n")
    assert prompt.endswith(INSTRUCTIONS)
    assert "characters omitted to fit the context window" in prompt
    assert fake_token_count("model", "system", prompt) <= 3000


def test_head_truncation_loses_instructions(monkeypatch):
    # MAGIS's original strategy: this is the failure the middle strategy avoids
    prompt = truncate(monkeypatch, "head")
    assert prompt.startswith("File: big.py\n")
    assert INSTRUCTIONS not in prompt
    assert fake_token_count("model", "system", prompt) <= 3000


def test_prompt_that_fits_is_unchanged(monkeypatch):
    assert truncate(monkeypatch, "middle", max_context=100000) == PROMPT


def test_cut_prompt_lengths(monkeypatch):
    monkeypatch.setattr(config, "llm_truncation_tail_ratio", 0.3)
    text = "a" * 700 + "b" * 300
    cut = chat_with_LLM.cut_prompt(text, 100, mode="middle")
    assert cut.startswith("a" * 70) and cut.endswith("b" * 30)
    assert "[900 characters omitted" in cut
    assert chat_with_LLM.cut_prompt(text, 100, mode="head") == "a" * 100
    assert chat_with_LLM.cut_prompt(text, 5000) == text
