"""High-level StatAuditor class for auditing manuscripts."""
from __future__ import annotations

from pathlib import Path

from .core import audit_file, audit_text
from .models import Severity


class StatAuditor:
    """
    High-level interface for auditing an academic manuscript.

    Parameters
    ----------
    source:
        Path to a text file, or raw manuscript text.

    Examples
    --------
    >>> auditor = StatAuditor("manuscript.txt")
    >>> report = auditor.run()
    >>> for finding in report.findings:
    ...     print(finding.severity, finding.message, finding.location)
    """

    def __init__(self, source: str) -> None:
        self.source = source
        p = Path(source)
        self._path: Path | None = p if p.is_file() else None

    def run(self, min_severity: Severity = Severity.INFO) -> "AuditReport":  # noqa: F821
        """Run the audit and return an AuditReport."""
        from .report import AuditReport  # local import avoids circular dependency

        if self._path is not None:
            findings = audit_file(self._path, min_severity)
        else:
            findings = audit_text(self.source, min_severity)
        return AuditReport(source=self.source, findings=findings)
