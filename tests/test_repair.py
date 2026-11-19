"""
Unit tests for Config B's traceback parsing, routing and local sandbox. Run from the repo root:
    python -m pytest tests
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repair import router, traceback_parser
from repair.sandbox import LocalRunner, RunResult

CRASH_IN_REPO = """Traceback (most recent call last):
  File "/work/repro.py", line 3, in <module>
    print(add(1, "2"))
  File "/testbed/pkg/calc.py", line 2, in add
    return a + b
  File "/opt/miniconda3/envs/testbed/lib/python3.9/site-packages/numpy/core/fromnumeric.py", line 5, in f
    x()
TypeError: unsupported operand type(s) for +: 'int' and 'str'
"""

SYNTAX_ERROR = """Traceback (most recent call last):
  File "/work/repro.py", line 1, in <module>
    from pkg.calc import add
  File "/testbed/pkg/calc.py", line 3
    return a +
              ^
SyntaxError: invalid syntax
"""


def run_result(output, apply_ok=True):
    return RunResult(output=output, returncode=1, apply_ok=apply_ok, apply_output="error: patch failed")


def test_parse_frames_and_exception():
    parsed = traceback_parser.parse("some output\n" + CRASH_IN_REPO)
    assert [frame.in_repo for frame in parsed.frames] == [False, True, False]
    assert parsed.last_repo_frame.path == "pkg/calc.py"
    assert parsed.last_repo_frame.func == "add"
    assert parsed.exception_type == "TypeError"
    assert parsed.signature() == "TypeError@pkg/calc.py:add"


def test_parse_syntax_error_frame_without_function():
    parsed = traceback_parser.parse(SYNTAX_ERROR)
    assert parsed.exception_type == "SyntaxError"
    assert parsed.last_repo_frame.path == "pkg/calc.py"
    assert parsed.last_repo_frame.line == 3


def test_parse_no_traceback():
    assert traceback_parser.parse("Issue reproduced\n") is None


def test_resolved():
    verdict = router.decide(run_result("Issue resolved\n"), "diff", ["pkg/calc.py"], None, 0, 3)
    assert verdict.resolved and verdict.route == router.END


def test_resolved_requires_applied_patch():
    verdict = router.decide(run_result("Issue resolved\n", apply_ok=False), "diff", ["pkg/calc.py"], None, 0, 3)
    assert not verdict.resolved and verdict.route == router.DEVELOP and verdict.signature == "apply-failed"


def test_empty_patch_goes_to_developer():
    verdict = router.decide(run_result("Issue reproduced\n"), "  \n", ["pkg/calc.py"], None, 0, 3)
    assert verdict.route == router.DEVELOP and verdict.reason == "empty patch"


def test_syntax_error_goes_to_developer_of_that_file():
    verdict = router.decide(run_result(SYNTAX_ERROR), "diff", ["pkg/calc.py"], None, 0, 3)
    assert verdict.route == router.DEVELOP and verdict.target_files == ["pkg/calc.py"]


def test_failure_in_unretrieved_file_relocalizes():
    verdict = router.decide(run_result(CRASH_IN_REPO), "diff", ["pkg/other.py"], None, 0, 3)
    assert verdict.route == router.RELOCALIZE and verdict.new_files == ["pkg/calc.py"]


def test_candidate_paths_with_dot_slash_match():
    verdict = router.decide(run_result(CRASH_IN_REPO), "diff", ["./pkg/calc.py"], None, 0, 3)
    assert verdict.route == router.DEVELOP and verdict.target_files == ["pkg/calc.py"]
    assert "TypeError" in verdict.critique and "pkg/calc.py, line 2, in add" in verdict.critique


def test_same_failure_twice_replans():
    verdict = router.decide(run_result(CRASH_IN_REPO), "diff", ["pkg/calc.py"], "TypeError@pkg/calc.py:add", 1, 3)
    assert verdict.route == router.PLAN


def test_wrong_behavior_without_traceback():
    first = router.decide(run_result("Issue reproduced\n"), "diff", ["pkg/calc.py"], None, 0, 3)
    assert first.route == router.DEVELOP
    second = router.decide(run_result("Issue reproduced\n"), "diff", ["pkg/calc.py"], first.signature, 1, 3)
    assert second.route == router.PLAN


def test_empty_patch_with_failure_in_unretrieved_file_relocalizes():
    verdict = router.decide(run_result(CRASH_IN_REPO), "", ["pkg/other.py"], None, 0, 3)
    assert verdict.route == router.RELOCALIZE and verdict.new_files == ["pkg/calc.py"]


def test_repeated_empty_patch_replans():
    verdict = router.decide(run_result("Issue reproduced\n"), "", ["pkg/calc.py"], "empty-patch", 1, 3)
    assert verdict.route == router.PLAN


def test_no_rounds_left_ends():
    verdict = router.decide(run_result(CRASH_IN_REPO), "diff", ["pkg/calc.py"], None, 3, 3)
    assert verdict.route == router.END and not verdict.resolved


def make_repo(path):
    os.makedirs(os.path.join(path, "pkg"))
    with open(os.path.join(path, "pkg", "__init__.py"), "w") as f:
        f.write("")
    with open(os.path.join(path, "pkg", "calc.py"), "w") as f:
        f.write("def add(a, b):\n    return a - b\n")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"], cwd=path, check=True)


SCRIPT = "from pkg.calc import add\nprint('Issue resolved' if add(1, 2) == 3 else 'Issue reproduced')\n"
FIX = """diff --git a/pkg/calc.py b/pkg/calc.py
--- a/pkg/calc.py
+++ b/pkg/calc.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""


def test_local_runner(tmp_path):
    make_repo(str(tmp_path / "repo"))
    runner = LocalRunner(str(tmp_path / "repo"), python=sys.executable)
    base = runner.run("", SCRIPT)
    assert base.apply_ok and "Issue reproduced" in base.output
    fixed = runner.run(FIX, SCRIPT)
    assert fixed.apply_ok and "Issue resolved" in fixed.output
    broken = runner.run(FIX.replace("return a - b", "return a * b"), SCRIPT)
    assert not broken.apply_ok
    # the base repo itself is never modified
    with open(tmp_path / "repo" / "pkg" / "calc.py") as f:
        assert "a - b" in f.read()


def test_local_runner_traceback_paths_map_to_repo(tmp_path):
    make_repo(str(tmp_path / "repo"))
    runner = LocalRunner(str(tmp_path / "repo"), python=sys.executable)
    run = runner.run("", "from pkg.calc import add\nadd(1, '2')\n")
    verdict = router.decide(run, "diff", ["pkg/calc.py"], None, 0, 3)
    assert verdict.target_files == ["pkg/calc.py"] and "TypeError" in verdict.reason
