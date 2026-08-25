"""Exact finding counts for every docs fixture."""

import pytest

from conftest import fixture, levels, run, tally
from writing_lint import docs


def test_good_source_is_silent():
    assert run(docs, "good-source.py") == []


def test_good_page_is_silent():
    """The web fixture is plain markdown, so the docs checker agrees too."""
    assert run(docs, "good-page.md") == []


def test_commented_source():
    findings = run(docs, "commented-source.py")
    assert levels(findings) == (21, 4)
    assert tally(findings) == {
        "banner": 2, "char": 1, "context": 3, "dead-code": 2, "length": 1,
        "opener": 2, "phrase": 5, "todo": 1, "word": 8,
    }


def test_commented_source_finds_dead_code_not_prose():
    findings = run(docs, "commented-source.py")
    dead = sorted(f.line for f in findings if f.rule == "dead-code")
    assert dead == [20, 21]


def test_bad_docs_markdown():
    findings = run(docs, "bad-docs.md")
    assert levels(findings) == (21, 2)
    assert tally(findings) == {
        "char": 2, "context": 2, "fence": 1, "heading": 3, "length": 1,
        "opener": 1, "phrase": 6, "word": 7,
    }


def test_shebang_is_not_prose():
    findings = run(docs, "commented-source.py")
    assert not [f for f in findings if f.line == 1]


@pytest.mark.parametrize("name,code", [
    ("good-source.py", 0),
    ("bad-docs.md", 1),
])
def test_exit_codes(name, code, capsys):
    assert docs.main([fixture(name)]) == code
    capsys.readouterr()
