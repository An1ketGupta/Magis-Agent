"""
Unit tests for block skeleton pruning (repair/pruning.py). Run from the repo root:
    python -m pytest tests
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repair import pruning

SOURCE = '''import os

LIMIT = 10


def parse_date(text):
    """Parse a date string."""
    parts = text.split("-")
    year = int(parts[0])
    return year


@cached
def render_table(rows):
    out = []
    for row in rows:
        out.append(str(row))
    return "\\n".join(out)


class Storage:
    """Keeps files."""
    root = "/tmp"

    def save(self, name, data):
        path = os.path.join(self.root, name)
        with open(path, "w") as f:
            f.write(data)
        return path

    def size(self): return 0
'''


def count_tokens(text):
    return len(text.split())


def test_extract_blocks():
    blocks = {block.name: block for block in pruning.extract_blocks(SOURCE)}
    assert list(blocks) == ["parse_date", "render_table", "Storage.save", "Storage.size"]
    assert (blocks["parse_date"].start, blocks["parse_date"].fold_start, blocks["parse_date"].end) == (6, 8, 10)
    assert blocks["render_table"].start == 13 # decorator included
    assert blocks["render_table"].fold_start == 15
    assert not blocks["Storage.size"].foldable # one-line method


def test_skeleton_keeps_signatures_and_real_line_numbers():
    view = pruning.PrunedView(SOURCE.splitlines(), pruning.extract_blocks(SOURCE))
    text = view.render()
    assert "6 | def parse_date(text):" in text
    assert '7 |     """Parse a date string."""' in text
    assert "8-10 |     ... (lines 8-10 folded)" in text
    assert "year = int" not in text
    assert "23 |     root = \"/tmp\"" in text # class-level statements stay
    assert "31 |     def size(self): return 0" in text
    assert not view.visible(9) and view.visible(6)


def test_file_that_fits_is_whole():
    view = pruning.prune(SOURCE, "anything", budget_tokens=10_000, count_tokens=count_tokens)
    assert view.whole and view.render().count("\n") == len(SOURCE.splitlines()) - 1


def test_prune_unfolds_the_relevant_block():
    skeleton_tokens = count_tokens(pruning.PrunedView(SOURCE.splitlines(), pruning.extract_blocks(SOURCE)).render())
    view = pruning.prune(SOURCE, "Storage save fails when the path does not exist",
                         budget_tokens=skeleton_tokens + 25, count_tokens=count_tokens)
    text = view.render()
    assert "path = os.path.join(self.root, name)" in text # Storage.save unfolded
    assert "year = int" not in text # parse_date still folded
    assert count_tokens(text) <= skeleton_tokens + 25


def test_expand_lines_on_failure():
    view = pruning.PrunedView(SOURCE.splitlines(), pruning.extract_blocks(SOURCE))
    assert view.expand_lines([9]) == ["parse_date"] # traceback frame at line 9
    assert "9 |     year = int(parts[0])" in view.render()
    assert view.expand_lines([9]) == []


LONG_DOCSTRINGS = '''"""
Tools for tables.

Long module documentation.
"""


class Table:
    """A table.

    More text about tables.
    """

    def width(self):
        """
        Return the width.

        Parameters: none.
        """
        return 3
'''


def test_long_docstrings_fold_after_summary_line():
    blocks = {block.name: block for block in pruning.extract_blocks(LONG_DOCSTRINGS)}
    assert (blocks["__doc__"].fold_start, blocks["__doc__"].end) == (3, 5)
    assert (blocks["Table.__doc__"].fold_start, blocks["Table.__doc__"].end) == (10, 12)
    assert blocks["Table.width"].fold_start == 17 # after "Return the width."
    text = pruning.PrunedView(LONG_DOCSTRINGS.splitlines(), list(blocks.values())).render()
    assert "2 | Tools for tables." in text and "Long module documentation" not in text
    assert "16 |         Return the width." in text and "return 3" not in text


def test_blocks_named_in_the_issue_come_first():
    lines = SOURCE.splitlines()
    blocks = pruning.extract_blocks(SOURCE)
    issue = "Traceback: in render_table ... the storage path is wrong"
    scores = pruning.named_first_scores(blocks, lines, issue)
    best = blocks[max(range(len(blocks)), key=lambda i: scores[i])]
    assert best.name == "render_table"


def test_unparsable_file_is_whole():
    source = "def broken(:\n" + "x = 1\n" * 200
    view = pruning.prune(source, "x", budget_tokens=50, count_tokens=count_tokens)
    assert view.whole
