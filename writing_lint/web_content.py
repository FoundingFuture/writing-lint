#!/usr/bin/env python3
"""Flag AI writing patterns and weak headings in web content.

Usage:
    check-web-content PATH [PATH]
    check-web-content --url https://example.com/page/
    check-web-content --strict content/
    check-web-content --contract ../theme/contract.toml content/

Reads .html, .htm, .md, .markdown, .mdx and .txt. Exit code 0 means no errors.
Add "web-content:ignore" to a line to skip that line.
Add "web-content:ignore-file" to the first 30 lines to skip the whole file.
"""

import os
import re
import statistics
import sys
from html.parser import HTMLParser

from . import common
from .common import EMOJI, Finding

RULES = common.load_rules("web_content")
BOUNDARY = RULES["boundary"]

BANNED_CHARS = common.char_table(RULES)
WORD_RE = common.compile_terms(RULES["words"], BOUNDARY)
PHRASE_RE = common.compile_terms(RULES["phrases"], BOUNDARY)
CONTEXT_RE = common.compile_terms(RULES["context"], BOUNDARY)
KEY_ADJECTIVE = common.key_adjective(RULES)
CONSTRUCTS = common.compile_constructs(RULES["constructs"])

LIMITS = RULES["limits"]
TITLE_CASE_MIN = LIMITS["title_case_min"]
MAX_SENTENCE_WORDS = LIMITS["max_sentence_words"]
MAX_HEADING_WORDS = LIMITS["max_heading_words"]
MAX_HEADING_DEPTH = LIMITS["max_heading_depth"]
MAX_PAREN_WORDS = LIMITS["max_paren_words"]
MAX_TITLE_CHARS = LIMITS["max_title_chars"]
MIN_DESCRIPTION_CHARS = LIMITS["min_description_chars"]
MAX_DESCRIPTION_CHARS = LIMITS["max_description_chars"]

FILLER_HEADINGS = re.compile(
    r"^(" + "|".join(
        re.escape(h).replace(r"\ ", r"\s+") for h in RULES["headings"]["filler"]
    ) + r")$", re.IGNORECASE)
HEADING_VERB = re.compile(
    r"\b(" + "|".join(re.escape(v) for v in RULES["headings"]["verbs"]) + r")\b",
    re.IGNORECASE)
WH_OPENER = re.compile(
    r"^(" + "|".join(RULES["headings"]["wh_openers"]) + r")\b", re.IGNORECASE)

MARKDOWN_EXT = {".md", ".markdown", ".mdx", ".txt"}
HTML_EXT = {".html", ".htm", ".xhtml"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
             ".next", "target", "vendor", "resources", "themes"}

class Block:
    """One heading, paragraph, or list item with its starting line number."""

    def __init__(self, kind, line, text, level=0):
        self.kind, self.line, self.text, self.level = kind, line, text, level


def words_of(text):
    return [w for w in re.findall(r"[A-Za-z][\w'-]*", text)]


def sentences_of(text):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", text.strip())
    return [p for p in parts if p]


class ContentParser(HTMLParser):
    SKIP = {"script", "style", "code", "pre", "nav", "header", "footer", "aside", "svg",
            "noscript", "template", "kbd", "samp", "textarea"}
    BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "dd", "dt",
              "figcaption", "td", "th", "summary"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.skip_depth = 0
        self.current = None
        self.buffer = []
        self.start_line = 0
        self.bold_runs = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in ("b", "strong", "em", "i") and self.current:
            self.bold_runs += 1
        if tag in self.BLOCKS:
            self.flush()
            self.current = tag
            self.start_line = self.getpos()[0]
        if tag == "br" and self.current:
            self.buffer.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag in self.BLOCKS and self.current == tag:
            self.flush()

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.current:
            self.buffer.append(data)

    def flush(self):
        if self.current:
            text = re.sub(r"\s+", " ", "".join(self.buffer)).strip()
            if text:
                kind = "heading" if self.current[0] == "h" and self.current[1:].isdigit() else self.current
                level = int(self.current[1]) if kind == "heading" else 0
                self.blocks.append(Block(kind, self.start_line, text, level))
        self.current, self.buffer = None, []


def parse_html(source):
    parser = ContentParser()
    parser.feed(source)
    parser.flush()
    return parser.blocks, parser.bold_runs


def parse_markdown(lines):
    blocks = []
    bold_runs = 0
    in_fence = in_front = False
    para, para_start = [], 0
    front = []

    def flush():
        nonlocal para
        if para:
            text = " ".join(l.strip() for l in para)
            blocks.append(Block("p", para_start, text))
        para = []

    for i, raw in enumerate(lines, start=1):
        s = raw.strip()
        if i == 1 and s in ("---", "+++"):
            in_front = True
            continue
        if in_front:
            if s in ("---", "+++"):
                in_front = False
                blocks.insert(0, Block("front", 1, "\n".join(front)))
            else:
                front.append(raw)
            continue
        # Fences first: nothing inside one is prose, HTML, or a shortcode.
        if re.match(r"^\s*(```|~~~)", raw):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if s == "<!--more-->" or s.startswith("<!--"):
            flush()
            continue
        if re.match(r"^\s*\{\{[<%]", raw):
            flush()
            blocks.append(Block("shortcode", i, s))
            continue
        if re.match(r"^\s*</?[a-zA-Z][^>]*>", raw):
            flush()
            blocks.append(Block("rawhtml", i, s))
            continue
        if not s:
            flush()
            continue
        if s in ("---", "***", "___"):
            flush()
            blocks.append(Block("hr", i, s))
            continue
        heading = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", raw)
        if heading:
            flush()
            blocks.append(Block("heading", i, heading.group(2), len(heading.group(1))))
            continue
        item = re.match(r"^\s*([-*+]|\d+[.)])\s+(.*)$", raw)
        if item:
            flush()
            blocks.append(Block("li", i, item.group(2)))
            continue
        if s.startswith("|") or s.startswith("<"):
            flush()
            continue
        if not para:
            para_start = i
        para.append(raw)
        bold_runs += len(re.findall(r"\*\*[^*]+\*\*|__[^_]+__", raw))
    flush()
    return blocks, bold_runs


def strip_code(text):
    """Remove markup that is not prose: images, link targets, shortcodes, code."""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)          # ![alt](src "title")
    text = re.sub(r"!\[[^\]]*\]\[[^\]]*\]", " ", text)          # ![alt][ref]
    text = re.sub(r"\[([^\]]*)\]\((?:[^()]|\([^)]*\))*\)", r"\1", text)  # [text](url) keeps text
    text = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", text)      # [text][ref] keeps text
    text = re.sub(r"\{\{[<%].*?[>%]\}\}", " ", text)
    return re.sub(r"`[^`]*`", " ", text)


def check_text(path, block, findings):
    text = strip_code(block.text)
    if "web-content:ignore" in text:
        return
    line = block.line
    for char, name, fix in BANNED_CHARS:
        if char in text:
            findings.append(Finding(path, line, "error", "char", f"{name}. Use {fix}."))
    if EMOJI.search(text):
        findings.append(Finding(path, line, "error", "char", "emoji. Remove it."))
    if re.search(r"\S\s--?\s\S|\w--\w", text):
        findings.append(Finding(path, line, "error", "char",
                                "hyphen used as a dash. Start a new sentence."))
    if "!" in re.sub(r"https?://\S+", "", text):
        findings.append(Finding(path, line, "error", "char", "exclamation mark. Use a period."))
    if ";" in text:
        findings.append(Finding(path, line, "error", "char", "semicolon. Use two sentences."))
    if "..." in text:
        findings.append(Finding(path, line, "error", "char", "ellipsis. Finish the sentence."))
    paren = re.findall(r"\(([^)]*)\)", text)
    for inner in paren:
        if len(inner.split()) > MAX_PAREN_WORDS:
            findings.append(Finding(path, line, "error", "paren",
                                    "parenthetical aside over five words. Make it a sentence."))

    for term, pattern in PHRASE_RE:
        if pattern.search(text):
            findings.append(Finding(path, line, "error", "phrase", f"banned phrase: {term}"))
    for term, pattern in WORD_RE:
        if pattern.search(text):
            findings.append(Finding(path, line, "error", "word", f"banned word: {term}"))
    for term, pattern in CONTEXT_RE:
        if pattern.search(text):
            findings.append(Finding(path, line, "warning", "context",
                                    f"filler risk: {term}. Keep only with a literal meaning."))
    if KEY_ADJECTIVE.search(text):
        findings.append(Finding(path, line, "error", "word", "banned word: key (as an adjective)"))

    for rule, level, find, message in CONSTRUCTS:
        if find(text):
            findings.append(Finding(path, line, level, rule, message))

    sents = sentences_of(text)
    for s in sents:
        n = len(words_of(s))
        if n > MAX_SENTENCE_WORDS:
            findings.append(Finding(path, line, "error", "length",
                                    f"sentence runs {n} words. Split at {MAX_SENTENCE_WORDS}."))
    short = [s for s in sents if len(words_of(s)) <= 4]
    run = 0
    for s in sents:
        run = run + 1 if len(words_of(s)) <= 4 else 0
        if run >= 3:
            findings.append(Finding(path, line, "error", "staccato",
                                    "three or more fragments in a row. Write one sentence."))
            break
    openers = [words_of(s)[0].lower() for s in sents if words_of(s)]
    for i in range(len(openers) - 2):
        if openers[i] == openers[i + 1] == openers[i + 2] and openers[i] not in ("the", "a", "an"):
            findings.append(Finding(path, line, "error", "anaphora",
                                    f"three sentences open with '{openers[i]}'. Vary or merge."))
            break
    if re.match(r"^\s*(I|We)\s+(think|believe|feel|suspect|would argue)\b", text):
        findings.append(Finding(path, line, "warning", "voice",
                                "opinion opener. State the fact, then the evidence."))


def check_heading(path, block, prev_heading_level, findings):
    title = re.sub(r"^\d+(\.\d+)*\.?\s+", "", strip_code(block.text).strip())
    line = block.line
    if block.level > MAX_HEADING_DEPTH:
        findings.append(Finding(path, line, "error", "heading",
                                f"h{block.level}. Maximum depth is h{MAX_HEADING_DEPTH}. Split the page."))
    if prev_heading_level and block.level > prev_heading_level + 1:
        findings.append(Finding(path, line, "error", "heading",
                                f"h{block.level} after h{prev_heading_level}. Do not skip levels."))
    if title.endswith((".", ":", "!", "?", ",")):
        findings.append(Finding(path, line, "error", "heading",
                                "heading ends with punctuation. Headings are labels."))
    if "?" in title:
        findings.append(Finding(path, line, "error", "heading",
                                "question heading. Use a noun phrase."))
    if re.search(r"[.!?]\s+\S", title):
        findings.append(Finding(path, line, "error", "heading",
                                "two sentences in a heading. Move the sentences into the body."))
    if ":" in title and not re.search(r"\d:\d", title):
        findings.append(Finding(path, line, "error", "heading",
                                "colon title. Use one noun phrase."))
    words = words_of(title)
    if len(words) > MAX_HEADING_WORDS:
        findings.append(Finding(path, line, "error", "heading",
                                f"heading runs {len(words)} words. Cut to {MAX_HEADING_WORDS} or fewer."))
    if len(words) >= 4 and HEADING_VERB.search(title):
        findings.append(Finding(path, line, "error", "heading",
                                "heading reads as a sentence. Write a noun phrase."))
    if re.match(r"^(how|why|what|when|where|whether|who)\b", title, re.IGNORECASE) and len(words) >= 4:
        findings.append(Finding(path, line, "error", "heading",
                                "wh-heading (why X, how X). Name the topic."))
    if re.match(r"^(a|an|the)\s", title, re.IGNORECASE):
        findings.append(Finding(path, line, "warning", "heading",
                                "heading starts with an article. Put the keyword first."))
    alpha = [w for w in words if w.isalpha()]
    capped = [w for w in alpha[1:] if w[:1].isupper() and not w.isupper()]
    if len(alpha) >= TITLE_CASE_MIN and len(capped) >= len(alpha) - 1:
        findings.append(Finding(path, line, "error", "heading",
                                "Title Case heading. Use sentence case."))
    if FILLER_HEADINGS.match(title):
        findings.append(Finding(path, line, "error", "heading", f"filler section: {title}"))


# An HTML tag in prose. Excludes comments and autolinks such as
# <https://x> and <me@x.y>. A tag name must be followed by a space, a
# slash or a closing bracket.
INLINE_HTML = re.compile(r"</?([a-zA-Z][a-zA-Z0-9-]*)(?:\s[^<>]*)?/?>")

FRONT_MATTER_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*[:=]")

# What a theme may name. A contract file adds to both lists. A page using
# a theme's own shortcode then reads as correct under that theme, and as a
# warning anywhere else.
KNOWN_SHORTCODES = set(RULES["hugo"]["builtin_shortcodes"])
KNOWN_FRONT_MATTER = set(RULES["hugo"]["front_matter_known"])


def reset_known():
    """Restore what is known to the built-in Hugo lists."""
    KNOWN_SHORTCODES.clear()
    KNOWN_SHORTCODES.update(RULES["hugo"]["builtin_shortcodes"])
    KNOWN_FRONT_MATTER.clear()
    KNOWN_FRONT_MATTER.update(RULES["hugo"]["front_matter_known"])


def read_contract(path, findings=None):
    """Add a theme's shortcodes and front matter keys to what is known."""
    try:
        with open(path, "rb") as handle:
            data = common.tomllib.load(handle)
    except (OSError, ValueError) as exc:
        if findings is not None:
            findings.append(Finding(path, 0, "error", "contract", str(exc)))
        return
    KNOWN_SHORTCODES.update(data.get("shortcodes", []))
    for key in ("front_matter", "params"):
        KNOWN_FRONT_MATTER.update(data.get(key, []))


def check_hugo(path, blocks, findings):
    front = next((b for b in blocks if b.kind == "front"), None)
    is_markdown = any(b.kind in ("front", "shortcode") for b in blocks) or \
        path.endswith((".md", ".markdown"))
    if not is_markdown:
        return
    if front is None:
        findings.append(Finding(path, 1, "error", "hugo", "no front matter."))
    else:
        text = front.text
        def field(name):
            m = re.search(r"^\s*" + name + r"\s*[:=]\s*(.*)$", text, re.MULTILINE)
            return m.group(1).strip().strip("\"'") if m else None
        for name in RULES["hugo"]["front_matter_required"]:
            if field(name) is None:
                findings.append(Finding(path, 1, "error", "hugo", f"front matter lacks {name}."))
        title = field("title")
        if title:
            if len(title) > MAX_TITLE_CHARS:
                findings.append(Finding(path, 1, "error", "hugo",
                                        f"title is {len(title)} characters. Keep under {MAX_TITLE_CHARS}."))
            if re.search(r"[.!?]\s|[.!?]$", title):
                findings.append(Finding(path, 1, "error", "hugo", "title is a sentence. Noun phrase."))
        desc = field("description")
        if desc is not None and not (MIN_DESCRIPTION_CHARS <= len(desc) <= MAX_DESCRIPTION_CHARS):
            findings.append(Finding(path, 1, "error", "hugo",
                                    f"description is {len(desc)} characters. "
                                    f"Keep {MIN_DESCRIPTION_CHARS} to {MAX_DESCRIPTION_CHARS}."))
        for raw in text.splitlines():
            m = FRONT_MATTER_KEY.match(raw)
            if m and m.group(1) not in KNOWN_FRONT_MATTER:
                findings.append(Finding(path, 1, "warning", "hugo",
                                        f"front matter key {m.group(1)} is not a Hugo key. "
                                        f"Put a custom key under params."))
    for b in blocks:
        if b.kind == "heading" and b.level == 1:
            findings.append(Finding(path, b.line, "error", "hugo",
                                    "h1 in body. The title front matter is the h1. Use ##."))
        if b.kind == "rawhtml":
            findings.append(Finding(path, b.line, "error", "hugo",
                                    "raw HTML. Goldmark drops it. Use Markdown or a shortcode."))
        if b.kind == "shortcode":
            m = re.match(r"\{\{[<%]\s*/?\s*([\w-]+)", b.text)
            if m and m.group(1) not in KNOWN_SHORTCODES:
                findings.append(Finding(path, b.line, "warning", "hugo",
                                        f"theme shortcode {m.group(1)}. Build fails under another theme. Prefer a built-in."))
        if b.kind in ("p", "li", "heading"):
            prose = strip_code(b.text)
            tag = INLINE_HTML.search(prose)
            if tag:
                findings.append(Finding(path, b.line, "error", "hugo",
                                        f"inline HTML <{tag.group(1)}>. Goldmark drops it. Use Markdown."))
        if b.kind in ("p", "li"):
            if re.search(r"\]\((?!https?://|/|#|\{\{)[^)]*\.md[)#]", b.text):
                findings.append(Finding(path, b.line, "error", "hugo",
                                        "relative .md link. Use relref or an absolute site path."))
            if re.search(r"\]\(\{\{[<%]\s*rel?ref\s+\"[^\"]*_?index(\.md)?\"", b.text):
                findings.append(Finding(path, b.line, "error", "hugo",
                                        "relref to index.md. Reference the directory."))
            if re.search(r"!\[\s*\]\(|!\[(image|screenshot|photo|picture)\]\(", b.text, re.IGNORECASE):
                findings.append(Finding(path, b.line, "error", "hugo",
                                        "image without descriptive alt text."))
            if re.search(r"(^|[^\\$])\$[^$\s][^$]*\$", b.text):
                findings.append(Finding(path, b.line, "warning", "hugo",
                                        "inline math. Needs passthrough in site config."))
            if re.search(r"\}\s*\{[.#][\w-]+", b.text) or re.search(r"^\{[.#][\w-]+", b.text):
                findings.append(Finding(path, b.line, "warning", "hugo",
                                        "block attribute. Needs parser.attribute.block."))


def check_document(path, blocks, bold_runs, findings):
    check_hugo(path, blocks, findings)
    blocks = [b for b in blocks if b.kind not in ("front", "shortcode", "rawhtml")]
    h1s = [b for b in blocks if b.kind == "heading" and b.level == 1]
    if len(h1s) > 1:
        findings.append(Finding(path, h1s[1].line, "error", "heading",
                                f"{len(h1s)} h1 headings. One per page."))
    prev_level = 0
    prev_heading = None
    para_lengths = []
    paragraphs = [b for b in blocks if b.kind == "p"]
    first_para_seen = False
    for idx, block in enumerate(blocks):
        if block.kind == "hr":
            findings.append(Finding(path, block.line, "error", "rule",
                                    "horizontal rule. Headings separate sections."))
            continue
        if block.kind == "heading":
            check_heading(path, block, prev_level, findings)
            check_text(path, block, findings)
            prev_level = block.level
            prev_heading = block
            continue
        check_text(path, block, findings)
        if block.kind == "li":
            if re.match(r"^\s*(\*\*|__)?[A-Z][\w\s/-]{0,30}(\*\*|__)?\s*[:.]\s+\S", block.text) and \
                    re.search(r"\*\*|__", block.text):
                findings.append(Finding(path, block.line, "error", "bullet",
                                        "bold-stem bullet (Term: restatement). Write the fact."))
            continue
        if block.kind != "p":
            continue
        n = len(words_of(block.text))
        para_lengths.append(n)
        sents = sentences_of(block.text)
        if prev_heading is not None and blocks[idx - 1] is prev_heading:
            hw = {w.lower() for w in words_of(prev_heading.text) if len(w) > 3}
            fw = {w.lower() for w in words_of(sents[0]) if len(w) > 3} if sents else set()
            if hw and len(hw & fw) >= max(2, len(hw) - 1):
                findings.append(Finding(path, block.line, "error", "restate",
                                        "first sentence repeats the heading. Start with new information."))
            if re.match(r"^(in this|this section|below|here we|here,? we|let)", sents[0] if sents else "", re.IGNORECASE):
                findings.append(Finding(path, block.line, "error", "lead-in",
                                        "lead-in paragraph announcing the section. Start with content."))
        if len(sents) == 1 and n <= 8 and strip_code(block.text).strip():
            findings.append(Finding(path, block.line, "warning", "one-liner",
                                    "one-line paragraph. Keep only if it carries a fact."))
        if not first_para_seen:
            first_para_seen = True
            if re.match(r"^(welcome|hello|hi\b|thank you|thanks for|in this)", block.text, re.IGNORECASE):
                findings.append(Finding(path, block.line, "error", "welcome",
                                        "welcome text. Start with the fact the reader came for."))
    if paragraphs:
        last = paragraphs[-1]
        last_sents = sentences_of(last.text)
        if last_sents and len(words_of(last_sents[-1])) <= 7 and len(last_sents) > 1:
            findings.append(Finding(path, last.line, "warning", "closer",
                                    "page ends on a short line. Check it is a fact, not a kicker."))
    if len(para_lengths) >= 5:
        mean = statistics.mean(para_lengths)
        sd = statistics.pstdev(para_lengths)
        if mean and sd / mean < 0.2:
            findings.append(Finding(path, paragraphs[0].line, "warning", "uniform",
                                    f"paragraphs are all about {int(mean)} words. Vary the length."))
    total_words = sum(para_lengths)
    if total_words and bold_runs > max(3, total_words // 150):
        findings.append(Finding(path, paragraphs[0].line if paragraphs else 1, "warning", "bold",
                                f"{bold_runs} bold or italic runs. Keep at most one per screen."))



def check_source(path, source, ext, findings):
    lines = source.splitlines()
    if any("web-content:ignore-file" in l for l in lines[:30]):
        return
    if ext in HTML_EXT or source.lstrip().lower().startswith(("<!doctype", "<html")):
        blocks, bold = parse_html(source)
    else:
        blocks, bold = parse_markdown(lines)
    check_document(path, blocks, bold, findings)


def check_file(path, findings):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            source = handle.read()
    except OSError as exc:
        findings.append(Finding(path, 0, "error", "io", str(exc)))
        return
    check_source(path, source, os.path.splitext(path)[1].lower(), findings)


def check_url(url, findings):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "writing-lint/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        source = resp.read().decode("utf-8", errors="replace")
    check_source(url, source, ".html", findings)


def main(argv=None):
    parser = common.parser_for("Flag AI writing patterns in web content.")
    parser.add_argument("targets", nargs="*", help="files or directories")
    parser.add_argument("--url", action="append", default=[], help="fetch and check a page")
    parser.add_argument("--contract", help="a theme's contract.toml, naming what it defines")
    args = parser.parse_args(argv)
    if not args.targets and not args.url:
        parser.error("give at least one file, directory, or --url")

    findings = []
    reset_known()
    if args.contract:
        read_contract(args.contract, findings)
    for path in common.collect(args.targets, MARKDOWN_EXT | HTML_EXT, SKIP_DIRS):
        check_file(path, findings)
    for url in args.url:
        try:
            check_url(url, findings)
        except Exception as exc:  # noqa: BLE001
            findings.append(Finding(url, 0, "error", "io", str(exc)))
    findings.sort(key=lambda f: (f.path, f.line, f.rule))
    return common.report(findings, args)


if __name__ == "__main__":
    sys.exit(main())
