"""
stataudit: Automated statistical reporting auditor for academic manuscripts.

Parses plain-text manuscripts and audits reported statistical claims:
checks p-values, confidence intervals, effect sizes, degrees of freedom,
sample sizes, regression R², and other reporting standards drawn from
APA guidelines and the ML reproducibility checklist.

Quick start
-----------
>>> from stataudit import StatAuditor
>>> report = StatAuditor("The result was ns, t = 3.2, p = .001.").run()
>>> for f in report.findings:
...     print(f.severity, f.rule, f.location)
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from .auditor import StatAuditor
from .core import audit_file, audit_text
from .models import Finding, Severity
from .report import AuditReport
from .rules import _RULES

__all__ = [
    "Severity",
    "Finding",
    "StatAuditor",
    "AuditReport",
    "audit_text",
    "audit_file",
    "_RULES",
    "__version__",
    "__author__",
    "__license__",
]
