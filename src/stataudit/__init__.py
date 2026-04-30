"""
stataudit: Automated statistical reporting audit tool for scientific manuscripts.

This shim re-exports the public API from the canonical ``stataudit`` module.
See the top-level ``stataudit.py`` for the full implementation.
"""

from stataudit import (  # noqa: F401
    AuditReport,
    Finding,
    Severity,
    __author__,
    __license__,
    __version__,
    audit_file,
    audit_text,
    main,
)

__all__ = [
    "AuditReport",
    "Finding",
    "Severity",
    "audit_text",
    "audit_file",
    "main",
    "__version__",
    "__author__",
    "__license__",
]
