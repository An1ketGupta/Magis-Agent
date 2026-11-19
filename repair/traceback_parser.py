"""
Parse Python tracebacks from a test run into frames and the final exception.
"""
import os
import re
from dataclasses import dataclass, field

# SyntaxError frames have no ", in <func>" part
FRAME_RE = re.compile(r'^\s*File "(?P<path>[^"]+)", line (?P<line>\d+)(?:, in (?P<func>.+))?$')
EXCEPTION_RE = re.compile(r"^(?P<type>[A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning|Failure))(?::\s?(?P<message>.*))?$")
# paths of the repo inside the sandbox (SWE-bench images use /testbed)
REPO_ROOTS = ["/testbed/"]


@dataclass
class Frame:
    path: str # repo-relative if in the repo, else as printed
    line: int
    func: str
    in_repo: bool


@dataclass
class ParsedTraceback:
    frames: list = field(default_factory=list)
    exception_type: str = None
    exception_message: str = None

    @property
    def repo_frames(self):
        return [frame for frame in self.frames if frame.in_repo]

    @property
    def last_repo_frame(self):
        repo_frames = self.repo_frames
        return repo_frames[-1] if repo_frames else None

    def signature(self):
        # identifies "the same failure" across rounds
        frame = self.last_repo_frame
        location = f"{frame.path}:{frame.func}" if frame else None
        return f"{self.exception_type}@{location}"


def normalize_path(path, repo_roots, script_names):
    if os.path.basename(path) in script_names:
        return path, False
    if "site-packages" in path or "dist-packages" in path or path.startswith("<"):
        return path, False
    for root in repo_roots:
        root = root.rstrip("/") + "/"
        if path.startswith(root):
            return path[len(root):], True
    if not os.path.isabs(path):
        return path, True
    return path, False


def parse(output, repo_roots=None, script_names=("repro.py",)):
    """Return the last traceback in `output` (stdout + stderr), or None if there is none."""
    repo_roots = (repo_roots or []) + REPO_ROOTS
    lines = output.splitlines()
    starts = [idx for idx, line in enumerate(lines) if line.startswith("Traceback (most recent call last):")]
    if not starts:
        return None
    parsed = ParsedTraceback()
    for line in lines[starts[-1]+1:]:
        match = FRAME_RE.match(line)
        if match:
            path, in_repo = normalize_path(match.group("path"), repo_roots, script_names)
            parsed.frames.append(Frame(path, int(match.group("line")), (match.group("func") or "<module>").strip(), in_repo))
            continue
        match = EXCEPTION_RE.match(line.strip())
        if match and not line.startswith(" "):
            parsed.exception_type = match.group("type")
            parsed.exception_message = (match.group("message") or "").strip()
    return parsed
