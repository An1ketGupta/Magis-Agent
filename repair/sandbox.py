"""
Run a reproduction script against the repo at the instance's base commit, optionally with a patch applied.
The patch is applied the way the SWE-bench harness does it: `git apply`, then `patch --fuzz=5` as fallback.
"""
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

APPLY_SCRIPT = """
if [ -s "$WORK/patch.diff" ]; then
  if git apply --verbose "$WORK/patch.diff" > "$WORK/apply.log" 2>&1 \\
     || patch --batch --fuzz=5 -p1 -i "$WORK/patch.diff" >> "$WORK/apply.log" 2>&1; then
    echo APPLY_OK > "$WORK/apply.status"
  else
    echo APPLY_FAILED > "$WORK/apply.status"
  fi
else
  echo APPLY_OK > "$WORK/apply.status"
fi
"""


@dataclass
class RunResult:
    output: str # stdout and stderr of the script, interleaved
    returncode: int
    apply_ok: bool
    apply_output: str = ""
    timed_out: bool = False
    repo_root: str = "/testbed" # where the repo was, to map traceback paths back to repo paths


def read(path):
    if not os.path.exists(path):
        return ""
    with open(path, errors="replace") as f:
        return f.read()


def prepare_workdir(patch, script):
    workdir = tempfile.mkdtemp(prefix="magis_sandbox_")
    with open(os.path.join(workdir, "patch.diff"), "w") as f:
        f.write(patch or "")
    with open(os.path.join(workdir, "repro.py"), "w") as f:
        f.write(script)
    return workdir


def collect(workdir, completed, timed_out, repo_root="/testbed"):
    status = read(os.path.join(workdir, "apply.status")).strip()
    output = completed.stdout if completed is not None else ""
    if timed_out:
        output += "\n[sandbox] the script timed out"
    return RunResult(output=output, returncode=completed.returncode if completed is not None else -1,
                     apply_ok=status == "APPLY_OK", apply_output=read(os.path.join(workdir, "apply.log")),
                     timed_out=timed_out, repo_root=repo_root)


class DockerRunner:
    """Official SWE-bench instance images: repo at /testbed, conda env `testbed`."""
    def __init__(self, instance_id, timeout=300,
                 image_template="swebench/sweb.eval.x86_64.{instance_id}:latest"):
        self.image = image_template.format(instance_id=instance_id.replace("__", "_1776_")).lower()
        self.timeout = timeout

    def run(self, patch, script):
        workdir = prepare_workdir(patch, script)
        with open(os.path.join(workdir, "run.sh"), "w") as f:
            # Some images install the repo as a plain copy in site-packages (e.g. requests: `pip install .`),
            # so the script must import /testbed (or /testbed/src) first, or it tests the unpatched copy.
            f.write("WORK=/work\nsource /opt/miniconda3/bin/activate testbed\ncd /testbed\n"
                    f"{APPLY_SCRIPT}\n"
                    "if [ -d /testbed/src ]; then export PYTHONPATH=/testbed/src:/testbed; else export PYTHONPATH=/testbed; fi\n"
                    f"timeout {self.timeout} python /work/repro.py\n")
        completed, timed_out = None, False
        try:
            completed = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{workdir}:/work",
                                        self.image, "bash", "/work/run.sh"],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       errors="replace", timeout=self.timeout + 120)
            timed_out = completed.returncode == 124
            return collect(workdir, completed, timed_out)
        except subprocess.TimeoutExpired as e:
            completed = subprocess.CompletedProcess(e.cmd, -1, stdout=(e.stdout or b"").decode(errors="replace")
                                                    if isinstance(e.stdout, bytes) else (e.stdout or ""))
            return collect(workdir, completed, True)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


class LocalRunner:
    """A clean copy of a local repo and a given Python. For tests and toy repos only (no isolation)."""
    def __init__(self, base_repo_path, python="python3", timeout=120):
        self.base_repo_path = base_repo_path
        self.python = python
        self.timeout = timeout

    def run(self, patch, script):
        workdir = prepare_workdir(patch, script)
        repo_copy = os.path.join(workdir, "repo")
        shutil.copytree(self.base_repo_path, repo_copy, symlinks=True)
        # discard edits and untracked files so the copy is exactly the base commit
        subprocess.run(["git", "checkout", "--", "."], cwd=repo_copy, capture_output=True)
        subprocess.run(["git", "clean", "-fdq"], cwd=repo_copy, capture_output=True)
        completed, timed_out = None, False
        try:
            subprocess.run(["bash", "-c", APPLY_SCRIPT], cwd=repo_copy, env={**os.environ, "WORK": workdir})
            completed = subprocess.run([self.python, os.path.join(workdir, "repro.py")], cwd=repo_copy,
                                       env={**os.environ, "PYTHONPATH": repo_copy},
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                       errors="replace", timeout=self.timeout)
            return collect(workdir, completed, False, repo_root=repo_copy)
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            return collect(workdir, subprocess.CompletedProcess(e.cmd, -1, stdout=stdout), True, repo_root=repo_copy)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
