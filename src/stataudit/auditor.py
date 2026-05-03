"""StatAuditor: high-level facade for running an audit."""
from __future__ import annotations

from pathlib import Path
from typing import Union

from ._core import Severity, audit_file, audit_text
from .report import AuditReport


class StatAuditor:
    """Audit statistical reporting in a manuscript.

    Parameters
    ----------
    source:
        Either a path to a plain-text file or a raw text string.  If a
        :class:`~pathlib.Path` or a string that resolves to an existing file
        is supplied the file is read; otherwise the value is treated as raw
        text.
    min_severity:
        Minimum :class:`~stataudit._core.Severity` level to include in the
        report.  Defaults to ``Severity.INFO`` (all findings).

    Examples
    --------
    >>> from stataudit import StatAuditor
    >>> auditor = StatAuditor("The effect was significant (p < 0.05).")
    >>> report = auditor.run()
    >>> len(report.findings) > 0
    True
    """

    def __init__(
        self,
        source: Union[str, Path],
        min_severity: Severity = Severity.INFO,
    ) -> None:
        self._path: Path | None = None
        self._text: str | None = None
        self._label: str

        candidate = Path(source) if isinstance(source, str) else source
        if isinstance(source, Path) or candidate.is_file():
            self._path = candidate
            self._label = str(candidate)
        else:
            self._text = str(source)
            self._label = "<text>"

        self.min_severity = min_severity

    def run(self) -> AuditReport:
        """Run the audit and return an :class:`~stataudit.report.AuditReport`.

        Returns
        -------
        AuditReport
            Report containing all findings above ``min_severity``.
        """
        if self._path is not None:
            findings = audit_file(self._path, self.min_severity)
        else:
            findings = audit_text(self._text or "", self.min_severity)
        return AuditReport(source=self._label, findings=findings)
