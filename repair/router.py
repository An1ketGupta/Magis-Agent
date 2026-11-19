"""
Decide which agent handles a failed verification (see docs/DESIGN_CONFIG_B.md, "route").
"""
from dataclasses import dataclass, field

from repair import traceback_parser

RESOLVED = "Issue resolved"
REPRODUCED = "Issue reproduced"

END = "end"
DEVELOP = "develop"
PLAN = "plan"
RELOCALIZE = "relocalize"


@dataclass
class Verdict:
    resolved: bool
    route: str
    reason: str
    signature: str = None
    new_files: list = field(default_factory=list) # files to add to the candidates (RELOCALIZE)
    target_files: list = field(default_factory=list) # files whose Developers should work again (DEVELOP)
    critique: str = ""


def normalize(file_path):
    # MAGIS lists files either as "pkg/mod.py" or "./pkg/mod.py"
    return file_path[2:] if file_path.startswith("./") else file_path


def output_signature(output):
    # a failure without a traceback is identified by its last non-empty output lines
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return "output:" + " | ".join(lines[-3:])


def truncate(text, max_chars=3000):
    if len(text) <= max_chars:
        return text
    return f"...[{len(text) - max_chars} characters cut]...\n" + text[-max_chars:]


def decide(run, patch, candidate_files, previous_signature, round_index, max_rounds):
    """
    run: sandbox.RunResult of the reproduction test on the patched repo.
    round_index: 0 for the initial attempt; max_rounds: number of feedback rounds allowed after it.
    """
    output = run.output
    if run.apply_ok and RESOLVED in output and REPRODUCED not in output:
        return Verdict(True, END, "reproduction test passes")
    candidate_files = {normalize(file_path) for file_path in candidate_files}

    parsed = traceback_parser.parse(output, repo_roots=[run.repo_root])
    frame = parsed.last_repo_frame if parsed is not None else None
    if frame is not None and frame.path not in candidate_files:
        # the failure is in code no Developer was given (whatever the patch looks like)
        verdict = Verdict(False, RELOCALIZE, f"failure in {frame.path}, which was not retrieved",
                          signature=parsed.signature(), new_files=[frame.path])
    else:
        if not patch or not patch.strip():
            verdict = Verdict(False, DEVELOP, "empty patch", signature="empty-patch")
        elif not run.apply_ok:
            verdict = Verdict(False, DEVELOP, "patch does not apply", signature="apply-failed")
        elif frame is not None and parsed.exception_type in ("SyntaxError", "IndentationError", "TabError"):
            verdict = Verdict(False, DEVELOP, "syntax error in the patched code", signature=parsed.signature(),
                              target_files=[frame.path])
        elif frame is not None:
            verdict = Verdict(False, DEVELOP, f"{parsed.exception_type} in {frame.path}",
                              signature=parsed.signature(), target_files=[frame.path])
        else:
            verdict = Verdict(False, DEVELOP, "reproduction test still fails", signature=output_signature(output))
        if verdict.signature == previous_signature:
            # the Developers' retry did not change the outcome: re-plan
            verdict.route = PLAN
            verdict.reason += ", same as the previous round"

    verdict.critique = make_critique(verdict, run, parsed)
    if round_index >= max_rounds:
        verdict.route = END
        verdict.reason += " (no feedback rounds left)"
    return verdict


def make_critique(verdict, run, parsed):
    parts = [f"The reproduction test for this issue still fails after your change ({verdict.reason})."]
    if not run.apply_ok:
        parts.append(f"## Patch application output\n```\n{truncate(run.apply_output, 1500)}\n```")
    if parsed is not None and parsed.exception_type:
        location = ""
        if parsed.last_repo_frame is not None:
            frame = parsed.last_repo_frame
            location = f" at {frame.path}, line {frame.line}, in {frame.func}"
        parts.append(f"## Error\n{parsed.exception_type}: {parsed.exception_message}{location}")
    parts.append(f"## Test output\n```\n{truncate(run.output)}\n```")
    return "\n\n".join(parts)
