"""
Core auditing engine for stataudit.

Defines :class:`Severity`, :class:`Finding`, :class:`AuditReport`, the
built-in detection rules, and the public :func:`audit_text` /
:func:`audit_file` API functions.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Tuple


class Severity(str, Enum):
    """Severity level for an audit finding.

    Ordered from least to most critical: ``INFO < WARNING < ERROR``.
    Inherits from :class:`str` so values are JSON-serialisable without
    extra conversion.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    def _order(self) -> int:
        return {"INFO": 0, "WARNING": 1, "ERROR": 2}[self.value]

    def __le__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() <= other._order()

    def __lt__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() < other._order()

    def __gt__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() > other._order()

    def __ge__(self, other: "Severity") -> bool:  # type: ignore[override]
        return self._order() >= other._order()


@dataclass
class Finding:
    """A single audit finding produced by one detection rule.

    Attributes:
        rule: Identifier of the detection rule that triggered this finding.
        text: Short excerpt from the source text surrounding the match.
        location: Human-readable location string (e.g. ``"line 42"`` or
            ``"sentence 3"``).
        severity: Severity level of the finding.
        suggestion: Actionable suggestion for resolving the issue.
    """

    rule: str
    text: str
    location: str
    severity: Severity
    suggestion: str

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dictionary representation."""
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    def __str__(self) -> str:
        return (
            f"[{self.severity.value}] {self.rule}\n"
            f"  Text      : {self.text!r}\n"
            f"  Location  : {self.location}\n"
            f"  Suggestion: {self.suggestion}"
        )


# ---------------------------------------------------------------------------
# Detection rules
# Each entry: (rule_name, compiled_pattern, severity, suggestion)
# ---------------------------------------------------------------------------
_RuleEntry = Tuple[str, "re.Pattern[str]", Severity, str]

_RULES: List[_RuleEntry] = [
    (
        "pvalue_exact",
        re.compile(r"\bp\s*[=<>]\s*[\d.]+(?:e[-+]?\d+)?\b", re.IGNORECASE),
        Severity.INFO,
        "Report exact p-value with appropriate precision (e.g., p = .034 or p < .001).",
    ),
    (
        "pvalue_ns",
        re.compile(r"\bns\b|\(ns\)", re.IGNORECASE),
        Severity.WARNING,
        "Replace 'ns' with an exact p-value (e.g., p = .12).",
    ),
    (
        "pvalue_over_precision",
        # Matches p = .000012 or p = 0.000012 (four or more leading zeros after decimal)
        re.compile(r"\bp\s*=\s*0?\.0{4,}\d", re.IGNORECASE),
        Severity.INFO,
        "Extremely small p-values should be reported as p < .001.",
    ),
    (
        "ci_level_missing",
        # Fires when CI/confidence interval is not immediately preceded by a percentage
        re.compile(r"\b(?:CI|confidence\s+interval)\b(?!\s*\d)", re.IGNORECASE),
        Severity.WARNING,
        "Specify the confidence level (e.g., 95% CI [lower, upper]).",
    ),
    (
        "t_test_df_missing",
        # t = value without (df) immediately after the value
        re.compile(r"\bt\s*=\s*[-+]?\d*\.?\d+(?!\s*\()"),
        Severity.WARNING,
        "Include degrees of freedom: t(df) = value.",
    ),
    (
        "anova_missing_df",
        # F = value without (df1, df2) immediately after
        re.compile(r"\bF\s*=\s*[-+]?\d*\.?\d+(?!\s*\()"),
        Severity.WARNING,
        "Include degrees of freedom: F(df_between, df_within) = value.",
    ),
    (
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*(?:[1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power.",
    ),
    (
        "over_precision",
        re.compile(r"\b\d+\.\d{5,}\b"),
        Severity.INFO,
        "Excessive decimal places — report to 2–3 significant decimal places.",
    ),
    (
        "one_tailed",
        re.compile(r"\bone[- ]?tailed\b", re.IGNORECASE),
        Severity.WARNING,
        "One-tailed tests require strong a priori justification.",
    ),
    (
        "nhst_only",
        re.compile(r"\b(?:significant|insignificant|failed\s+to\s+reject)\b", re.IGNORECASE),
        Severity.INFO,
        "Supplement NHST language with effect sizes and confidence intervals.",
    ),
    (
        "outlier_handling",
        re.compile(r"\boutliers?\b", re.IGNORECASE),
        Severity.INFO,
        "Describe the outlier detection criterion and number of cases removed.",
    ),
    (
        "missing_data",
        re.compile(r"\bmissing\s+(?:data|values?|cases?)\b", re.IGNORECASE),
        Severity.INFO,
        "Report proportion of missing data and the imputation or exclusion strategy.",
    ),
    (
        "regression_r2_missing",
        re.compile(r"\bregress(?:ed|ion)\b", re.IGNORECASE),
        Severity.WARNING,
        "Report R² (and adjusted R² if applicable) alongside regression results.",
    ),
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false\s+discovery|holm|benjamini)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Verify the multiple-comparisons correction method is explicitly stated.",
    ),
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report sample size alongside a correlation coefficient.",
    ),
]


def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences on sentence-ending punctuation.

    Uses a look-behind split on ``.``, ``!``, or ``?`` followed by
    whitespace. Sufficient for the structured prose typical of academic
    manuscripts.

    Parameters
    ----------
    text:
        Raw input text.

    Returns
    -------
    List[str]
        Non-empty list of sentence strings.
    """
    return re.split(r"(?<=[.!?])\s+", text.strip())


def audit_text(text: str, min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit a plain-text string for statistical reporting issues.

    Each sentence of *text* is checked against all built-in detection
    rules. A :class:`Finding` is produced for every pattern match.

    Parameters
    ----------
    text:
        Academic text to audit (one or more paragraphs).
    min_severity:
        Only return findings at or above this severity level.  Defaults
        to :attr:`Severity.INFO` (all findings included).

    Returns
    -------
    List[Finding]
        Findings in document order.  Empty if the text is clean or all
        matches fall below *min_severity*.
    """
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


def audit_file(path: "Path | str", min_severity: Severity = Severity.INFO) -> List[Finding]:
    """Audit a text file for statistical reporting issues.

    Reads *path*, delegates to :func:`audit_text`, and replaces each
    finding's ``location`` with a ``"line N"`` string when the match
    can be attributed to a specific source line.

    Parameters
    ----------
    path:
        Path to a readable plain-text file (UTF-8 assumed; non-decodable
        bytes are replaced with the Unicode replacement character).
    min_severity:
        Minimum severity threshold; see :func:`audit_text`.

    Returns
    -------
    List[Finding]
        Findings with ``location`` set to ``"line N"`` wherever possible,
        otherwise ``"sentence N"``.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist or is not a file.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

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


@dataclass
class AuditReport:
    """Container for a complete audit run.

    Parameters
    ----------
    source:
        Human-readable label for the audited input (file path or
        ``"<stdin>"``).
    findings:
        List of :class:`Finding` objects produced by the audit.
    """

    source: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        """Return a summary mapping with total and per-severity counts.

        Returns
        -------
        dict
            Keys: ``source`` (str), ``total`` (int), ``by_severity``
            (dict mapping severity name → count).
        """
        counts: dict = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return {
            "source": self.source,
            "total": len(self.findings),
            "by_severity": counts,
        }

    def to_markdown(self) -> str:
        """Render the report as a Markdown string."""
        s = self.summary["by_severity"]
        lines = [
            "# Statistical Audit Report",
            "",
            f"**Source:** {self.source}",
            f"**Total findings:** {len(self.findings)}",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| ERROR    | {s['ERROR']} |",
            f"| WARNING  | {s['WARNING']} |",
            f"| INFO     | {s['INFO']} |",
            "",
        ]
        if not self.findings:
            lines.append("_No findings._")
            return "\n".join(lines)

        by_sev: dict = {"ERROR": [], "WARNING": [], "INFO": []}
        for f in self.findings:
            by_sev[f.severity.value].append(f)

        for sev in ("ERROR", "WARNING", "INFO"):
            group = by_sev[sev]
            if not group:
                continue
            lines += [f"## {sev}", ""]
            for f in group:
                lines += [
                    f"### `{f.rule}`",
                    f"- **Location:** {f.location}",
                    f"- **Text:** `{f.text}`",
                    f"- **Suggestion:** {f.suggestion}",
                    "",
                ]
        return "\n".join(lines)

    def to_json(self, indent: int = 2) -> str:
        """Render the report as a JSON string.

        Parameters
        ----------
        indent:
            Indentation width in spaces (default 2).
        """
        return json.dumps(
            {
                "summary": self.summary,
                "findings": [f.to_dict() for f in self.findings],
            },
            indent=indent,
            ensure_ascii=False,
        )

    def to_text(self) -> str:
        """Render the report as a plain-text string."""
        if not self.findings:
            return f"No findings for {self.source}."
        lines = [
            f"Audit report for: {self.source}",
            f"Total findings: {len(self.findings)}",
            "",
        ]
        for f in self.findings:
            lines.append(str(f))
            lines.append("")
        return "\n".join(lines)
