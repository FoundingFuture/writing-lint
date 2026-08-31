"""Exact finding counts for every web content fixture.

A rule change moves one of these numbers. That is the point: the number
is the record of what the rule did before the change.
"""

import pytest

from conftest import fixture, levels, run, tally
from writing_lint import web_content


def test_good_page_is_silent():
    assert run(web_content, "good-page.md") == []


def test_bad_theme_page():
    findings = run(web_content, "bad-theme-page.md")
    assert levels(findings) == (31, 8)
    assert tally(findings) == {
        "comparison": 2, "context": 2, "contraction": 1, "contrast": 1,
        "heading": 3, "hugo": 6, "lead-in": 1, "length": 1, "one-liner": 1,
        "phrase": 5, "reader": 2, "welcome": 1, "word": 13,
    }


def test_contract_makes_theme_names_known():
    without = run(web_content, "bad-theme-page.md")
    within = run(web_content, "bad-theme-page.md", contract="contract.toml")
    assert levels(within) == (31, 6)
    dropped = {f.message for f in without} - {f.message for f in within}
    assert len(dropped) == 2
    assert any("sources" in m for m in dropped)
    assert any("customField" in m for m in dropped)


def test_raw_html_page():
    findings = run(web_content, "raw-html.md")
    assert levels(findings) == (7, 0)
    assert tally(findings) == {"hugo": 7}
    assert sorted(f.line for f in findings) == [7, 11, 13, 15, 17, 19, 21]


def test_verge_page():
    findings = run(web_content, "verge-page.html")
    # 26 words is the limit and 18 the target, so one sentence that used to
    # fail now warns instead. The counts move with it.
    assert levels(findings) == (34, 6)
    assert tally(findings) == {
        "announced-count": 1, "bold": 1, "context": 1, "contrast": 3,
        "heading": 4, "length": 2, "phrase": 10, "question-reveal": 1,
        "reader": 1, "staccato": 1, "word": 15,
    }


def test_html_navigation_is_not_prose():
    """nav, header and footer carry chrome, not content."""
    findings = run(web_content, "verge-page.html")
    assert not [f for f in findings if f.line in (5, 6)]
    assert not [f for f in findings if "seamless things" in f.message]


def test_finding_format():
    finding = run(web_content, "raw-html.md")[0]
    assert finding.format().startswith(fixture("raw-html.md") + ":7: error: [hugo] ")
    assert set(finding.as_dict()) == {"file", "line", "level", "rule", "message"}


@pytest.mark.parametrize("name,code", [
    ("good-page.md", 0),
    ("raw-html.md", 1),
])
def test_exit_codes(name, code, capsys):
    assert web_content.main([fixture(name)]) == code
    capsys.readouterr()


def test_strict_promotes_warnings(capsys):
    assert web_content.main([fixture("good-page.md"), "--strict"]) == 0
    assert web_content.main([fixture("bad-theme-page.md"), "--strict"]) == 1
    capsys.readouterr()
