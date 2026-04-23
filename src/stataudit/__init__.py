"""
stataudit: Automated statistical reporting audit tool for ML papers.

Parses PDF or LaTeX source of machine learning papers and audits reported
statistical claims: checks for missing confidence intervals, verifies that
reported metrics are consistent across tables and text, flags absent baseline
comparisons, and detects common statistical reporting errors following the
ML reproducibility checklist.
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

from .auditor import StatAuditor
from .report import AuditReport

__all__ = ["StatAuditor", "AuditReport"]
