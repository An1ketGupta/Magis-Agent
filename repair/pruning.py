"""
Block-level skeleton pruning of a Python file (Config C2; expand-on-failure for Config D).

A file is shown with its real line numbers. Every function and method body is folded to one marker line,
keeping the signature and docstring; module-level code and class-level statements stay visible. The blocks
most relevant to the issue are then unfolded, in score order, while the view fits in a token budget. Files
that fit in the budget are shown whole. Line numbers are those of the real file, so MAGIS's line-range
edits still point at the right lines.

Blocks come from Python's `ast` (exact line ranges, no extra dependency; all SWE-bench repos are Python).
A file that does not parse is shown whole. Block scores come from a scorer function (BM25 against the
issue by default), so a learned scorer such as SWE-Pruner can be plugged in later.
"""
import ast
import re
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi


@dataclass
class Block:
    name: str # qualified name, e.g. "Model.save"
    start: int # first line, decorators included (1-based)
    end: int # last line
    fold_start: int # first folded line (after the signature and docstring)

    @property
    def foldable(self):
        return self.fold_start <= self.end


def docstring_node(body):
    first = body[0] if body else None
    if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
            and isinstance(first.value.value, str):
        return first
    return None


def summary_line(node, lines):
    """Last line to keep of a docstring: the first line with text (its summary)."""
    for line_number in range(node.lineno, node.end_lineno + 1):
        if lines[line_number-1].strip().lstrip("rRuUbB").strip("\"'").strip():
            return line_number
    return node.lineno


def extract_blocks(source):
    """
    Foldable blocks of a file, in line order: function and method bodies (nested functions belong to their
    enclosing block), and the rest of long module/class docstrings after their summary line.
    """
    tree = ast.parse(source)
    lines = source.splitlines()
    blocks = []

    def add_docstring(body, name):
        node = docstring_node(body)
        if node is not None and node.end_lineno > node.lineno:
            keep = summary_line(node, lines)
            blocks.append(Block(name, node.lineno, node.end_lineno, keep + 1))

    def visit(body, prefix):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = min([node.lineno] + [decorator.lineno for decorator in node.decorator_list])
                first = node.body[0]
                docstring = docstring_node(node.body)
                if docstring is not None:
                    # keep the signature and the docstring's summary line, fold the rest
                    fold_start = summary_line(docstring, lines) + 1
                elif first.lineno > node.lineno:
                    fold_start = first.lineno
                else: # one-line function, nothing to fold
                    fold_start = node.end_lineno + 1
                blocks.append(Block(prefix + node.name, start, node.end_lineno, fold_start))
            elif isinstance(node, ast.ClassDef):
                add_docstring(node.body, prefix + node.name + ".__doc__")
                visit(node.body, prefix + node.name + ".")

    add_docstring(tree.body, "__doc__")
    visit(tree.body, "")
    return sorted(blocks, key=lambda block: block.start)


def tokenize(text):
    # same as exp/SWE-bench/bm25_retrieval.py: words, plus identifiers split into their parts
    tokens = []
    for word in re.findall(r"[A-Za-z0-9_]+", text):
        tokens.append(word.lower())
        parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+", word)
        if len(parts) > 1:
            tokens.extend(part.lower() for part in parts)
    return tokens


def bm25_scores(blocks, lines, query):
    """Score each block's code (name + lines) against the query (the issue text)."""
    if not blocks:
        return []
    documents = [tokenize(block.name + "\n" + "\n".join(lines[block.start-1:block.end])) or ["<empty>"]
                 for block in blocks]
    return list(BM25Okapi(documents).get_scores(tokenize(query)))


def named_first_scores(blocks, lines, query):
    """BM25, but blocks whose function name appears in the issue (e.g. in a traceback) come first."""
    scores = bm25_scores(blocks, lines, query)
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query))
    top = max(scores, default=0) + 1
    for idx, block in enumerate(blocks):
        name = block.name.split(".")[-1]
        if name != "__doc__" and name in words and len(name) >= 4:
            scores[idx] += top
    return scores


@dataclass
class PrunedView:
    lines: list
    blocks: list
    expanded: set = field(default_factory=set) # indices into blocks shown in full
    whole: bool = False # True: the file is shown without folding

    def folded_ranges(self):
        if self.whole:
            return []
        ranges = []
        for idx, block in enumerate(self.blocks):
            if idx in self.expanded or not block.foldable:
                continue
            # a block inside a folded range (e.g. a method of a nested class) is already hidden
            if ranges and ranges[-1][0] <= block.fold_start <= ranges[-1][1]:
                continue
            ranges.append((block.fold_start, block.end))
        return sorted(ranges)

    def visible(self, line_number):
        return not any(start <= line_number <= end for start, end in self.folded_ranges())

    def render(self):
        # same line format as operate.get_file_content(add_number=True): "<n> | <code>"
        output = []
        ranges = iter(self.folded_ranges())
        current = next(ranges, None)
        line_number = 1
        while line_number <= len(self.lines):
            if current and line_number == current[0]:
                start, end = current
                indent = re.match(r"\s*", self.lines[start-1]).group(0)
                output.append(f"{start}-{end} | {indent}... (lines {start}-{end} folded)")
                line_number = end + 1
                current = next(ranges, None)
                continue
            output.append(f"{line_number} | {self.lines[line_number-1]}")
            line_number += 1
        return "\n".join(output)

    def expand_lines(self, line_numbers):
        """Unfold the blocks containing these lines (expand-on-failure). Returns the newly unfolded names."""
        names = []
        for idx, block in enumerate(self.blocks):
            if idx not in self.expanded and any(block.start <= n <= block.end for n in line_numbers):
                self.expanded.add(idx)
                names.append(block.name)
        return names


def prune(source, query, budget_tokens, count_tokens, scorer=named_first_scores):
    """Fold the file to fit `budget_tokens` (as counted by `count_tokens` on the rendered view)."""
    lines = source.splitlines()
    whole = PrunedView(lines, [], whole=True)
    if count_tokens(whole.render()) <= budget_tokens:
        return whole
    try:
        blocks = extract_blocks(source)
    except (SyntaxError, ValueError):
        return whole
    view = PrunedView(lines, blocks)
    used = count_tokens(view.render())
    scores = scorer(blocks, lines, query)
    # unfold the best blocks while they fit; the cost of a block is its hidden lines minus the marker line
    for idx in sorted(range(len(blocks)), key=lambda i: -scores[i]):
        block = blocks[idx]
        if not block.foldable or scores[idx] <= 0:
            continue
        hidden = "\n".join(f"{n} | {lines[n-1]}" for n in range(block.fold_start, block.end + 1))
        cost = count_tokens(hidden) - count_tokens(f"{block.fold_start}-{block.end} | ... (lines {block.fold_start}-{block.end} folded)")
        if used + cost <= budget_tokens:
            view.expanded.add(idx)
            used += cost
    # nested blocks make the estimate inexact: fold the lowest-scored blocks again until the view fits
    for idx in sorted(view.expanded, key=lambda i: scores[i]):
        if count_tokens(view.render()) <= budget_tokens:
            break
        view.expanded.discard(idx)
    return view
