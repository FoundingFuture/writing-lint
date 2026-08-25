import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


def run(module, name, **kwargs):
    """Check one fixture and return its findings."""
    findings = []
    if hasattr(module, "reset_known"):
        module.reset_known()
        contract = kwargs.get("contract")
        if contract:
            module.read_contract(fixture(contract))
    module.check_file(fixture(name), findings)
    return findings


def tally(findings):
    return dict(sorted(Counter(f.rule for f in findings).items()))


def levels(findings):
    errors = sum(1 for f in findings if f.level == "error")
    return errors, len(findings) - errors
