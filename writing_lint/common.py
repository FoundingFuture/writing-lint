"""Rule loading, findings, and the output contract both checkers share."""

import argparse
import json
import os
import re
import sys

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and older
    import tomli as tomllib

RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.toml")

# A term is bounded by word characters alone, or by word characters and
# hyphens. The web checker uses the second form, so "key" stays unmatched
# inside "load-bearing". The docs checker uses the first, because it reads
# identifiers where a hyphen is a separator.
BOUNDARIES = {
    "word": (r"(?<!\w)", r"(?!\w)"),
    "hyphen": (r"(?<![\w-])", r"(?![\w-])"),
}

_CACHE = {}


def load_rules(section):
    """Return the rules for one checker, with [shared] merged underneath."""
    if section not in _CACHE:
        with open(RULES_PATH, "rb") as handle:
            data = tomllib.load(handle)
        _CACHE[section] = _merge(data.get("shared", {}), data.get(section, {}))
    return _CACHE[section]


def _merge(shared, overlay):
    """Overlay one checker's table onto the shared one.

    A list is extended and de-duplicated, keeping first order. A table is
    merged one level down. Anything else replaces the shared value.
    """
    out = dict(shared)
    for key, value in overlay.items():
        base = out.get(key)
        if isinstance(base, list) and isinstance(value, list):
            out[key] = _dedupe(base + value)
        elif isinstance(base, dict) and isinstance(value, dict):
            out[key] = _merge(base, value)
        else:
            out[key] = value
    return out


def _dedupe(seq):
    """Drop repeats, keeping first order. A table row is kept as it is."""
    seen, out = set(), []
    for item in seq:
        if isinstance(item, dict):
            out.append(item)
        elif item not in seen:
            seen.add(item)
            out.append(item)
    return out


def compile_terms(terms, boundary="word"):
    """Compile each term to a bounded, case-insensitive pattern.

    Spaces match any run of whitespace, so a term still matches where a
    line wrapped. A straight apostrophe also matches the curly form.
    """
    before, after = BOUNDARIES[boundary]
    out = []
    for term in _dedupe(terms):
        body = re.escape(term).replace(r"\ ", r"\s+").replace("'", "['’]")
        out.append((term, re.compile(before + body + after, re.IGNORECASE)))
    return out


def compile_constructs(rows):
    """Compile the construct table into (rule, level, matcher, message)."""
    out = []
    for row in rows:
        flags = re.IGNORECASE if row.get("ignorecase", True) else 0
        pattern = re.compile(row["pattern"], flags)
        anchored = row.get("method", "search") == "match"
        find = pattern.match if anchored else pattern.search
        out.append((row["rule"], row.get("level", "error"), find, row["message"]))
    return out


def key_adjective(rules):
    """Match "key" only where it is an adjective, never as a map key."""
    nouns = "|".join(rules["key_adjective"]["nouns"])
    return re.compile(r"\b(key\s+(" + nouns + r")|is\s+key\b|are\s+key\b)", re.IGNORECASE)


def char_table(rules):
    """Return the banned characters as (char, name, fix), in file order."""
    return [(char, row["name"], row["fix"]) for char, row in rules["chars"].items()]


EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff️⬀-⯿]"
)


class Finding:
    """One reported problem, at one line of one file."""

    def __init__(self, path, line, level, rule, message):
        self.path = path
        self.line = line
        self.level = level
        self.rule = rule
        self.message = message

    def format(self):
        return f"{self.path}:{self.line}: {self.level}: [{self.rule}] {self.message}"

    def as_dict(self):
        return {"file": self.path, "line": self.line, "level": self.level,
                "rule": self.rule, "message": self.message}


def collect(targets, extensions, skip_dirs):
    """Walk the targets and return every file the checker reads."""
    paths = []
    for target in targets:
        if os.path.isfile(target):
            paths.append(target)
            continue
        for root, dirs, files in os.walk(target):
            dirs[:] = [x for x in dirs if x not in skip_dirs and not x.startswith(".")]
            for name in sorted(files):
                if os.path.splitext(name)[1].lower() in extensions:
                    paths.append(os.path.join(root, name))
    return paths


def add_common_args(parser):
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--quiet", action="store_true", help="print only the count")
    return parser


def report(findings, args):
    """Print the findings and return the exit code."""
    errors = sum(1 for f in findings if f.level == "error")
    warnings = len(findings) - errors
    if args.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    elif not args.quiet:
        for finding in findings:
            print(finding.format())
    print(f"{errors} error(s), {warnings} warning(s)", file=sys.stderr)
    return 1 if errors or (args.strict and warnings) else 0


def parser_for(description):
    return add_common_args(argparse.ArgumentParser(description=description))
