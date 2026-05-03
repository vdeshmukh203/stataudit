"""stataudit: Automated statistical reporting audit tool for academic manuscripts.

Parses plain-text manuscripts and audits reported statistical claims:
missing confidence intervals, unreported degrees of freedom, over-precise
p-values, absent effect sizes, and other common reporting errors.

Quick start
-----------
>>> from stataudit import StatAuditor
>>> report = StatAuditor("The result was significant (p < 0.05).").run()
>>> len(report.findings) > 0
True
"""

__version__ = "0.2.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from ._core import Finding, Severity, audit_file, audit_text
from .auditor import StatAuditor
from .report import AuditReport

__all__ = [
    "Finding",
    "Severity",
    "StatAuditor",
    "AuditReport",
    "audit_text",
    "audit_file",
]
