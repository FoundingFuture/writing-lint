"""The package holds its own source to its own rules.

The fixtures are excluded. They carry the faults on purpose.
"""

import os

from conftest import ROOT
from writing_lint import docs


def sources():
    """Every file the package owns, minus the fixtures."""
    paths = [os.path.join(ROOT, name)
             for name in ("README.md", "CHANGELOG.md")]
    for folder in ("writing_lint", "tests"):
        for root, dirs, files in os.walk(os.path.join(ROOT, folder)):
            dirs[:] = [d for d in dirs if d not in ("fixtures", "__pycache__")]
            paths.extend(os.path.join(root, f) for f in sorted(files)
                         if f.endswith((".py", ".md", ".toml")))
    return sorted(paths)


def test_package_passes_check_docs():
    findings = []
    for path in sources():
        docs.check_file(path, findings)
    assert [f.format() for f in findings] == []
