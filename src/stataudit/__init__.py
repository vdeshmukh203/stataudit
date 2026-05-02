"""
stataudit: Automated statistical reporting audit tool for ML papers.

Parses plain-text or PDF manuscripts and audits reported statistical claims:
checks for missing confidence intervals, flags incomplete significance-test
reporting, and detects common statistical errors following ML reproducibility
best-practice guidelines.

This package re-exports the public API from the root ``stataudit`` module.
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

import sys as _sys
import pathlib as _pathlib

# Allow the root-level stataudit.py to be found regardless of working directory
_root = str(_pathlib.Path(__file__).resolve().parent.parent.parent)
if _root not in _sys.path:
    _sys.path.insert(0, _root)

from stataudit import (  # noqa: E402
    AuditReport,
    Finding,
    Severity,
    audit_text,
    audit_file,
    __version__ as _v,
)

__all__ = ["AuditReport", "Finding", "Severity", "audit_text", "audit_file"]
