"""
stataudit: Automated statistical reporting audit tool for academic manuscripts.

Scans plain-text (and LaTeX / Markdown) manuscripts for common statistical
reporting errors: missing confidence intervals, absent effect sizes and degrees
of freedom, over-precise p-values, underpowered samples, and more.

Quick start::

    from stataudit import audit_text, AuditReport

    findings = audit_text("The result was significant (t = 3.2, ns).")
    report = AuditReport(source="example", findings=findings)
    print(report.to_markdown())

CLI::

    stataudit manuscript.txt --format markdown -o report.md
    stataudit --list-rules

GUI::

    stataudit-gui
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from .core import (  # noqa: F401
    AuditReport,
    Finding,
    Severity,
    _RULES,
    audit_file,
    audit_text,
)
from .cli import main  # noqa: F401

__all__ = [
    "Severity",
    "Finding",
    "AuditReport",
    "audit_text",
    "audit_file",
    "main",
    "__version__",
]
