"""The rule file merges the way both checkers expect.

check-docs holds a subset of the vocabulary check-web-content holds, plus
a few terms of its own. Three terms sit in a different category in each
checker, so neither may inherit the other's reading of them.
"""

from writing_lint import docs, web_content


def test_shared_terms_reach_both_checkers():
    web = {t for t, _ in web_content.WORD_RE}
    doc = {t for t, _ in docs.WORD_RE}
    assert "robust" in web and "robust" in doc
    assert len(web) == 185
    assert len(doc) == 121


def test_web_only_terms_stay_out_of_docs():
    web = {t for t, _ in web_content.WORD_RE}
    doc = {t for t, _ in docs.WORD_RE}
    assert "throughline" in web and "throughline" not in doc
    assert "footgun" in web and "footgun" not in doc


def test_category_differs_per_checker():
    """A term banned in one checker may be a context term in the other."""
    web_words = {t for t, _ in web_content.WORD_RE}
    web_context = {t for t, _ in web_content.CONTEXT_RE}
    doc_words = {t for t, _ in docs.WORD_RE}
    doc_context = {t for t, _ in docs.CONTEXT_RE}
    assert "notably" in web_words and "notably" in doc_context
    assert "basically" in web_context and "basically" in doc_words
    assert "fundamentally" in web_context and "fundamentally" in doc_words


def test_no_term_is_listed_twice():
    for compiled in (web_content.WORD_RE, web_content.PHRASE_RE,
                     docs.WORD_RE, docs.PHRASE_RE):
        terms = [t for t, _ in compiled]
        assert len(terms) == len(set(terms))


def test_boundaries_differ():
    """The web checker treats a hyphen as a boundary. The docs checker treats it as a word character."""
    assert web_content.BOUNDARY == "hyphen"
    assert docs.BOUNDARY == "word"


def test_counts_match_the_rule_file():
    assert len(web_content.PHRASE_RE) == 244
    assert len(docs.PHRASE_RE) == 96
    assert len(web_content.CONTEXT_RE) == 58
    assert len(docs.CONTEXT_RE) == 26
    assert len(web_content.CONSTRUCTS) == 23
    assert len(docs.CONSTRUCTS) == 2
