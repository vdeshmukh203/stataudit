"""
stataudit — automated statistical reporting audit tool for academic manuscripts.

Scans plain-text manuscripts for common statistical reporting errors: missing
confidence intervals, absent degrees of freedom, unreported variance, small
sample sizes, and more.  Outputs findings as plain text, Markdown, JSON, or
HTML.

Basic usage::

    from stataudit import StatAuditor, AuditReport

    auditor = StatAuditor("manuscript.txt")
    report: AuditReport = auditor.run()

    for finding in report.findings:
        print(finding.severity, finding.rule, finding.location)

    report.save_html("audit_report.html")

Or, using the lower-level API directly::

    from stataudit import audit_text, Severity

    findings = audit_text(text, min_severity=Severity.WARNING)
"""

__version__ = "0.2.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from .auditor import StatAuditor, audit_file, audit_text
from .report import AuditReport, Finding, Severity

__all__ = [
    "StatAuditor",
    "AuditReport",
    "Finding",
    "Severity",
    "audit_text",
    "audit_file",
]
