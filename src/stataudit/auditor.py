"""Core auditing logic."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .report import AuditReport, Finding, Severity
from .rules import RULES


def _split_sentences(text: str) -> List[str]:
    return re.split(r"(?<=[.!?])\s+", text.strip())


def audit_text(text: str, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Return a list of :class:`Finding` objects for statistical issues in *text*."""
    if not text:
        return []
    findings: List[Finding] = []
    sentences = _split_sentences(text)
    for sent_idx, sentence in enumerate(sentences):
        location = f"sentence {sent_idx + 1}"
        for rule_name, pattern, severity, suggestion in RULES:
            if severity < min_severity:
                continue
            for m in pattern.finditer(sentence):
                start = max(0, m.start() - 20)
                snippet = sentence[start : m.end() + 20].strip()
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
    """Audit a text file and map findings to line numbers."""
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = audit_text(text, min_severity)
    lines = text.splitlines()
    for finding in findings:
        snippet = finding.text[:20]
        for i, line in enumerate(lines, 1):
            if snippet in line:
                finding.location = f"line {i}"
                break
    return findings


class StatAuditor:
    """High-level auditor that wraps :func:`audit_file` / :func:`audit_text`.

    Parameters
    ----------
    source:
        Path to a text file *or* a raw text string.
    min_severity:
        Only include findings at or above this level.
    """

    def __init__(
        self,
        source: str,
        min_severity: Severity = Severity.INFO,
    ) -> None:
        self.source = source
        self.min_severity = min_severity

    def run(self) -> AuditReport:
        """Execute the audit and return an :class:`AuditReport`."""
        path = Path(self.source)
        if path.is_file():
            findings = audit_file(path, self.min_severity)
        else:
            findings = audit_text(self.source, self.min_severity)
        return AuditReport(source=self.source, findings=findings)
