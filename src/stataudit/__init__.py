"""
stataudit: Automated statistical reporting audit tool for scientific manuscripts.

Audits reported statistical claims — p-values, confidence intervals, effect sizes,
degrees of freedom, and sample sizes — for common reporting errors and omissions.
"""

__version__ = "0.1.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

# The installed package is the single-file module stataudit.py at the repo root.
# Re-export the public API from there so both `import stataudit` and
# `from stataudit import ...` work identically.
from stataudit import (  # noqa: F401  (re-exports)
    AuditReport,
    Finding,
    Severity,
    StatAuditor,
    audit_file,
    audit_text,
)

__all__ = [
    "AuditReport",
    "Finding",
    "Severity",
    "StatAuditor",
    "audit_file",
    "audit_text",
]
