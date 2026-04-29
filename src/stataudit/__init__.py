"""
stataudit: Automated statistical reporting audit tool for scientific manuscripts.

Detects common statistical reporting errors and omissions including missing
confidence intervals, absent degrees of freedom, unreported effect sizes,
suspicious p-values, and ML-reproducibility issues.
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from .report import AuditReport, Finding, Severity
from .auditor import StatAuditor, audit_file, audit_text

__all__ = [
    "Severity",
    "Finding",
    "AuditReport",
    "StatAuditor",
    "audit_text",
    "audit_file",
]
