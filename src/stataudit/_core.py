"""Core types and audit logic for stataudit."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Sequence, Tuple


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    def _order(self) -> int:
        return {"INFO": 0, "WARNING": 1, "ERROR": 2}[self.value]

    def __le__(self, other: "Severity") -> bool:
        return self._order() <= other._order()

    def __lt__(self, other: "Severity") -> bool:
        return self._order() < other._order()

    def __gt__(self, other: "Severity") -> bool:
        return self._order() > other._order()

    def __ge__(self, other: "Severity") -> bool:
        return self._order() >= other._order()


@dataclass
class Finding:
    rule: str
    text: str
    location: str
    severity: Severity
    suggestion: str

    def to_dict(self) -> dict:
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


# Tuple layout: (rule_name, compiled_pattern, severity, suggestion)
RuleSpec = Tuple[str, "re.Pattern[str]", Severity, str]

RULES: List[RuleSpec] = [
    (
        "pvalue_ns",
        re.compile(r"\bns\b|\(ns\)", re.IGNORECASE),
        Severity.WARNING,
        "Replace 'ns' with an exact p-value (e.g., p = .12).",
    ),
    (
        "pvalue_over_precision",
        # Catches p = .00001 style — values clearly below .001 should use p < .001
        re.compile(r"\bp\s*=\s*\.?0{3,}\d+", re.IGNORECASE),
        Severity.WARNING,
        "Values below .001 should be reported as p < .001, not with excessive zeros.",
    ),
    (
        "pvalue_exact",
        re.compile(r"\bp\s*[=<>]\s*[\d.]+(?:e[-+]?\d+)?\b", re.IGNORECASE),
        Severity.INFO,
        "Verify p-value precision: report to 2–3 decimal places or as p < .001.",
    ),
    (
        "ci_level_missing",
        # Fire when CI/confidence interval appears without a numeric level.
        # Lookbehind handles "95% CI" and "95%CI"; lookahead handles "CI [95%]".
        re.compile(
            r"(?<!% )(?<!%)\b(?:CI|confidence interval)\b(?!\s*\d)(?!\s*\[?\d)",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Specify the confidence level explicitly (e.g., 95% CI).",
    ),
    (
        "t_test_df_missing",
        re.compile(r"\bt\s*=\s*[-+]?[\d.]+(?!\s*\()"),
        Severity.WARNING,
        "Include degrees of freedom with the t-statistic: t(df) = value.",
    ),
    (
        "anova_missing_df",
        re.compile(r"\bF\s*=\s*[-+]?[\d.]+(?!\s*\()"),
        Severity.WARNING,
        "Include degrees of freedom with the F-statistic: F(df1, df2) = value.",
    ),
    (
        "sample_size_small",
        re.compile(r"\b[nN]\s*=\s*(?:[1-9]|[12]\d)\b"),
        Severity.WARNING,
        "Very small sample (N < 30) — verify statistical power is adequate.",
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
        "One-tailed tests require explicit a priori justification.",
    ),
    (
        "nhst_only",
        re.compile(
            r"\b(?:significant|insignificant|failed to reject)\b", re.IGNORECASE
        ),
        Severity.INFO,
        "Supplement significance language with effect sizes and confidence intervals.",
    ),
    (
        "outlier_handling",
        re.compile(r"\boutlier\b", re.IGNORECASE),
        Severity.INFO,
        "State the outlier detection criterion and how outliers were handled.",
    ),
    (
        "missing_data",
        re.compile(
            r"\bmissing\s+(?:data|values?|cases?)\b", re.IGNORECASE
        ),
        Severity.INFO,
        "Report the proportion of missing data and the imputation strategy used.",
    ),
    (
        "regression_r2_missing",
        # Matches "regression/regressed" NOT followed (before next sentence end) by R², R^2, R2, R-squared
        re.compile(
            r"\bregress(?:ed|ion)\b(?![^.!?]*(?:R[²2]|R\^2|R-squared))",
            re.IGNORECASE,
        ),
        Severity.WARNING,
        "Report R² (coefficient of determination) alongside regression results.",
    ),
    (
        "multiple_comparisons",
        re.compile(
            r"\b(?:bonferroni|FDR|false discovery|holm|benjamini)\b",
            re.IGNORECASE,
        ),
        Severity.INFO,
        "Confirm the multiple-comparisons correction method is stated explicitly.",
    ),
    (
        "correlation_missing_n",
        re.compile(r"\br\s*=\s*[-+]?0?\.\d+\b", re.IGNORECASE),
        Severity.INFO,
        "Report the sample size N when stating a correlation coefficient.",
    ),
]


def _split_sentences(text: str) -> List[str]:
    """Split *text* into sentences on sentence-ending punctuation."""
    return re.split(r"(?<=[.!?])\s+", text.strip())


def audit_text(
    text: str, min_severity: Severity = Severity.INFO
) -> List[Finding]:
    """Audit a plain-text string and return a list of :class:`Finding` objects.

    Parameters
    ----------
    text:
        The manuscript text to audit.
    min_severity:
        Only findings at or above this severity are returned.

    Returns
    -------
    List[Finding]
        Findings ordered by sentence position, then rule order.
    """
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


def audit_file(
    path: Path, min_severity: Severity = Severity.INFO
) -> List[Finding]:
    """Audit a plain-text file and map each finding to its source line.

    Parameters
    ----------
    path:
        Path to the text file.
    min_severity:
        Only findings at or above this severity are returned.

    Returns
    -------
    List[Finding]
        Findings with ``location`` set to ``"line N"`` where possible.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    findings = audit_text(text, min_severity)
    lines = text.splitlines()
    for finding in findings:
        # Use the first 30 chars of the snippet to locate the source line
        snippet = finding.text[:30]
        for line_no, line in enumerate(lines, 1):
            if snippet in line:
                finding.location = f"line {line_no}"
                break
    return findings
