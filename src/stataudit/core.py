"""Core auditing functions: audit_text and audit_file."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .models import Finding, Severity
from .rules import _RULES


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences at sentence-ending punctuation."""
    return re.split(r"(?<=[.!?])\s+", text.strip())


def audit_text(text: str, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit a string and return all Findings at or above min_severity."""
    if not text or not text.strip():
        return []
    findings: List[Finding] = []
    sentences = _split_sentences(text)
    for sent_idx, sentence in enumerate(sentences):
        location = f"sentence {sent_idx + 1}"
        for rule_name, pattern, severity, suggestion in _RULES:
            if severity < min_severity:
                continue
            for m in pattern.finditer(sentence):
                start = max(0, m.start() - 20)
                end = min(len(sentence), m.end() + 20)
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
    """Audit a text file and map each Finding to a line number."""
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = audit_text(text, min_severity)
    lines = text.splitlines()
    for finding in findings:
        # Map the snippet back to the first matching line
        needle = finding.text[:20]
        for i, line in enumerate(lines, 1):
            if needle in line:
                finding.location = f"line {i}"
                break
    return findings
