"""
stataudit: Automated statistical reporting audit tool for scientific manuscripts.

Scans plain-text manuscripts for common statistical reporting errors and
incomplete disclosures following APA and ML-reproducibility-checklist guidelines.

Quick-start
-----------
>>> from stataudit import audit_text
>>> findings = audit_text("Results were significant (t = 3.2, p = .002).")
>>> for f in findings:
...     print(f.severity.value, f.rule)
"""

__version__ = "0.2.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from .report import AuditReport, Finding, Severity
from .auditor import StatAuditor, audit_file, audit_text
from .rules import RULES

__all__ = [
    "Severity",
    "Finding",
    "AuditReport",
    "StatAuditor",
    "audit_text",
    "audit_file",
    "RULES",
]
