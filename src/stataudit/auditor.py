"""Core auditing logic: sentence-level rule application."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from .report import AuditReport, Finding, Severity
from ._rules import RULES


def _split_sentences(text: str) -> List[str]:
    """Split on sentence-ending punctuation followed by whitespace and an uppercase letter.

    This avoids splitting on common abbreviations such as "Fig.", "et al.", "Dr.", etc.
    """
    return re.split(r"(?<=[.!?])\s+(?=[A-Z\"])", text.strip())


def audit_text(text: str, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit *text* and return all Findings at or above *min_severity*."""
    if not text or not text.strip():
        return []
    findings: List[Finding] = []
    sentences = _split_sentences(text)
    for sent_idx, sentence in enumerate(sentences):
        location = f"sentence {sent_idx + 1}"
        for rule_name, pattern, severity, suggestion in RULES:
            if severity < min_severity:
                continue
            for m in pattern.finditer(sentence):
                start = max(0, m.start() - 25)
                end = min(len(sentence), m.end() + 25)
                snippet = sentence[start:end].strip()
                findings.append(
                    Finding(
                        rule=rule_name,
                        text=snippet,
                        location=location,
                        severity=severity,
                        suggestion=suggestion,
                    )
                )
    return findings


def audit_file(path: Path, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit a plain-text file and refine Finding locations to line numbers."""
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = audit_text(text, min_severity)
    lines = text.splitlines()
    for finding in findings:
        key = finding.text[:20]
        for i, line in enumerate(lines, 1):
            if key in line:
                finding.location = f"line {i}"
                break
    return findings


class StatAuditor:
    """High-level auditor that accepts either a file path or raw text.

    If *source* resolves to an existing file the file is read; otherwise
    *source* is treated as the text to audit directly.

    Parameters
    ----------
    source:
        File path string **or** raw manuscript text.
    min_severity:
        Lowest severity level to include in the report.
    """

    def __init__(self, source: str, min_severity: Severity = Severity.INFO) -> None:
        self.source = source
        self.min_severity = min_severity
        self._path: Optional[Path] = None
        p = Path(source)
        if p.exists() and p.is_file():
            self._path = p

    def run(self) -> AuditReport:
        """Execute the audit and return an :class:`AuditReport`."""
        if self._path is not None:
            findings = audit_file(self._path, self.min_severity)
            src_label = str(self._path)
        else:
            findings = audit_text(self.source, self.min_severity)
            src_label = "<text>"
        return AuditReport(source=src_label, findings=findings)
