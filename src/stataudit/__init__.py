"""
stataudit: Automated statistical reporting audit tool for academic manuscripts.

Parses plain text (and optionally LaTeX/PDF sources) of research papers and
audits reported statistical claims: checks for missing confidence intervals,
flags absent effect sizes, detects inconsistent reporting conventions, and
surfaces common statistical errors following best-practice guidelines for
empirical research.

The canonical implementation lives in ``stataudit.py`` at the project root.
This package shim re-exports the full public API so that both
``import stataudit`` and ``from stataudit import ...`` work correctly whether
the module is used from an installed wheel or from the source tree.
"""

from __future__ import annotations

__version__ = "0.2.0"
__author__ = "Vaibhav Deshmukh"
__license__ = "MIT"

# Re-export the public API from the canonical top-level module.
# The try/except guards against unusual import-order edge cases during
# development where stataudit.py may not yet be on sys.path.
try:
    from stataudit import (  # noqa: F401
        Severity,
        Finding,
        AuditReport,
        StatAuditor,
        audit_text,
        audit_file,
        main,
    )
except ImportError:  # pragma: no cover
    pass

__all__ = [
    "Severity",
    "Finding",
    "AuditReport",
    "StatAuditor",
    "audit_text",
    "audit_file",
    "main",
]
